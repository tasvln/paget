from openai import OpenAI
import requests
import json
import time
from pathlib import Path

class SpecialistAgent:
    def __init__(self, agent_id: str, model: str = "qwen2.5-1.5b-instruct-q4_k_m.gguf"):
        self.agent_id = agent_id
        self.model = model
        self.coordinator_url = "http://localhost:8000"

        self.client = OpenAI(
            api_key="local-key",
            base_url="http://localhost:8080/v1"
        )

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
            params={"task_type": "implementation"}
        )
        return resp.json().get("task")

    def build_system_prompt(self, task):
        role = task.get('role', 'general')
        requirements = task.get('spec_requirements', [])
        constraints = task.get('agent_constraints', [])

        req_text = "\n".join(f"  • {r}" for r in requirements) if requirements else "None specified"
        const_text = "\n".join(f"  • {c}" for c in constraints) if constraints else "None specified"

        return f"""You are a {role}.

                {task['description']}

                Requirements:
                {req_text}

                Constraints:
                {const_text}

                Provide production-ready code."""

    def generate_code(self, task):
        system_prompt = self.build_system_prompt(task)

        # task_type/component_id don't change generation behavior — a
        # refinement task is still task_type="implementation", just with
        # feedback already folded into task['description'] by the
        # coordinator. Nothing here needs to branch on it.
        print(f"[{self.agent_id}] Generating for: {task['id']} (role: {task.get('role', 'general')})")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task["description"]}
            ],
            max_tokens=2048,
            temperature=0.7
        )

        return response.choices[0].message.content

    def extract_code(self, response):
        if "```python" in response:
            code = response.split("```python")[1].split("```")[0].strip()
        elif "```" in response:
            code = response.split("```")[1].split("```")[0].strip()
        else:
            code = response.strip()

        return code

    def validate_code(self, code):
        """
        First-pass, cheap filter — only checks the code is syntactically
        valid Python. This deliberately does NOT make this task "validated"
        in the project sense; validator.py runs the same check again,
        independently, against the saved file. Two reasons to keep both:
        this catches a bad response before wasting a disk write, and
        validator.py catches cases where something corrupts the file
        between save and validation, or where you want validation decoupled
        from the agent that wrote the code in the first place.
        """
        try:
            compile(code, '<string>', 'exec')
            return True, "Syntax valid"
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        except Exception as e:
            return False, f"Error: {e}"

    def save_code(self, task_id: str, code: str, component_name: str = None):
        """
        Saves to output/<component_name>.py directly — flat, no per-component
        subfolder. Since refinement reuses the same component_name across
        retries (see component_name_for), this naturally overwrites the
        same file each time rather than accumulating -refine-v1, -refine-v2
        copies. component_name should always be set now (manager.py always
        creates tasks with clean ids); task_id fallback kept only for safety.
        """

        PROJECT_ROOT = Path(__file__).resolve().parent.parent

        output_dir = PROJECT_ROOT / "output"
        output_dir.mkdir(exist_ok=True)

        name = component_name or task_id
        file_path = output_dir / f"{name}.py"

        file_path.write_text(code)
        print(f"[{self.agent_id}] Saved: {file_path}")

        return str(file_path)

    def complete_task(self, task_id: str, result: str, validation_errors: list = None):
        requests.post(
            f"{self.coordinator_url}/agent/task/complete/{self.agent_id}",
            params={"task_id": task_id},
            json={"result": result, "validation_errors": validation_errors or []}
        )
        print(f"[{self.agent_id}] Completed: {task_id}")

    def component_name_for(self, task: dict) -> str:
        """
        Derive the output folder/file name for a task. This MUST match
        what validator.py looks up, since manager.py sets the validation
        task's component_id to the implementation task's full id (e.g.
        'calc-adder', not a split fragment like 'adder'). Using anything
        else here (the old code used task_id.split('-')[1]) causes every
        validation to report a false "file not found" — confirmed via a
        live run where specialist saved to output/adder/ while validator
        looked in output/calc-adder/.

        For a refinement task (id like 'calc-adder-refine-v1'),
        component_id is set by the coordinator to the ORIGINAL task's id
        ('calc-adder') — using that here means refined code overwrites the
        same file instead of creating a new '...-refine-v1' folder.
        """
        if task.get("component_id"):
            return task["component_id"]
        return task["id"]

    def run(self):
        self.register()
        self.update_status("idle")

        print(f"[{self.agent_id}] Ready. Waiting for tasks...")

        while True:
            task = self.get_next_task()

            if not task:
                time.sleep(5)
                continue

            task_id = task['id']
            print(f"\n[{self.agent_id}] Got task: {task_id}")

            self.update_status("working", task_id)

            try:
                response = self.generate_code(task)
                code = self.extract_code(response)

                is_valid, msg = self.validate_code(code)
                if not is_valid:
                    print(f"[{self.agent_id}] ✗ {msg}")
                    self.complete_task(task_id, response, [msg])
                    self.update_status("idle")
                    continue

                print(f"[{self.agent_id}] ✓ Valid")

                component_name = self.component_name_for(task)
                self.save_code(task_id, code, component_name)

                self.complete_task(task_id, code, [])

            except Exception as e:
                print(f"[{self.agent_id}] ✗ {str(e)}")
                self.complete_task(task_id, str(e), [f"Exception: {str(e)}"])

            self.update_status("idle")
            time.sleep(1)

if __name__ == "__main__":
    import sys

    agent_id = sys.argv[1] if len(sys.argv) > 1 else "agent-1"
    model = sys.argv[2] if len(sys.argv) > 2 else "qwen2.5-1.5b-instruct-q4_k_m.gguf"

    agent = SpecialistAgent(agent_id, model)
    agent.run()