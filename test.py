import requests
import time
import json

coordinator = "http://localhost:8000"

# Create 5 tasks
tasks = [
    "Write a full Python function that returns the first 10 Fibonacci numbers.",
    "Write a full function that checks if a string is a palindrome.",
    "Write a full function that merges two sorted lists into one sorted list.",
    "Write a full function that calculates the factorial of a number.",
    "Write a full function that finds the most common element in a list.",
]

print("Creating 5 tasks...")
for i, description in enumerate(tasks, 1):
    task_id = f"task-{i}"
    resp = requests.post(
        f"{coordinator}/task/create",
        params={"task_id": task_id, "description": description}
    )
    print(f"  Created {task_id}: {description[:50]}...")

print("\nWaiting for agents to complete tasks...")

# Monitor for 120 seconds
for second in range(120):
    time.sleep(1)
    state = requests.get(f"{coordinator}/state").json()
    
    done_count = sum(1 for t in state["tasks"] if t["status"] == "done")
    in_progress = sum(1 for t in state["tasks"] if t["status"] == "in_progress")
    pending = sum(1 for t in state["tasks"] if t["status"] == "pending")
    
    print(f"[{second}s] Done: {done_count}/5 | In Progress: {in_progress} | Pending: {pending} | Agents: {len(state['agents'])}")
    
    if done_count == 5:
        print("\n✓ All tasks completed!")
        break

# Show final state
print("\n=== FINAL STATE ===")
state = requests.get(f"{coordinator}/state").json()
print(json.dumps(state, indent=2))