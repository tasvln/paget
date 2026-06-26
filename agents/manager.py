import requests
import json
import time
from pathlib import Path

class ManagerAgent:
    """
    Owns: reading SPEC.json, creating the initial task graph, and reporting
    project status. Does NOT own refinement logic anymore — that's the
    coordinator's job now (see coordinator.py's create_refinement_task),
    which removes the race condition where both this class and the
    coordinator could react to the same failure independently.
    """

    def __init__(self, coordinator_url: str = "http://localhost:8000", spec_file: str = "SPEC.json"):
        self.agent_id = "manager-agent"
        self.coordinator_url = coordinator_url
        self.spec_file = spec_file
        self.spec = None
        self.project_name = None
        self.initialized = False

    def register(self):
        """Register with coordinator"""
        requests.post(
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
        """
        Break SPEC into component tasks. For each component, create:
          1. an "implementation" task (writes the code) — unchanged from before
          2. a "validation" task that depends_on the implementation task and
             carries component_id pointing back at it

        One validation task per component (not one combined end-of-project
        task) is what keeps component_id unambiguous — each validation task
        has exactly one thing it's checking, so a failure routes to exactly
        one refinement target with no special-casing needed in the
        coordinator.
        """
        if not self.spec:
            return False

        print(f"\n[Manager] Decomposing {self.project_name}...")

        try:
            health = requests.get(f"{self.coordinator_url}/", timeout=5)
            print(f"[Manager] Coordinator health: {health.json()}")
        except Exception as e:
            print(f"[Manager] ERROR: Cannot reach coordinator at {self.coordinator_url}")
            print(f"  {e}")
            return False

        for component in self.spec.get('components', []):
            component_name = component['name']
            task_id = f"{self.project_name}-{component_name}"

            req_text = "\n".join(f"  • {r}" for r in component.get('requirements', []))
            description = f"""Build: {component_name}
    Description: {component.get('description', 'N/A')}

    Requirements:
    {req_text}"""

            # 1. implementation task
            try:
                resp = requests.post(
                    f"{self.coordinator_url}/task/create",
                    params={
                        "task_id": task_id,
                        "description": description,
                        "spec_requirements": json.dumps(component.get('requirements', [])),
                        "parent_task": self.project_name,
                        "task_type": "implementation"
                    },
                    timeout=5
                )

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

            # 2. validation task for this component, gated on the
            # implementation task finishing, with component_id pointing
            # back at it so a failure here refines the right thing.
            validate_task_id = f"{task_id}-validate"
            try:
                resp = requests.post(
                    f"{self.coordinator_url}/task/create",
                    params={
                        "task_id": validate_task_id,
                        "description": f"Validate: {component_name}",
                        "depends_on": json.dumps([task_id]),
                        "parent_task": self.project_name,
                        "task_type": "validation",
                        "component_id": task_id
                    },
                    timeout=5
                )

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "task created":
                        print(f"  ✓ Created: {validate_task_id} (validates {task_id})")
                else:
                    print(f"  ✗ {validate_task_id}: HTTP {resp.status_code}")

            except Exception as e:
                print(f"  ✗ {validate_task_id}: {e}")
                continue

        self.initialized = True
        return True

    def get_state(self):
        """Get current coordinator state"""
        resp = requests.get(f"{self.coordinator_url}/state")
        return resp.json()

    def get_project_status(self):
        """Print current project status — read-only reporting, no decisions made here"""
        state = self.get_state()
        tasks = state.get('tasks', [])
        project_tasks = [t for t in tasks if t.get('parent_task') == self.project_name]

        done = sum(1 for t in project_tasks if t['status'] == 'done')
        failed = sum(1 for t in project_tasks if t['status'] == 'failed')
        in_prog = sum(1 for t in project_tasks if t['status'] == 'in_progress')
        pending = sum(1 for t in project_tasks if t['status'] == 'pending')

        print(f"\n[Manager] {self.project_name} status:")
        print(f"  ✓ Done: {done}")
        print(f"  ⚙ In Progress: {in_prog}")
        print(f"  ⏳ Pending: {pending}")
        print(f"  ✗ Failed: {failed}")

        if failed:
            print(f"  → Failed tasks (check validation_errors in /state for file paths):")
            for t in project_tasks:
                if t['status'] == 'failed':
                    print(f"      • {t['id']}")

        if done + failed == len(project_tasks):
            print(f"  → Project complete!")

    def run(self):
        """Main agent loop — decompose once, then just report status periodically"""
        self.register()

        if not self.load_spec():
            print("[Manager] Failed to load SPEC, exiting")
            return

        if not self.decompose_spec():
            print("[Manager] Failed to decompose SPEC, exiting")
            return

        print(f"\n[Manager] Watching project status (no auto-refinement here — coordinator handles that)...")

        loop_count = 0
        while True:
            loop_count += 1

            if loop_count % 10 == 0:
                self.get_project_status()

            time.sleep(5)

if __name__ == "__main__":
    import sys

    spec_file = sys.argv[1] if len(sys.argv) > 1 else "SPEC.json"
    manager = ManagerAgent(spec_file=spec_file)
    manager.run()