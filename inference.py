import os
import json
import re
import requests
from openai import OpenAI
from typing import Dict, Any, List

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.environ.get("HF_TOKEN")

ENV_URL = "http://localhost:8000"

client = OpenAI(
    api_key=os.environ.get("HF_TOKEN"),
    base_url=os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
)

def log_start(task: int, env: str, model: str):
    print(f"[START] {json.dumps({'task': task, 'env': env, 'model': model})}", flush=True)

def log_step(step: int, action: Dict[str, Any], reward: float, done: bool, error: Any = None):
    log_data = {'step': step, 'action': action, 'reward': reward, 'done': done, 'error': str(error) if error else None}
    print(f"[STEP] {json.dumps(log_data)}", flush=True)

def log_end(success: bool, steps: int, score: float, rewards: List[float]):
    print(f"[END] {json.dumps({'success': success, 'steps': steps, 'score': score, 'rewards': rewards})}", flush=True)

def extract_json(text: str) -> str:
    """Safely extract JSON from Markdown code blocks if they exist."""
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    return text.strip()

def run_agent_loop(task_id: int):
    log_start(task=task_id, env="bug-triage-env", model=MODEL_NAME)
    
    try:
        resp = requests.post(f"{ENV_URL}/reset", json={"task_id": task_id})
        resp.raise_for_status()
        state = resp.json()
    except Exception as e:
        print(f"Error connecting to env: {e}")
        return
        
    done = state.get("done", False)
    step = 0
    rewards = []
    
    while not done and step < 8:
        step += 1
        observation = state.get("observation", {})
        
        prompt = f"""
You are an expert Site Reliability Engineer (SRE).
Your goal is to investigate and resolve an incoming ticket.

Current Observation:
ticket_description: {observation.get('ticket_description')}
command_result: {observation.get('command_result')}
step_count: {observation.get('step_count')}

You must output your action strictly as JSON matching this format exactly:
{{
  "command": "search_logs" | "query_metrics" | "resolve_ticket",
  "command_args": {{
      // for search_logs -> "service": "database" | "payment" | etc
      // for query_metrics -> "metric": "cpu" | "payment_latency" | etc
      // for resolve_ticket -> "severity": "low"|"medium"|"high"|"critical", "root_cause": "...", "escalation": "..."
  }}
}}

Analyze the command_result. If you need more information, use search_logs or query_metrics first. 
Once you have enough info, use resolve_ticket.
"""
        try:
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            action_text = completion.choices[0].message.content or ""
            clean_json = extract_json(action_text)
            action_payload = json.loads(clean_json)
        except Exception as e:
            action_payload = {
                "command": "resolve_ticket", 
                "command_args": {"severity": "medium", "root_cause": "unknown", "escalation": "none"}
            }
            
        try:
            step_resp = requests.post(f"{ENV_URL}/step", json={"action": action_payload})
            step_resp.raise_for_status()
            step_result = step_resp.json()
            
            state = {"observation": step_result["observation"]}
            done = step_result["done"]
            reward = step_result["reward"]
            rewards.append(reward)

            log_step(step=step, action=action_payload, reward=reward, done=done)
        except Exception as e:
            print(f"Error stepping environment: {e}")
            break

    total_reward = sum(rewards)
    # clamp to 0-1
    score = min(max(total_reward, 0.0), 1.0)
    success = score >= 0.5
    
    log_end(success=success, steps=step, score=score, rewards=rewards)

def main():
    for task in [1, 2, 3]:
        run_agent_loop(task)

if __name__ == "__main__":
    main()
