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
        resp = requests.post(
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
            f"{self.coordinator_url}/agent/task/next/{self.agent_id}"
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
        try:
            compile(code, '<string>', 'exec')
            return True, "Syntax valid"
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        except Exception as e:
            return False, f"Error: {e}"
    
    def save_code(self, task_id: str, code: str, component_name: str = None):
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        if component_name:
            component_dir = output_dir / component_name
            component_dir.mkdir(exist_ok=True)
            file_path = component_dir / f"{component_name}.py"
        else:
            file_path = output_dir / f"{task_id}.py"
        
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
                
                component_name = task_id.split('-')[1] if '-' in task_id else task_id
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