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


# functions
# ----------------------------
# load or create initial state
def load():
    """Load state from disk"""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            data = json.load(f)
            # Reconstruct models
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
# ----------------------------
# root 
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

# Register Agent
# POST /agent/register?agent_id=agentA
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
    task = next((t for t in state.tasks if t.id == task_id), None)
    if not task or not task.depends_on:
        return True
    
    for dep_id in task.depends_on:
        dep_task = next((t for t in state.tasks if t.id == dep_id), None)
        if not dep_task or dep_task.status != "done":
            return False
    return True

@app.post("/task/create")
def create_task(
    task_id: str,
    description: str,
    spec_requirements: str = "{}",
    depends_on: str = "[]",
    parent_task: str = None
):
    """Create a new task or re-activate existing one"""
    
    with task_lock:
        # Check if task exists
        existing = next((t for t in state.tasks if t.id == task_id), None)
        
        if existing:
            # Task exists - re-activate if done
            if existing.status == "done":
                existing.status = "pending"
                existing.retry_count = 0
                existing.result = ""
                existing.validation_errors = []
                
                # Re-add to queue if no dependencies or deps are met
                try:
                    spec_reqs = json.loads(spec_requirements) if spec_requirements else {}
                    deps = json.loads(depends_on) if depends_on else []
                except:
                    spec_reqs, deps = {}, []
                
                if not deps and task_id not in state.task_queue:
                    state.task_queue.append(task_id)
                
                save(state)
                return {"status": "task re-activated"}
            else:
                return {"status": "task already exists"}
        
        # Create new task
        try:
            spec_reqs = json.loads(spec_requirements) if spec_requirements else {}
            deps = json.loads(depends_on) if depends_on else []
        except:
            spec_reqs, deps = {}, []
        
        task = Task(
            id=task_id,
            description=description,
            status="pending",
            assigned_to="",
            spec_requirements=spec_reqs,
            depends_on=deps,
            parent_task=parent_task
        )
        
        state.tasks.append(task)
        
        # Add to queue if no dependencies
        if not deps:
            state.task_queue.append(task_id)
        
        save(state)
        return {"status": "task created"}
    
# GET next task
@app.get("/agent/task/next/{agent_id}")
def get_next_task(agent_id: str):
    """Get next available task for agent"""
    
    with task_lock:
        # Find pending tasks with met dependencies
        available = [
            tid for tid in state.task_queue
            if are_dependencies_met(tid)
        ]
        
        if not available:
            return {"task": None}
        
        task_id = available[0]
        state.task_queue.remove(task_id)
        
        task = next((t for t in state.tasks if t.id == task_id), None)
        if task:
            task.status = "in_progress"
            task.assigned_to = agent_id
            task.start_time = time.time()
            
            # Update agent status
            agent = state.get_agent(agent_id)
            agent.status = "working"
            agent.current_task = task_id
            
            save(state)
            return {"task": task.model_dump()}
    
    return {"task": None}

# if agent has completed a task
# POST /agent/complete-task/agentA?task_id=task1&result=finished
@app.post("/agent/task/complete/{agent_id}")
def complete_task(agent_id: str, task_id: str, body: dict):
    """Complete task - mark as done or create refinement"""
    
    result = body.get("result", "")
    validation_errors = body.get("validation_errors", [])
    
    with task_lock:
        task = next((t for t in state.tasks if t.id == task_id), None)
        if not task:
            return {"status": "task not found"}
        
        agent = state.get_agent(agent_id)
        
        if validation_errors:
            # Validation failed - create refinement or mark failed
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.validation_errors = validation_errors
                task.status = "failed"
                
                # Create refinement task
                refinement_id = f"{task_id}-refine-v{task.retry_count}"
                refinement = Task(
                    id=refinement_id,
                    description=f"Refine: {task.description}\n\nFeedback:\n" + 
                                "\n".join(f"- {e}" for e in validation_errors),
                    status="pending",
                    parent_task=task_id,
                    spec_requirements=task.spec_requirements
                )
                state.tasks.append(refinement)
                state.task_queue.append(refinement_id)
                
                agent.status = "idle"
                agent.current_task = None
                save(state)
                return {"status": "task failed, refinement created"}
            else:
                task.status = "failed"
                task.result = result
                task.validation_errors = validation_errors
                agent.status = "idle"
                agent.current_task = None
                agent.errors += 1
                save(state)
                return {"status": "task failed, max retries exceeded"}
        else:
            # Success
            task.status = "done"
            task.result = result
            task.end_time = time.time()
            task_duration = task.end_time - task.start_time
            
            # Update agent metrics
            agent.tasks_completed += 1
            agent.total_time += task_duration
            agent.avg_time_per_task = agent.total_time / agent.tasks_completed
            agent.status = "idle"
            agent.current_task = None
            
            # Unlock dependent tasks
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



