from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Union
import time

# 1. TASK - Work unit
class Task(BaseModel):
    id: str
    description: str
    status: str = "pending"  # pending, in_progress, done, failed
    assigned_to: str = ""
    result: str = ""
    
    # Spec & validation
    spec_requirements: Union[List[str], Dict] = []  # Accept list or dict
    validation_errors: List[str] = []
    
    # Retry logic
    retry_count: int = 0
    max_retries: int = 3
    
    # Dependencies
    parent_task: Optional[str] = None
    depends_on: List[str] = []
    
    # Timestamps
    created_at: float = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        if self.created_at is None:
            self.created_at = time.time()


# 2. AGENT - Specialist agent tracking
class Agent(BaseModel):
    agent_id: str
    status: str = "idle"  # ADD DEFAULT: idle, working, error
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


# 3. MANAGER - Coordinator State
class ManagerState(BaseModel):
    project_name: str = "untitled"
    agents: Dict[str, Agent] = {}
    tasks: List[Task] = []
    task_queue: List[str] = []
    
    def get_agent(self, agent_id: str) -> Agent:
        """Get or create agent"""
        if agent_id not in self.agents:
            self.agents[agent_id] = Agent(agent_id=agent_id, status="idle", last_update=time.time())
        return self.agents[agent_id]