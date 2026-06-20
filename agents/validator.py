import requests
import json
import subprocess
import time

class TestAgent:
    def __init__(self, coordinator_url: str = "http://localhost:8000"):
        self.coordinator_url = coordinator_url
        self.agent_id = "test-agent"
        self.spec = None
    
    def register(self):
        """Register with coordinator"""
        requests.post(
            f"{self.coordinator_url}/agent/register",
            params={"agent_id": self.agent_id}
        )
        print(f"[TestAgent] Registered")
    
    def load_spec(self, spec_file: str):
        """Load SPEC.json"""
        with open(spec_file) as f:
            self.spec = json.load(f)
    
    def validate_output(self, output_dir: str):
        """Run tests from SPEC.json"""
        errors = []
        
        print(f"\n[TestAgent] Validating output in {output_dir}")
        
        for test in self.spec.get('tests', []):
            print(f"  Running: {test['name']}")
            try:
                # Run the test command
                result = subprocess.run(
                    test['command'],
                    cwd=output_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                # Check if output matches expected
                if test['expected_output'] in result.stdout or result.returncode == 0:
                    print(f"    ✓ PASS")
                else:
                    error = f"{test['name']}: Expected '{test['expected_output']}' in output"
                    errors.append(error)
                    print(f"    ✗ FAIL: {error}")
            except Exception as e:
                error = f"{test['name']}: {str(e)}"
                errors.append(error)
                print(f"    ✗ ERROR: {error}")
        
        return errors
    
    def get_next_test_task(self):
        """Get a test task from coordinator"""
        resp = requests.get(
            f"{self.coordinator_url}/agent/task/next/{self.agent_id}"
        )
        return resp.json().get("task")
    
    def complete_task(self, task_id: str, result: str, validation_errors: list = None):
        """Report task completion"""
        requests.post(
            f"{self.coordinator_url}/agent/task/complete/{self.agent_id}",
            params={"task_id": task_id},
            json={"result": result, "validation_errors": validation_errors or []}
        )
        print(f"[TestAgent] Completed {task_id}")
    
    def run(self):
        """Main loop"""
        self.register()
        self.load_spec("SPEC.json")
        
        while True:
            task = self.get_next_test_task()
            if not task:
                print("[TestAgent] No test tasks available, waiting...")
                time.sleep(5)
                continue
            
            print(f"[TestAgent] Got task: {task['id']}")
            
            # Validate output
            errors = self.validate_output("./output")
            
            if errors:
                # Tests failed - mark as failed, agents will retry
                self.complete_task(
                    task['id'],
                    f"Validation failed with {len(errors)} errors",
                    errors
                )
                print(f"[TestAgent] ✗ Validation FAILED - Agents should refine")
            else:
                # All tests passed!
                self.complete_task(
                    task['id'],
                    "All validation tests passed!",
                    []
                )
                print(f"[TestAgent] ✓ Validation PASSED")

if __name__ == "__main__":
    agent = TestAgent()
    agent.run()