from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List
import json
from pathlib import Path
import asyncio

app = FastAPI()

STATE_FILE = Path("shared/manager_state.json")
STATE_FILE.parent.mkdir(exist_ok=True)

# status would be -> "pending", "in_progress", "done"
class Task(BaseModel):
    id: str
    description: str
    assigned_to: str
    status: str 
    result: str = ""

# with the laws of parallel computing
class ManagerState(BaseModel):
    agents: Dict[str, dict]  # agent_id -> {status, last_heartbeat, etc}
    tasks: List[Task]
    task_queue: List[str]  # task IDs waiting to be done


# functions
# ----------------------------
# load or create initial state
def load():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            data = json.load(f)
            return ManagerState(**data)
    return ManagerState(agents={}, tasks=[], task_queue=[])

# save the present state
def save(state: ManagerState):
    with open(STATE_FILE, "w") as f:
        f.write(state.model_dump_json(indent=2))

# the entire application shares one in-memory object
state = load()


# routes
# ----------------------------
# root 
@app.get("/")
def root():
    """Health check"""
    return {"status": "agent manager running", "agents": len(state.agents), "tasks": len(state.tasks)}

# Register Agent
# POST /agent/register?agent_id=agentA
@app.post("/agent/register")
def register_agent(agent_id: str):
    """Registering Agent"""
    state.agents[agent_id] = {
        "status": "idle",
        "last_heartbeat": None,
        "tasks_completed": 0
    }
    save(state)
    return {"status": "registered"}

# GET next task
@app.get("/agent/task/next/{agent_id}")
def get_next_task(agent_id: str):
    """Agent asks what to do next: what should I do?"""
    if not state.task_queue:
        return {"task": None}
    
    task_id = state.task_queue.pop(0)
    task = next((t for t in state.tasks if t.id == task_id), None)

    if task:
        task.status = "in_progress"
        task.assigned_to = agent_id
        save(state)
        return {"task": task.model_dump()}
    
    return {"task": None}

# if agent has completed a task
# POST /agent/complete-task/agentA?task_id=task1&result=finished
@app.post("/agent/task/complete/{agent_id}")
def complete_task(agent_id: str, task_id: str, body: dict):
    """Agent says: I finished this task"""
    result = body.get("result", "")
    task = next((t for t in state.tasks if t.id == task_id), None)

    if task:
        task.status = "done"
        task.result = result
        state.agents[agent_id]["tasks_completed"] += 1
        save(state)
        print(f"[DEBUG] Task {task_id} marked as done by {agent_id}")
        return {"status": "task completed"}
    
    print(f"[DEBUG] Task {task_id} not found")
    return {"status": "task not found"}

# create a task
@app.post("/task/create")
def create_task(task_id: str, description: str):
    """Create a new task for agents to pick up"""

    task = Task(
        id = task_id,
        description = description,
        assigned_to = "",
        status = "pending"
    )

    state.tasks.append(task)
    state.task_queue.append(task_id)

    save(state)

    return {"status": "task created"}

@app.get("/state")
def get_state():
    """Peek at current state"""

    return state.model_dump()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)



