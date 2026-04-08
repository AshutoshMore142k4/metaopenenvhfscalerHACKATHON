---
title: Bug Triage SRE Env
emoji: 🐛
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# OpenEnv SRE Bug Triage Benchmark
## Motivation
This environment models a **production-grade engineering and support workflow**. Teams spend countless hours reading vague bug reports, matching them to stack traces, assessing priority, and routing them to the correct group. This interactive environment evaluates whether LLM agents can act like real Site Reliability Engineers (SREs), using **tools** to deduce root causes before making final resolutions.

## Environment Design (The "WOW" Factor)
Unlike simple text classification environments, the **SRE Bug Triage Benchmark** forces the agent into an iterative ReAct pattern where they must actively query pseudo-systems to uncover full state context.

### The Observation Space
Agents receive strongly-typed JSON representing the current state:
```json
{
  "ticket_description": "User reported slow performance during checkout.",
  "command_result": "Logs for database: OutOfMemory errors detected in pgsql pool",
  "step_count": 2
}
```

### The Action Space
Agents must output strict JSON commanding the environment:
```json
{
  "command": "search_logs", 
  "command_args": {"service": "database"}
}
```
Supported commands:
- `search_logs`
- `query_metrics`
- `resolve_ticket`

## Progressive Task Breakdown
There are 3 tasks designed to test varying difficulties and tool horizons:
- **Task 1 (Easy)**: Severity assessment directly from the ticket description.
- **Task 2 (Medium - Log Investigation)**: The agent receives a vague ticket. It must invoke `search_logs` to uncover hidden errors, then `resolve_ticket`. Partial rewards are awarded for searching the right log!
- **Task 3 (Hard - Escalation & Metrics)**: The agent must correlate metrics and logs across different services to find hidden latency sources and map it to the right on-call team.

## Baseline Results
| Task | Difficulty | Expected Baseline Score |
| ---- | ---------- | ----------------------------- |
| 1    | Easy       | 1.0  |
| 2    | Medium     | 0.8  |
| 3    | Hard       | 0.6  |

## Execution Instructions

Run the OpenEnv server:
```bash
docker build -t openenv-triage .
docker run -p 8000:8000 openenv-triage
```

Run the baseline agent:
```bash
pip install -r requirements.txt
export API_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-4o-mini"
export HF_TOKEN="your_token_here"
python inference.py
```
