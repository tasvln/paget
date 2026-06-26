from fastapi import FastAPI
from typing import Dict, List
import json
from pathlib import Path
import time
import threading

from models import Task, Agent, ManagerState

app = FastAPI()

STATE_FILE = Path("shared/manager_state.json")
STATE_FILE.parent.mkdir(exist_ok=True)

task_lock = threading.Lock()


# ----------------------------
# state load/save (unchanged)
# ----------------------------
def load():
    """Load state from disk"""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            data = json.load(f)
            agents = {aid: Agent(**a) for aid, a in data.get('agents', {}).items()}
            tasks = [Task(**t) for t in data.get('tasks', [])]
            return ManagerState(
                project_name=data.get('project_name', 'untitled'),
                agents=agents,
                tasks=tasks,
                task_queue=data.get('task_queue', [])
            )
    return ManagerState(agents={}, tasks=[], task_queue=[])

def save(state: ManagerState):
    """Save state to disk"""
    with open(STATE_FILE, "w") as f:
        f.write(state.model_dump_json(indent=2))

state = load()


# ----------------------------
# routes
# ----------------------------
@app.get("/")
def root():
    """Health check with stats"""
    done = sum(1 for t in state.tasks if t.status == "done")
    in_prog = sum(1 for t in state.tasks if t.status == "in_progress")
    pending = sum(1 for t in state.tasks if t.status == "pending")

    return {
        "status": "coordinator running",
        "project": state.project_name,
        "agents": len(state.agents),
        "tasks": {
            "done": done,
            "in_progress": in_prog,
            "pending": pending
        }
    }

@app.post("/agent/register")
def register_agent(agent_id: str):
    """Register a new agent"""
    with task_lock:
        agent = state.get_agent(agent_id)
        agent.status = "idle"
        save(state)
    return {"status": "registered"}

@app.post("/agent/status/{agent_id}")
def update_agent_status(agent_id: str, body: dict):
    """Update agent status (idle, working, error)"""
    with task_lock:
        agent = state.get_agent(agent_id)
        agent.status = body.get("status", "idle")
        agent.current_task = body.get("current_task", None)
        agent.last_update = time.time()
        save(state)
    return {"status": "updated"}

def are_dependencies_met(task_id: str) -> bool:
    """Check if all task dependencies are done"""
    task = state.get_task(task_id)
    if not task or not task.depends_on:
        return True
    for dep_id in task.depends_on:
        dep_task = state.get_task(dep_id)
        if not dep_task or dep_task.status != "done":
            return False
    return True


@app.post("/task/create")
def create_task(
    task_id: str,
    description: str,
    spec_requirements: str = "{}",
    depends_on: str = "[]",
    parent_task: str = None,
    task_type: str = "implementation",  # NEW — replaces string-matched task IDs like "{project}-test"
    component_id: str = None            # NEW — set on validation tasks, points back at the implementation task
):
    """Create a new task or re-activate existing one"""
    with task_lock:
        existing = state.get_task(task_id)

        if existing:
            if existing.status in ("done", "failed"):
                existing.status = "pending"
                existing.retry_count = 0
                existing.result = ""
                existing.validation_errors = []

                try:
                    deps = json.loads(depends_on) if depends_on else []
                except Exception:
                    deps = []

                if not deps and task_id not in state.task_queue:
                    state.task_queue.append(task_id)

                save(state)
                return {"status": "task re-activated"}
            else:
                return {"status": "task already exists"}

        try:
            spec_reqs = json.loads(spec_requirements) if spec_requirements else {}
            deps = json.loads(depends_on) if depends_on else []
        except Exception:
            spec_reqs, deps = {}, []

        task = Task(
            id=task_id,
            description=description,
            status="pending",
            assigned_to="",
            spec_requirements=spec_reqs,
            depends_on=deps,
            parent_task=parent_task,
            task_type=task_type,
            component_id=component_id
        )

        state.tasks.append(task)

        if not deps:
            state.task_queue.append(task_id)

        save(state)
        return {"status": "task created"}


@app.get("/agent/task/next/{agent_id}")
def get_next_task(agent_id: str, task_type: str = None):
    """
    Get next available task for agent.

    task_type filters the queue to only tasks this agent can actually do —
    e.g. specialist.py passes task_type=implementation, validator.py passes
    task_type=validation. Without this, any free agent grabs whatever's
    next in the queue regardless of kind, which lets a validator end up
    "completing" an implementation task (reporting file-not-found because
    it never writes code) and a specialist end up trying to validate
    something. If task_type is omitted, behavior is unfiltered (accepts
    anything), kept for backward compatibility.
    """
    with task_lock:
        available = [
            tid for tid in state.task_queue
            if are_dependencies_met(tid)
            and (task_type is None or state.get_task(tid).task_type == task_type)
        ]

        if not available:
            return {"task": None}

        task_id = available[0]
        state.task_queue.remove(task_id)

        task = state.get_task(task_id)
        if task:
            task.status = "in_progress"
            task.assigned_to = agent_id
            task.start_time = time.time()

            agent = state.get_agent(agent_id)
            agent.status = "working"
            agent.current_task = task_id

            save(state)
            return {"task": task.model_dump()}

    return {"task": None}


# ----------------------------
# refinement — single source of truth, lives only here now.
# Manager no longer has find_failed_tasks / create_refinement_tasks /
# monitor_and_refine — delete those when you update manager.py.
# ----------------------------
def create_refinement_task(target: Task, errors: List[str]) -> str:
    """
    Refine an IMPLEMENTATION task IN PLACE — same id, same object, just a
    new description (with feedback folded in) and status reset to pending
    so it goes back into the queue. `target` is always the implementation
    task that needs fixing — for a failed validation task, the caller
    resolves target via component_id before calling this.

    This used to create a brand new task with id "{target.id}-refine-v{n}"
    each retry. That broke validation tasks that depend_on the original
    id: once the original task's status became "failed" permanently, any
    validation task depending on it could never unlock, even after a
    refinement succeeded, because depends_on still pointed at the old
    (failed) id and nothing ever rewrote it. Reusing the same id sidesteps
    the problem entirely — nothing depending on this id ever needs to be
    updated, because the id never changes.

    Two more bugs fixed here after observing a real run:

    1. original_description is captured ONCE (first refinement only) and
       reused on every subsequent retry. The old code took
       target.description.split('\n')[0] each time — but description gets
       overwritten to "Refine: ..." after the first retry, so the SECOND
       retry's first line was already "Refine: " with nothing after it.
       Confirmed in a live run as "Refine: Refine: Refine: " nesting
       across three retries.

    2. Feedback text uses plain "- " instead of "✗"/"•" unicode bullets.
       A live run showed the model echoing those exact unicode characters
       back as literal characters in its "code" output, which then failed
       to compile with "invalid character '✗'" — i.e. the error-reporting
       formatting was leaking into and corrupting the next attempt.
    """
    target.retry_count += 1

    # Capture the original description text on the FIRST refinement only,
    # so it doesn't get overwritten/lost on subsequent retries.
    if target.original_description is None:
        target.original_description = target.description.split(chr(10))[0]

    error_text = "\n".join(f"- {e}" for e in errors)
    target.description = (
        f"Refine: {target.original_description}\n\n"
        f"Previous attempt failed with:\n{error_text}\n\n"
        f"Requirements (unchanged):\n" +
        "\n".join(f"- {r}" for r in (target.spec_requirements or []))
    )
    target.status = "pending"
    target.validation_errors = errors
    target.result = ""

    if target.id not in state.task_queue:
        state.task_queue.append(target.id)

    return target.id


@app.post("/agent/task/complete/{agent_id}")
def complete_task(agent_id: str, task_id: str, body: dict):
    """
    Complete task - mark as done, or route failure to the right target.

    For an "implementation" task, the target of refinement is the task
    itself (same as before). For a "validation" task, the target is
    component_id — the validation task has nothing to fix, the bug lives in
    the implementation it checked.
    """
    result = body.get("result", "")
    validation_errors = body.get("validation_errors", [])

    with task_lock:
        task = state.get_task(task_id)
        if not task:
            return {"status": "task not found"}

        agent = state.get_agent(agent_id)

        if validation_errors:
            if task.task_type == "validation" and task.component_id:
                target = state.get_task(task.component_id)
            else:
                target = task

            if target is None:
                task.status = "failed"
                task.result = result
                task.validation_errors = validation_errors
                agent.status = "idle"
                agent.current_task = None
                agent.errors += 1
                save(state)
                return {"status": "task failed, target not found"}

            # If task and target are different objects, task is a
            # validation wrapper — mark IT failed permanently for
            # visibility (validation tasks are never themselves refined).
            # If task IS target (a plain implementation task failing on
            # its own with no validation wrapper), don't touch status here
            # at all — create_refinement_task below is the sole owner of
            # target.status in that case, avoiding a confusing
            # failed-then-immediately-pending flip on the same object.
            if task is not target:
                task.status = "failed"
                task.validation_errors = validation_errors

            if target.retry_count < target.max_retries:
                refinement_id = create_refinement_task(target, validation_errors)
                agent.status = "idle"
                agent.current_task = None
                save(state)
                return {"status": "task failed, refinement created", "refinement": refinement_id}
            else:
                target.status = "failed"
                target.validation_errors = validation_errors
                agent.status = "idle"
                agent.current_task = None
                agent.errors += 1
                save(state)
                return {"status": "task failed, max retries exceeded on target"}
        else:
            # Success
            task.status = "done"
            task.result = result
            task.end_time = time.time()
            task_duration = task.end_time - task.start_time

            agent.tasks_completed += 1
            agent.total_time += task_duration
            agent.avg_time_per_task = agent.total_time / agent.tasks_completed
            agent.status = "idle"
            agent.current_task = None

            # Unlock dependents
            for other in state.tasks:
                if other.status == "pending" and task_id in other.depends_on:
                    if are_dependencies_met(other.id) and other.id not in state.task_queue:
                        state.task_queue.append(other.id)

            # If this was the LAST validation task for the project to pass,
            # generate main.py wiring up every component. Checking this on
            # every successful completion (not just validation ones) is
            # cheap and avoids needing a separate "are we done" poller.
            if task.task_type == "validation":
                maybe_generate_main(task.parent_task)

            save(state)
            return {"status": "task completed"}


def maybe_generate_main(project_name: str):
    """
    If every validation task belonging to this project is now "done",
    write output/main.py importing each component module. Does nothing
    (silently) if the project isn't fully validated yet, or if there are
    no validation tasks at all (e.g. validator wasn't used this run).
    """
    if not project_name:
        return

    validation_tasks = [
        t for t in state.tasks
        if t.parent_task == project_name and t.task_type == "validation"
    ]
    if not validation_tasks:
        return
    if not all(t.status == "done" for t in validation_tasks):
        return

    component_ids = [t.component_id for t in validation_tasks if t.component_id]
    if not component_ids:
        return

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    lines = [
        f'"""',
        f"Auto-generated entry point for project '{project_name}'.",
        f"Generated once all {len(component_ids)} component(s) passed validation.",
        f"",
        f"Uses importlib instead of plain 'import' because component ids",
        f"(and therefore filenames) contain hyphens, e.g. '{component_ids[0]}.py' —",
        f"'import {component_ids[0]}' is not valid Python syntax.",
        f'"""',
        "",
        "import importlib.util",
        "import os",
        "",
        "_here = os.path.dirname(os.path.abspath(__file__))",
        "_modules = {}",
        "",
        "def _load(component_id):",
        "    path = os.path.join(_here, f'{component_id}.py')",
        "    spec = importlib.util.spec_from_file_location(component_id, path)",
        "    module = importlib.util.module_from_spec(spec)",
        "    spec.loader.exec_module(module)",
        "    return module",
        "",
    ]
    for cid in component_ids:
        lines.append(f"_modules['{cid}'] = _load('{cid}')")
    lines.append("")
    lines.append("if __name__ == '__main__':")
    lines.append(f"    print('{project_name}: all components loaded successfully')")
    for cid in component_ids:
        lines.append(f"    print('  - {cid}:', _modules['{cid}'].__file__)")

    main_path = output_dir / "main.py"
    main_path.write_text("\n".join(lines) + "\n")
    print(f"[coordinator] All components validated — generated {main_path}")


@app.get("/state")
def get_state():
    """Get full coordinator state"""
    return state.model_dump()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)