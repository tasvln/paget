from openai import OpenAI
import requests
import json
import time

class Agent:
    def __init__(self, agent_id: str, model: str = "qwen2.5-1.5b-instruct-q4_k_m.gguf"):
        self.agent_id = agent_id
        self.model = model
        self.coordinator_url = "http://localhost:8000"
        
        # Use OpenAI SDK for local llama.cpp
        self.client = OpenAI(
            api_key="local-key",
            base_url="http://localhost:8080/v1"
        )
    
    def register(self):
        """Tell coordinator I exist"""
        resp = requests.post(
            f"{self.coordinator_url}/agent/register",
            params={"agent_id": self.agent_id}
        )
        print(f"[{self.agent_id}] Registered: {resp.json()}")
    
    def get_next_task(self):
        """Ask coordinator: what should I do?"""
        resp = requests.get(
            f"{self.coordinator_url}/agent/task/next/{self.agent_id}"
        )
        data = resp.json()
        return data.get("task")
    
    def complete_task(self, task_id: str, result: str):
        """Tell coordinator: I finished"""
        requests.post(
            f"{self.coordinator_url}/agent/task/complete/{self.agent_id}",
            params={"task_id": task_id},
            json={"result": result}
        )
        print(f"[{self.agent_id}] Completed task {task_id}")
    
    def run(self):
        """Main loop: get task, do work, report back"""
        self.register()
        
        while True:
            task = self.get_next_task()
            
            if not task:
                print(f"[{self.agent_id}] No tasks available, waiting...")
                time.sleep(5)
                continue
            
            print(f"[{self.agent_id}] Got task: {task['description']}")
            
            # Call local LLM via OpenAI SDK
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": task["description"]
                }],
                max_tokens=512
            )
            
            result = response.choices[0].message.content
            print(f"[{self.agent_id}] Result: {result[:100]}...")
            
            self.complete_task(task["id"], result)
            time.sleep(1)

if __name__ == "__main__":
    import sys
    
    agent_id = sys.argv[1] if len(sys.argv) > 1 else "agent-1"
    model = sys.argv[2] if len(sys.argv) > 2 else "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    
    agent = Agent(agent_id, model)
    agent.run()