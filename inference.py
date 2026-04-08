import os
import json
import requests
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Dict, Any, List

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.environ.get("HF_TOKEN")

ENV_URL = "http://localhost:7860"

client = OpenAI(
    api_key=os.environ.get("HF_TOKEN"),
    base_url=os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
)

class CommandArgs(BaseModel):
    service: str | None = Field(None, description="The service to search logs for. Only required if command is search_logs")
    metric: str | None = Field(None, description="The metric to query. Only required if command is query_metrics")
    severity: str | None = Field(None, description="Low, medium, high, or critical. Required if command is resolve_ticket")
    root_cause: str | None = Field(None, description="The root cause deduced. Required if command is resolve_ticket")
    escalation: str | None = Field(None, description="The team to escalate to. Required if command is resolve_ticket")

class BugTriageAction(BaseModel):
    command: str = Field(description="search_logs, query_metrics, or resolve_ticket")
    command_args: CommandArgs

def log_start(task: int, env: str, model: str):
    print(f"[START] {json.dumps({'task': task, 'env': env, 'model': model})}", flush=True)

def log_step(step: int, action: Dict[str, Any], reward: float, done: bool, error: Any = None):
    log_data = {'step': step, 'action': action, 'reward': reward, 'done': done, 'error': str(error) if error else None}
    print(f"[STEP] {json.dumps(log_data)}", flush=True)

def log_end(success: bool, steps: int, score: float, rewards: List[float]):
    print(f"[END] {json.dumps({'success': success, 'steps': steps, 'score': score, 'rewards': rewards})}", flush=True)

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
    
    system_prompt = """
You are an expert Site Reliability Engineer (SRE).
Your goal is to investigate and resolve an incoming ticket.
Use the tool 'search_logs' or 'query_metrics' first if the ticket is vague. 
Once you have found the root cause or have enough info, use 'resolve_ticket'.
"""
    messages = [{"role": "system", "content": system_prompt}]
    
    while not done and step < 8:
        step += 1
        observation = state.get("observation", {})
        
        user_msg = f"""
Current Observation:
ticket_description: {observation.get('ticket_description')}
command_result: {observation.get('command_result')}
step_count: {observation.get('step_count')}
"""
        messages.append({"role": "user", "content": user_msg})
        
        try:
            completion = client.beta.chat.completions.parse(
                model=MODEL_NAME,
                messages=messages,
                response_format=BugTriageAction
            )
            
            action_obj = completion.choices[0].message.parsed
            
            args_clean = {k: v for k, v in action_obj.command_args.model_dump().items() if v is not None}
            action_payload = {
                "command": action_obj.command,
                "command_args": args_clean
            }
            
            messages.append({
                "role": "assistant",
                "content": completion.choices[0].message.content
            })
            
        except Exception as e:
            action_payload = {
                "command": "resolve_ticket", 
                "command_args": {"severity": "medium", "root_cause": "unknown", "escalation": "none"}
            }
            messages.append({"role": "assistant", "content": json.dumps(action_payload)})
            
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
