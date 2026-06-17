from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List
import json
from pathlib import Path
import asyncio

from datetime import datetime
import time
import threading

app = FastAPI()

STATE_FILE = Path("shared/manager_state.json")
STATE_FILE.parent.mkdir(exist_ok=True)

class Task(BaseModel):
    id: str
    description: str
    assigned_to: str
    status: str  # "pending", "in_progress", "done"
    result: str = ""
    created_at: float = None
    start_time: float = None
    end_time: float = None
    
    def __init__(self, **data):
        super().__init__(**data)
        if self.created_at is None:
            self.created_at = time.time()

# In agent status
class AgentStatus:
    status: str  # "idle", "working", "error"
    current_task: str = None
    tasks_completed: int = 0
    total_time: float = 0  # Sum of all task times
    avg_time_per_task: float = 0
    errors: int = 0
    last_heartbeat: float = None

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

task_lock = threading.Lock()

# GET next task
@app.get("/agent/task/next/{agent_id}")
def get_next_task(agent_id: str):
    """Agent asks: what should I do? (Thread-safe)"""
    
    with task_lock:  # Atomic operation
        if not state.task_queue:
            return {"task": None}
        
        task_id = state.task_queue.pop(0)  # FIFO, but locked
        task = next((t for t in state.tasks if t.id == task_id), None)
        
        if task:
            task.status = "in_progress"
            task.assigned_to = agent_id
            task.start_time = time.time()  # Add timestamp
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
        with task_lock:
            task.status = "done"
            task.result = result
            task.end_time = time.time()
            
            # Update agent metrics
            task_duration = task.end_time - task.start_time
            agent = state.agents[agent_id]
            agent["tasks_completed"] += 1
            agent["total_time"] += task_duration
            agent["avg_time_per_task"] = agent["total_time"] / agent["tasks_completed"]
            agent["status"] = "idle"
            agent["last_heartbeat"] = time.time()
            
            save(state)
            print(f"[DONE] {task_id} by {agent_id} ({task_duration:.1f}s)")
            return {"status": "task completed"}
    
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

@app.post("/agent/heartbeat/{agent_id}")
def heartbeat(agent_id: str, body: dict):
    """Agent sends heartbeat"""
    if agent_id in state.agents:
        state.agents[agent_id]["status"] = body.get("status", "idle")
        state.agents[agent_id]["last_heartbeat"] = time.time()
    return {"status": "heartbeat received"}

@app.get("/state")
def get_state():
    """Peek at current state"""

    return state.model_dump()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)



