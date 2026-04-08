from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, Literal
import random

app = FastAPI(title="Bug Triage SRE Environment")

class BugTriageAction(BaseModel):
    command: str = Field(
        description="The action to perform in the environment."
    )
    command_args: Dict[str, Any] = Field(
        description="Arguments for the chosen command. "
                    "For 'search_logs': {'service': str}, "
                    "For 'query_metrics': {'metric': str}, "
                    "For 'resolve_ticket': {'severity': str, 'root_cause': str, 'escalation': str}"
    )

class BugTriageObservation(BaseModel):
    ticket_description: str
    command_result: Optional[str] = None
    step_count: int

class ResetRequest(BaseModel):
    task_id: int

class StepRequest(BaseModel):
    action: BugTriageAction

class ActionResponse(BaseModel):
    observation: BugTriageObservation
    reward: float
    done: bool
    info: Dict[str, Any]

session_state = {
    "task_id": 1,
    "step_count": 0,
    "ground_truth": {},
    "logs_queried": False,
    "metrics_queried": False
}

EASY_TICKETS = [
    {"desc": "The login button is completely broken and nobody can access the app.", "gt": {"severity": "critical"}}
]
MEDIUM_TICKETS = [
    {
        "desc": "User reported slow performance during checkout.", 
        "logs": {"database": "OutOfMemory errors detected in pgsql pool", "frontend": "No errors"},
        "gt": {"severity": "high", "root_cause": "database"}
    }
]
HARD_TICKETS = [
    {
        "desc": "Intermittent failure when payment gateway is used.", 
        "logs": {"payment": "Timeout connecting to Stripe API 504", "database": "All queries successful"},
        "metrics": {"payment_latency": "p99 10000ms", "cpu": "30%"},
        "gt": {"severity": "high", "root_cause": "payment", "escalation": "billing_team"}
    }
]

@app.get("/")
def health_check():
    return {"status": "ok"}


@app.post("/reset", response_model=ActionResponse)
def reset(req: ResetRequest):
    session_state["task_id"] = req.task_id
    session_state["step_count"] = 0
    session_state["logs_queried"] = False
    session_state["metrics_queried"] = False
    
    if req.task_id == 1:
        ticket = random.choice(EASY_TICKETS)
    elif req.task_id == 2:
        ticket = random.choice(MEDIUM_TICKETS)
    elif req.task_id == 3:
        ticket = random.choice(HARD_TICKETS)
    else:
        raise HTTPException(status_code=400, detail="Invalid task ID")
        
    session_state["ground_truth"] = ticket
    
    obs = BugTriageObservation(
        ticket_description=ticket["desc"],
        command_result="Environment initialized. Type a command to proceed.",
        step_count=0
    )
        
    return ActionResponse(
        observation=obs,
        reward=0.0,
        done=False,
        info={"message": "Environment reset successfully"}
    )

@app.post("/step", response_model=ActionResponse)
def step(req: StepRequest):
    session_state["step_count"] += 1
    action = req.action
    
    reward = 0.0
    done = False
    cmd_result = ""
    
    task_id = session_state["task_id"]
    gt_full = session_state["ground_truth"]
    gt = gt_full.get("gt", {})
    
    if action.command == "search_logs":
        service = action.command_args.get("service")
        if "logs" in gt_full and service in gt_full["logs"]:
            cmd_result = f"Logs for {service}: {gt_full['logs'][service]}"
            if not session_state["logs_queried"]:
                reward += 0.2
                session_state["logs_queried"] = True
        else:
            cmd_result = f"No logs found for service '{service}'."
            
    elif action.command == "query_metrics":
        metric = action.command_args.get("metric")
        if "metrics" in gt_full and metric in gt_full["metrics"]:
            cmd_result = f"Metrics for {metric}: {gt_full['metrics'][metric]}"
            if not session_state["metrics_queried"]:
                reward += 0.2
                session_state["metrics_queried"] = True
        else:
            cmd_result = f"Metric '{metric}' not found."
            
    elif action.command == "resolve_ticket":
        sev = action.command_args.get("severity", "")
        root = action.command_args.get("root_cause", "")
        esc = action.command_args.get("escalation", "")
        
        if task_id == 1:
            if sev.lower() == gt.get("severity", ""):
                reward += 1.0
        elif task_id == 2:
            if sev.lower() == gt.get("severity", ""):
                reward += 0.4
            if root and gt.get("root_cause", "") in root.lower():
                reward += 0.4
        elif task_id == 3:
            if sev.lower() == gt.get("severity", ""):
                reward += 0.2
            if root and gt.get("root_cause", "") in root.lower():
                reward += 0.2
            if esc.lower() == gt.get("escalation", ""):
                reward += 0.2
                
        cmd_result = "Ticket resolved. Investigation closed."
        done = True
        
    else:
        cmd_result = f"Error: Invalid command '{action.command}'. Use search_logs, query_metrics, or resolve_ticket."
        reward -= 0.1 # Small penalty for invalid command

    if session_state["step_count"] >= 8:
        cmd_result = "Step limit reached. Forced termination."
        done = True
        
    obs = BugTriageObservation(
        ticket_description=gt_full.get("desc", ""),
        command_result=cmd_result,
        step_count=session_state["step_count"]
    )
        
    return ActionResponse(
        observation=obs,
        reward=reward,
        done=done,
        info={"step": session_state["step_count"]}
    )

@app.get("/state")
def state():
    return session_state
