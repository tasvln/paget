#!/bin/bash

# chmod +x spawn_agents.sh
# spawn_agents.sh - Spawn N agents easily

AGENT_COUNT=${1:-3}  # Default 3 agents, or pass as argument
MODEL="qwen2.5-coder-3b-instruct.Q4_K_M.gguf"

echo "Spawning $AGENT_COUNT agents..."

for i in $(seq 1 $AGENT_COUNT); do
    echo "Starting agent-$i..."
    python agents/specialist.py agent-$i $MODEL &
    sleep 0.5  # Stagger startup
done

echo "All agents spawned. Press Ctrl+C to stop."
wait