import requests
import time
import json

coordinator = "http://localhost:8000"

# Create 5 tasks
tasks = [
    "Write a Python function that returns the first 10 Fibonacci numbers.",
    "Write a function that checks if a string is a palindrome.",
    "Write a function that merges two sorted lists into one sorted list.",
    "Write a function that calculates the factorial of a number.",
    "Write a function that finds the most common element in a list.",
]

print("Creating 5 tasks...")
for i, description in enumerate(tasks, 1):
    task_id = f"task-{i}"
    requests.post(
        f"{coordinator}/task/create",
        params={"task_id": task_id, "description": description}
    )

print("\nWaiting for agents to complete tasks...\n")

for second in range(120):
    time.sleep(1)
    state = requests.get(f"{coordinator}/state").json()
    
    done = sum(1 for t in state["tasks"] if t["status"] == "done")
    in_prog = sum(1 for t in state["tasks"] if t["status"] == "in_progress")
    pending = sum(1 for t in state["tasks"] if t["status"] == "pending")
    
    # Agent status line
    agent_status = " | ".join([
        f"{aid}: {a['status']} ({a['tasks_completed']} done, {a.get('avg_time_per_task', 0):.1f}s avg)"
        for aid, a in state["agents"].items()
    ])
    
    print(f"[{second:3d}s] Tasks: {done}/5 done, {in_prog} working, {pending} pending | {agent_status}")
    
    if done == 5:
        print("\n✓ All tasks completed!")
        break

# Final summary
# print("\n=== FINAL METRICS ===")
# state = requests.get(f"{coordinator}/state").json()
# for agent_id, agent_data in state["agents"].items():
#     print(f"{agent_id}: {agent_data['tasks_completed']} tasks, {agent_data['avg_time_per_task']:.1f}s avg")