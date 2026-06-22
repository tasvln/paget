User Input: "Build a flight simulator game"
    ↓
[Manager Agent]
  - Breaks down into subtasks:
    • Task: "Graphics rendering system"
    • Task: "Physics engine" 
    • Task: "Input/controls system"
    • Task: "UI system"
    ↓
[Specialist Agents] (different agents/models per domain)
  Agent-Graphics (Claude) → Writes rendering code
  Agent-Physics (Claude) → Writes physics code
  Agent-UI (Mistral) → Writes UI code
    ↓
[Refinement Agents]
  Agent-Optimizer → Makes code efficient
  Agent-Security → Checks for vulnerabilities
    ↓
[Test Agent]
  Validates against SPEC.json:
  {
    "requirements": ["60 FPS", "3D rendering", "realistic physics"],
    "tests": [
      {"name": "fps_test", "expected": ">= 60"},
      {"name": "physics_test", "check": "gravity == 9.8"}
    ],
    "quality": {"coverage": ">= 80%", "type_hints": true}
  }
    ↓
  ✓ Pass → Output complete code
  ✗ Fail → Re-delegate to agents for refinement
    ↓
[Final Output]
  /output/
    ├── flight_simulator.py
    ├── tests/
    ├── SPEC.json (the contract)
    └── BUILD_LOG.json (what agents did)

------------------------------------------------------------

[VSCode Plugin] → [Claude Agent] → [Code Generator] → [Test Agent] → [Output]
       ↓              ↓                  ↓              ↓           ↓
    Node            Node              Node           Node         Node
    
Drag-and-drop to connect. Click to configure. 
Plug in Blender, Unity, Figma, etc. as nodes.
Target: Mac, Windows, Web, Mobile

-------------------------------------------------------------

┌─ COORDINATOR (FastAPI app)
│  - Stores state
│  - Routes requests
│  - Orchestrates flow
│
├─ MANAGER AGENT (running agent)
│  - Reads SPEC.json → decomposes into tasks
│  - Sends to specialists
│  - Gets test failures back
│  - Creates REFINEMENT tasks intelligently
│  - Loops until tests pass
│
├─ SPECIALIST AGENTS (running agents)
│  - Do actual work
│  - AWARE of what they're building (task description + spec)
│  - Report results
│
└─ TEST AGENT (running agent)
   - Validates specialist output
   - Reports errors back to manager
   - "These components failed validation: X, Y, Z"

[Manager] splits SPEC → tasks
    ↓
[Specialists] build → results
    ↓
[Tester] validates → errors?
    ↓
If errors → [Manager] reads them → creates refinement tasks
    ↓
[Specialists] refine → results
    ↓
[Tester] validates → pass?
    ↓
Loop until pass
    ↓
Output complete

---------------------------------------------------------

COORDINATOR (server.py)
├─ Stores state (tasks, agents, queue)
├─ Routes requests
└─ Orchestrates flow

MANAGER AGENT (manager.py)
├─ Reads SPEC.json
├─ Decomposes into tasks
├─ Calls /task/create on coordinator
└─ Monitors for failures 

SPECIALIST AGENTS (specialist.py) - Multiple instances
├─ Calls /agent/register
├─ Polls /agent/task/next
├─ Generates code (with role-based prompts)
├─ Calls /agent/task/complete
└─ Reports status with /agent/status


----------------------------------------

Coordinator
    ├── State
    ├── Queue
    ├── Dependencies
    └── Retry/Refinement

Manager
    ├── Read SPEC
    ├── Create Tasks
    └── Report Progress

SpecialistAgent
    └── Generate Code

ValidationAgent
    ├── Generate Tests
    ├── Run Tests
    ├── Produce Structured Failures
    └── Trigger Refinement Through Coordinator