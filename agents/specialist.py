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
    
    def get_next_task(self):
        resp = requests.get(
            f"{self.coordinator_url}/agent/task/next/{self.agent_id}"
        )
        return resp.json().get("task")
    
    def complete_task(self, task_id: str, result: str):
        requests.post(
            f"{self.coordinator_url}/agent/task/complete/{self.agent_id}",
            params={"task_id": task_id},
            json={"result": result}
        )
        print(f"[{self.agent_id}] Completed {task_id}")
    
    def save_code_to_output(self, filename: str, code: str):
        """Write generated code to output directory"""
        output_dir = Path("./output")
        output_dir.mkdir(exist_ok=True)
        
        file_path = output_dir / filename
        file_path.write_text(code)
        print(f"[{self.agent_id}] Saved: {filename}")
    
    def run(self):
        self.register()
        
        while True:
            task = self.get_next_task()
            
            if not task:
                print(f"[{self.agent_id}] No tasks, waiting...")
                time.sleep(5)
                continue
            
            print(f"[{self.agent_id}] Got task: {task['id']}")
            
            # Call LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": task["description"]
                }],
                max_tokens=2048
            )
            
            result = response.choices[0].message.content
            print(f"[{self.agent_id}] Generated code ({len(result)} chars)")
            
            # Save to output
            filename = f"{task['id']}.py"
            self.save_code_to_output(filename, result)
            
            self.complete_task(task["id"], result)
            time.sleep(1)

if __name__ == "__main__":
    import sys
    agent_id = sys.argv[1] if len(sys.argv) > 1 else "agent-1"
    agent = SpecialistAgent(agent_id)
    agent.run()