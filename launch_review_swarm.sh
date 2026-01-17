#!/bin/bash
# Launch parallel documentation review swarm

set -e

NUM_AGENTS=${1:-4}

echo "============================================================"
echo "Launching Documentation Review Swarm"
echo "============================================================"
echo ""
echo "Configuration:"
echo "  Number of agents: $NUM_AGENTS"
echo "  Prompt file: .subagent_prompt.md"
echo "  Lock directory: docs/.locks"
echo ""

# Check prerequisites
if [ ! -f ".subagent_prompt.md" ]; then
    echo "ERROR: .subagent_prompt.md not found"
    echo "This file should contain the review instructions"
    exit 1
fi

if [ ! -f "subagent_worker.py" ]; then
    echo "ERROR: subagent_worker.py not found"
    exit 1
fi

if [ ! -f "subagent_coordinator.py" ]; then
    echo "ERROR: subagent_coordinator.py not found"
    exit 1
fi

# Run coordinator with specified number of agents
python subagent_coordinator.py --agents "$NUM_AGENTS"
