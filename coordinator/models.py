from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Union
import time

class Task(BaseModel):
    id: str
    description: str
    status: str = "pending"  # pending, in_progress, done, failed
    assigned_to: str = ""
    result: str = ""

    # Spec & validation
    spec_requirements: Union[List[str], Dict] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)

    # Retry logic
    retry_count: int = 0
    max_retries: int = 3

    # Dependencies
    parent_task: Optional[str] = None
    depends_on: List[str] = Field(default_factory=list)

    # Task typing + component linkage
    # "implementation" = write code (the only kind that existed before).
    # "validation" = check an implementation task's output. When a
    # validation task fails, refinement targets component_id, not itself.
    task_type: str = "implementation"
    component_id: Optional[str] = None

    # Set once on the FIRST refinement and never touched again. Lets
    # create_refinement_task build "Refine: <original first line>" on every
    # retry without re-deriving it from the (by-then-overwritten)
    # description, which was causing "Refine: Refine: Refine: " nesting
    # across repeated retries — confirmed in a live run with 3 retries.
    original_description: Optional[str] = None

    # Timestamps
    created_at: float = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.created_at is None:
            self.created_at = time.time()

class Agent(BaseModel):
    agent_id: str
    status: str = "idle"  # idle, working, error
    current_task: Optional[str] = None
    tasks_completed: int = 0
    total_time: float = 0
    avg_time_per_task: float = 0
    errors: int = 0
    last_update: float = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.last_update is None:
            self.last_update = time.time()

class ManagerState(BaseModel):
    project_name: str = "untitled"
    agents: Dict[str, Agent] = Field(default_factory=dict)
    tasks: List[Task] = Field(default_factory=list)
    task_queue: List[str] = Field(default_factory=list)

    def get_agent(self, agent_id: str) -> Agent:
        """Get or create agent"""
        if agent_id not in self.agents:
            self.agents[agent_id] = Agent(agent_id=agent_id, status="idle", last_update=time.time())
        return self.agents[agent_id]

    def get_task(self, task_id: str) -> Optional[Task]:
        """Convenience lookup used throughout the coordinator"""
        return next((t for t in self.tasks if t.id == task_id), None)