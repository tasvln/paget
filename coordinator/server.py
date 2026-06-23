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


# state load/save
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


# routes

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
            if existing.status == "done":
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
def get_next_task(agent_id: str):
    """Get next available task for agent"""
    with task_lock:
        available = [
            tid for tid in state.task_queue
            if are_dependencies_met(tid)
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
        Create a refinement task for an IMPLEMENTATION task. `target` is always
        the implementation task that needs fixing — for a failed validation
        task, the caller resolves target via component_id before calling this.
    """
    target.retry_count += 1
    refinement_id = f"{target.id}-refine-v{target.retry_count}"

    error_text = "\n".join(f"  ✗ {e}" for e in errors)
    description = (
        f"Refine: {target.description.split(chr(10))[0]}\n\n"
        f"Previous attempt failed with:\n{error_text}\n\n"
        f"Requirements (unchanged):\n" +
        "\n".join(f"  • {r}" for r in (target.spec_requirements or []))
    )

    refinement = Task(
        id=refinement_id,
        description=description,
        status="pending",
        parent_task=target.parent_task,
        spec_requirements=target.spec_requirements,
        retry_count=target.retry_count,
        max_retries=target.max_retries,
        task_type="implementation",
        component_id=target.id,
    )
    state.tasks.append(refinement)
    state.task_queue.append(refinement_id)
    return refinement_id


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

            # Validation tasks themselves are marked failed for visibility
            # but are never retried/refined directly — only implementation
            # tasks are.
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

            save(state)
            return {"status": "task completed"}


@app.get("/state")
def get_state():
    """Get full coordinator state"""
    return state.model_dump()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)