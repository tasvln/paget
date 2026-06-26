import requests
import time
from pathlib import Path

class ValidatorAgent:
    """
    Runs a "validation" task: an independent, second-pass check that a
    component's saved code is real, runnable Python — not whether its logic
    is correct. No LLM involved here; this is purely mechanical, which is
    the point — it's a check on whether the specialist produced actual code
    versus prose/a truncated response/markdown leftovers, done by something
    other than the agent grading its own work.

    If the person has written their own test file alongside a component
    (output/<component>/test_<component>.py), it gets run too. If it
    doesn't exist, that step is silently skipped — this is the hook for
    "the user can add test code themselves" without the validator ever
    generating tests on its own.

    On failure, this just reports validation_errors back through the
    existing /agent/task/complete endpoint. The coordinator already knows
    how to turn that into a refinement task pointed at component_id — see
    coordinator.py's complete_task. This file doesn't create refinement
    tasks itself and doesn't talk to a manager; it only flags and stops.
    """

    def __init__(self, agent_id: str = "validator-1", output_dir: str = "output"):
        PROJECT_ROOT = Path(__file__).resolve().parent.parent
        
        self.agent_id = agent_id
        self.coordinator_url = "http://localhost:8000"
        self.output_dir = PROJECT_ROOT / "output"

    # ------------------------------------------------------------------
    # coordinator plumbing — same shape as specialist.py
    # ------------------------------------------------------------------
    def register(self):
        requests.post(
            f"{self.coordinator_url}/agent/register",
            params={"agent_id": self.agent_id}
        )
        print(f"[{self.agent_id}] Registered")

    def update_status(self, status: str, current_task: str = None):
        requests.post(
            f"{self.coordinator_url}/agent/status/{self.agent_id}",
            json={"status": status, "current_task": current_task}
        )

    def get_next_task(self):
        resp = requests.get(
            f"{self.coordinator_url}/agent/task/next/{self.agent_id}",
            params={"task_type": "validation"}
        )
        return resp.json().get("task")

    def complete_task(self, task_id: str, result: str, validation_errors: list = None):
        requests.post(
            f"{self.coordinator_url}/agent/task/complete/{self.agent_id}",
            params={"task_id": task_id},
            json={"result": result, "validation_errors": validation_errors or []}
        )
        print(f"[{self.agent_id}] Completed: {task_id}")

    # ------------------------------------------------------------------
    # the actual check
    # ------------------------------------------------------------------
    def component_file(self, component_id: str) -> Path:
        return self.output_dir / f"{component_id}.py"

    def optional_test_file(self, component_id: str) -> Path:
        return self.output_dir / f"test_{component_id}.py"

    def check_component(self, component_id: str) -> tuple[bool, list[str]]:
        """
        Returns (passed, errors). errors is empty on success. Every error
        string includes the file path so whoever reads validation_errors
        later (you, or a refinement prompt) knows exactly what to open.
        """
        file_path = self.component_file(component_id)
        errors = []

        if not file_path.exists():
            return False, [f"{file_path}: file not found — component was never saved"]

        code = file_path.read_text()

        # Step 1: is this even valid Python at all?
        try:
            compiled = compile(code, str(file_path), 'exec')
        except SyntaxError as e:
            return False, [f"{file_path}: SyntaxError: {e}"]
        except Exception as e:
            return False, [f"{file_path}: {type(e).__name__}: {e}"]

        # Step 2: does it actually run as a module (catches import errors,
        # NameErrors from undefined references, etc. — things compile()
        # alone won't catch since compile() only builds the AST).
        namespace = {}
        try:
            exec(compiled, namespace)
        except Exception as e:
            return False, [f"{file_path}: raised {type(e).__name__} on execution: {e}"]

        # Step 3: optional, user-authored test file — only if present.
        test_path = self.optional_test_file(component_id)
        if test_path.exists():
            test_code = test_path.read_text()
            try:
                test_compiled = compile(test_code, str(test_path), 'exec')
            except SyntaxError as e:
                return False, [f"{test_path}: SyntaxError: {e}"]

            # Give the test file access to whatever the component defined,
            # the same way a normal `from component import *` would.
            test_namespace = dict(namespace)
            try:
                exec(test_compiled, test_namespace)
            except Exception as e:
                return False, [f"{test_path}: raised {type(e).__name__}: {e}"]

        return True, errors

    # ------------------------------------------------------------------
    # main loop — identical shape to specialist.py's run()
    # ------------------------------------------------------------------
    def run(self):
        self.register()
        self.update_status("idle")
        print(f"[{self.agent_id}] Ready. Waiting for validation tasks...")

        while True:
            task = self.get_next_task()

            if not task:
                time.sleep(5)
                continue

            task_id = task['id']
            component_id = task.get('component_id') or task_id
            print(f"\n[{self.agent_id}] Validating: {component_id} (task: {task_id})")

            self.update_status("working", task_id)

            try:
                passed, errors = self.check_component(component_id)

                if passed:
                    print(f"[{self.agent_id}] ✓ {component_id} runs cleanly")
                    self.complete_task(task_id, f"{component_id} validated successfully", [])
                else:
                    print(f"[{self.agent_id}] ✗ {component_id} failed: {errors}")
                    self.complete_task(task_id, "", errors)

            except Exception as e:
                print(f"[{self.agent_id}] ✗ unexpected error: {e}")
                self.complete_task(task_id, "", [f"Validator exception: {e}"])

            self.update_status("idle")
            time.sleep(1)


if __name__ == "__main__":
    import sys
    agent_id = sys.argv[1] if len(sys.argv) > 1 else "validator-1"
    agent = ValidatorAgent(agent_id)
    agent.run()