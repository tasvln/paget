import requests
import time
import json

manager = "http://localhost:8000"

# Create a task
# task_id = "task-2"
# description = "Write a full Python function that returns the first 10 Fibonacci numbers. Return the code as plain text."

# resp = requests.post(
#     f"{manager}/task/create",
#     params={"task_id": task_id, "description": description}
# )
# print(f"Created task: {resp.json()}")

# # Wait for agent to pick it up and complete it
# for i in range(60):  # Try for 60 seconds
#     time.sleep(1)
#     state = requests.get(f"{manager}/state").json()
    
#     task = next((t for t in state["tasks"] if t["id"] == task_id), None)
#     if task and task["status"] == "done":
#         print(f"\n✓ Task completed!")
#         print(f"Result:\n{task['result']}")
#         break
#     else:
#         print(f"  [{i}s] Task status: {task['status'] if task else 'not found'}")

# # Print final state
# print("\n=== FINAL STATE ===")
# state = requests.get(f"{manager}/state").json()
# print(json.dumps(state, indent=2))

# create multiple tasks

for i in range(5):
    task_id = f"task-{i}"
    description = f"Write a Python function that returns the first {i+5} Fibonacci numbers. Return the code as plain text."

    resp = requests.post(
        f"{manager}/task/create",
        params={"task_id": task_id, "description": description}
    )
    print(f"Created task: {resp.json()}")

for i in range(60):  # Try for 60 seconds
    time.sleep(1)
    state = requests.get(f"{manager}/state").json()
    
    completed_tasks = [t for t in state["tasks"] if t["status"] == "done"]
    print(f"  [{i}s] Completed tasks: {len(completed_tasks)}/{len(state['tasks'])}")
    
    if len(completed_tasks) == len(state["tasks"]):
        print("\n✓ All tasks completed!")
        break

# Print final state
print("\n=== FINAL STATE ===")
state = requests.get(f"{manager}/state").json()
print(json.dumps(state, indent=2))
