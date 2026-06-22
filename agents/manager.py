import requests
import json
import time
from pathlib import Path

class ManagerAgent:
    def __init__(self, coordinator_url: str = "http://localhost:8000", spec_file: str = "SPEC.json"):
        self.agent_id = "manager-agent"
        self.coordinator_url = coordinator_url
        self.spec_file = spec_file
        self.spec = None
        self.project_name = None
        self.initialized = False
    
    def register(self):
        """Register with coordinator"""
        resp = requests.post(
            f"{self.coordinator_url}/agent/register",
            params={"agent_id": self.agent_id}
        )
        print(f"[Manager] Registered")
    
    def load_spec(self):
        """Load SPEC.json"""
        if not Path(self.spec_file).exists():
            print(f"[Manager] SPEC.json not found at {self.spec_file}")
            return False
        
        with open(self.spec_file) as f:
            self.spec = json.load(f)
        
        self.project_name = self.spec.get("project", "untitled")
        print(f"[Manager] Loaded spec: {self.project_name}")
        print(f"[Manager] Goal: {self.spec.get('high_level_goal', 'N/A')}")
        return True
    
    def decompose_spec(self):
        """Break SPEC into component tasks"""
        if not self.spec:
            return False
        
        print(f"\n[Manager] Decomposing {self.project_name}...")
        
        # First, check if coordinator is alive
        try:
            health = requests.get(f"{self.coordinator_url}/", timeout=5)
            print(f"[Manager] Coordinator health: {health.json()}")
        except Exception as e:
            print(f"[Manager] ERROR: Cannot reach coordinator at {self.coordinator_url}")
            print(f"  {e}")
            return False
        
        # Create task for each component
        component_task_ids = []
        
        for component in self.spec.get('components', []):
            task_id = f"{self.project_name}-{component['name']}"
            component_task_ids.append(task_id)
            
            # Build description with requirements
            req_text = "\n".join(f"  • {r}" for r in component.get('requirements', []))
            description = f"""Build: {component['name']} Description: {component.get('description', 'N/A')} Requirements: {req_text}"""
            
            # Create task
            try:
                resp = requests.post(
                    f"{self.coordinator_url}/task/create",
                    params={
                        "task_id": task_id,
                        "description": description,
                        "spec_requirements": json.dumps(component.get('requirements', [])),
                        "parent_task": self.project_name
                    },
                    timeout=5
                )
                
                # Check response status
                if resp.status_code != 200:
                    print(f"  ✗ {task_id}: HTTP {resp.status_code}")
                    print(f"    Response: {resp.text}")
                    continue
                
                data = resp.json()
                if data.get("status") == "task created":
                    print(f"  ✓ Created: {task_id}")
                else:
                    print(f"  ! {task_id}: {data.get('status')}")
            
            except requests.exceptions.ConnectionError:
                print(f"  ✗ Connection error: Cannot reach coordinator")
                return False
            except Exception as e:
                print(f"  ✗ {task_id}: {e}")
                continue
        
        # Create test task (depends on all components)
        test_task_id = f"{self.project_name}-test"
        test_description = f"""Validate {self.project_name} Run all validation checks: {chr(10).join(f"  • {t['name']}: {t.get('command', 'manual')}" for t in self.spec.get('tests', []))}"""
        
        try:
            resp = requests.post(
                f"{self.coordinator_url}/task/create",
                params={
                    "task_id": test_task_id,
                    "description": test_description,
                    "depends_on": json.dumps(component_task_ids),
                    "parent_task": self.project_name
                },
                timeout=5
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "task created":
                    print(f"  ✓ Created: {test_task_id} (depends on {len(component_task_ids)} components)")
            else:
                print(f"  ✗ Test task: HTTP {resp.status_code}")
        
        except Exception as e:
            print(f"  ✗ Test task error: {e}")
        
        self.initialized = True
        return True

    def get_state(self):
        """Get current coordinator state"""
        resp = requests.get(f"{self.coordinator_url}/state")
        return resp.json()
    
    def get_project_status(self):
        """Print current project status"""
        state = self.get_state()
        tasks = state.get('tasks', [])
        project_tasks = [t for t in tasks if t.get('parent_task') == self.project_name]
        
        done = sum(1 for t in project_tasks if t['status'] == 'done')
        failed = sum(1 for t in project_tasks if t['status'] == 'failed')
        in_prog = sum(1 for t in project_tasks if t['status'] == 'in_progress')
        pending = sum(1 for t in project_tasks if t['status'] == 'pending')
        
        print(f"\n[Manager] {self.project_name} status:")
        print(f"  Done: {done}")
        print(f"  In Progress: {in_prog}")
        print(f"  Pending: {pending}")
        print(f"  Failed: {failed}")
        
        if done + failed == len(project_tasks):
            print(f"  → Project complete!")
    
    def run(self):
        """Main agent loop"""
        self.register()
        
        # Load and decompose SPEC on startup
        if not self.load_spec():
            print("[Manager] Failed to load SPEC, exiting")
            return
        
        if not self.decompose_spec():
            print("[Manager] Failed to decompose SPEC, exiting")
            return
        
        print(f"\n[Manager] Starting supervision loop...")
        
        # Main loop: monitor for failures and refine
        loop_count = 0
        while True:
            loop_count += 1
            
            if loop_count % 10 == 0:  # Print status every 10 loops
                self.get_project_status()
            
            # Check for failed tasks and create refinements
            # self.monitor_and_refine()
            
            # Wait before next check
            time.sleep(5)

if __name__ == "__main__":
    import sys
    
    spec_file = sys.argv[1] if len(sys.argv) > 1 else "SPEC.json"
    manager = ManagerAgent(spec_file=spec_file)
    manager.run()