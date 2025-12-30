import os
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Optional
import random


from dotenv import load_dotenv
from google import adk
from google.adk.agents import Agent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.agent_tool import AgentTool


from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SRE-Main-Orchestrator")

MODEL_NAME = os.getenv("SRE_MODEL_NAME")
SRE_MODEL = LiteLlm(model=MODEL_NAME, api_base="http://localhost:11434", num_ctx=4096)

def fetch_telemetry_checkpoint(service_name: str) -> str:
    """
    Checks for telemetry in the local state file. 
    If missing, requests the agent to prompt the user.
    """
    state_file = "incident_state.json"
    
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            data = json.load(f)
            
            if data.get("service") == service_name:
                return f"TELEMETRY LOADED: CPU {data['cpu']}, Errors {data['errors']}. Data is current."
    
    return (f"MISSING_DATA: No telemetry found for {service_name}.\nPlease ask the user to provide CPU, Error Rate, and Latency manually in the chat.")


def save_manual_telemetry(service: str, cpu: str, errors: str, latency: str) -> str:
    """
    Called by the agent once the user provides details in the chat.
    """
    data = {
        "service": service,
        "cpu": cpu,
        "errors": errors,
        "latency": latency
    }
    with open("incident_state.json", "w") as f:
        json.dump(data, f)
    return "SUCCESS: Telemetry saved to state. Proceed with triage."


def query_historical_incidents(service_name: str, error_pattern: str) -> str:
    """
    Searches the knowledge base for similar historical P1 incidents.
    """
    
    similar_cases = [
        {"id": "INC-992", "cause": "Connection Pool Exhaustion", "fix": "Increased DB Max Connections"},
        {"id": "INC-441", "cause": "Memory Leak in Hotfix", "fix": "Rollback to previous stable version"}
    ]
    return f"HISTORICAL CORRELATION: Found {len(similar_cases)} similar events. Recent fix for 503s: {similar_cases[0]['fix']}."


def run_synthetic_probe(target_url: str) -> str:
    """
    Performs an out-of-band network probe to verify external connectivity.
    """
    results = ["TIMEOUT", "REJECTED", "SUCCESS"]
    status = random.choice(results)
    return f"PROBE RESULT for {target_url}: {status} (Internal Latency: 12ms)"


def analyze_stack_trace(logs: str) -> str:
    """
    Deep-dives into log strings to extract specific exception types.
    """
    if "ConnectionResetError" in logs or "503" in logs:
        return "LOG_ANALYSIS: Pattern suggests downstream saturation or circuit breaker trip."
    return "LOG_ANALYSIS: No standard exception pattern recognized."


def suggest_runbook_steps(service_name: str) -> str:
    """
    Retrieves the standard operating procedure (SOP) for the service.
    """
    sop = {
        "payment-gateway": "1. Check DB connections. 2. Verify Auth Service tokens. 3. Restart Pods if CPU > 90%.",
        "default": "1. Escalate to On-Call. 2. Fetch Logs. 3. Check for recent deployments."
    }
    return f"SOP/RUNBOOK for {service_name}: {sop.get(service_name, sop['default'])}"


def update_incident_timeline(event_description: str):
    """
    Maintains a chronological log of agent actions for the postmortem.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {event_description}\n"
    with open("incident_timeline.txt", "a") as f:
        f.write(entry)
    return "TIMELINE_UPDATED"


def request_human_approval(action: str, reasoning: str) -> str:
    """
    Stops execution to ask a human operator for permission. 
    Must be called BEFORE high-risk actions like service restarts or scaling.
    """
    print(f"\n[!!!] MANUAL APPROVAL REQUIRED: {action}")
    print(f"[AGENT REASONING]: {reasoning}")
    choice = input("Authorize execution? (yes/no): ").strip().lower()
    return "APPROVED" if choice == "yes" else "DENIED_BY_OPERATOR"


def request_human_approval(action: str, reasoning: str) -> str:
    """
    Stops execution to ask a human operator for permission in an ADK web environment.
    This function should signal the ADK Runner to request user confirmation in the UI.
    Must be called BEFORE high-risk actions like service restarts or scaling
    It returns a status code that the agent interprets.
    """
    print(f"\n[!!!] MANUAL APPROVAL REQUIRED: {action}")
    print(f"[AGENT REASONING]: {reasoning}")
    return f"APPROVAL_PENDING: Authorize '{action}'? (Reply 'yes' or 'no')"


def execute_infrastructure_action(service_name: str, action: str) -> str:
    """
    Executes a technical remediation task such as 'RESTART', 'SCALE', or 'FLUSH_CACHE'.
    Requires human approval first if the action is destructive.
    """
    ts = datetime.now().strftime("%H:%M:%S")
    log_entry = f"### EXECUTION LOG\n- Service: {service_name}\n- Action: {action}\n- Status: SUCCESS\n- Time: {ts}"
    return log_entry


def verify_canary_health(service_name: str) -> str:
    """
    Verifies system stability after a fix has been applied. 
    Checks if error rates have dropped below 1%.
    """
    return "### CANARY VERIFICATION\n- Result: PASSED\n- Observation: Traffic stabilized, errors < 1%."


def send_external_notification(channel: str, message: str) -> str:
    """
    Broadcasts a professional status update to stakeholders via Slack or PagerDuty.
    Use this every time an incident state changes (e.g., Triage Started, Resolved).
    """
    with open("notification_broadcast.log", "a") as f:
        f.write(f"[{datetime.now()}] [{channel.upper()}] {message}\n")
    return f"NOTIFICATION SENT: Broadcast to {channel} confirmed."


def archive_validated_report(content: str, report_type: str) -> str:
    """
    REQUIRED: Saves the final report to a local file.
    Content MUST start with '
    If this tool is not called, the report is NOT saved.
    """
    if not content or "###" not in content:
        return "ERROR: Tool failed. Content must use Markdown'###' headers to be valid for archival."
    
    filename = f"{report_type}_{str(uuid.uuid4())[:6]}.md"
    try:
        with open(filename, "w") as f:
            f.write(content)
        return f"SUCCESS: Report saved as {filename}. Inform the user the file is archived."
    except Exception as e:
        return f"SYSTEM ERROR: Could not write file: {str(e)}"


SIMULATION_LOG_FILE = "service_simulation.log"

def generate_mock_logs(service_name: str, num_entries: int = 50):
    """Generates a large number of simulated log entries, including some errors."""
    error_patterns = ["ConnectionResetError", "503 Service Unavailable", "MemoryLeakWarning", "TimeoutError"]
    with open(SIMULATION_LOG_FILE, "a") as f:
        for i in range(num_entries):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            log_level = random.choice(["INFO", "WARNING", "ERROR"])
            message = f"[{timestamp}] [{log_level}] [{service_name}] Request ID {uuid.uuid4().hex[:8]}: "
            if log_level == "ERROR" and random.random() < 0.3:
                message += f"{random.choice(error_patterns)} detected.\n"
            else:
                message += "User request processed successfully.\n"
            f.write(message)
    return f"Generated {num_entries} mock log entries in {SIMULATION_LOG_FILE}."


def analyze_large_logs_for_patterns(log_file: str) -> str:
    """Performs a more thorough, local analysis of the generated log file for common patterns."""
    error_counts = {}
    total_lines = 0
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            for line in f:
                total_lines += 1
                if "ERROR" in line:
                    for pattern in ["ConnectionResetError", "503", "MemoryLeakWarning", "TimeoutError"]:
                        if pattern in line:
                            error_counts[pattern] = error_counts.get(pattern, 0) + 1
                            break
    
    if total_lines == 0:
        return "LOG_ANALYSIS: No logs processed."
    
    report = f"LOG_ANALYSIS: Analyzed {total_lines} lines.\n"
    if error_counts:
        for pattern, count in error_counts.items():
            report += f"- Found {count} instances of '{pattern}'.\n"
        report += "Pattern suggests specific, recurring errors."
    else:
        report += "No specific error patterns recognized."
    return report


def track_error_budget(service_name: str, incident_duration_minutes: float, budget_minutes: int = 500) -> str:
    """Tracks the SRE error budget for a service, locally, without a database."""
    remaining_budget = budget_minutes - incident_duration_minutes
    if remaining_budget < 0:
        return f"ERROR_BUDGET_BREACH: The {service_name} service has exceeded its quarterly error budget by {-remaining_budget} minutes."
    else:
        return f"ERROR_BUDGET_STATUS: {service_name} has {remaining_budget} minutes of budget remaining."


def simulate_chaos_test(service_name: str, fault_type: str) -> str:
    """Simulates a controlled 'chaos' injection to test system resilience locally."""
    if fault_type == "network_latency":
        latency = random.randint(100, 1000)
        return f"CHAOS_TEST_RESULT: Injected {latency}ms latency into {service_name} network path. System stability check required."
    elif fault_type == "cpu_spike":
        duration = random.randint(5, 30)
        return f"CHAOS_TEST_RESULT: Simulated 99% CPU spike on {service_name} for {duration} seconds. Monitoring response."
    else:
        return f"CHAOS_TEST_RESULT: Unknown fault type {fault_type}."


#Agents
triage_agent = Agent(
    name='TriageAgent',
    model=SRE_MODEL,
    instruction="""Analyze incident data. Identify root causes. Keep reports factual and brief.
    gather and analyze incident data for handoff to runbook creation. 
    Create a short incident report. Identify the core technical issues. 
    Acknowledge missing data and if needed, ask specific technical questions before attempting a transfer. """,
    tools=[
        query_historical_incidents, 
        analyze_stack_trace, 
        suggest_runbook_steps,
        generate_mock_logs, 
        analyze_large_logs_for_patterns
    ],
    output_key="triage_report"
)

runbook_agent = Agent(
    name = 'RunbookAgent',
    model = SRE_MODEL,
    instruction="""You are a specialized report creating agent. 
    Your only job is to take the triaged incident report and create a suggested runbook that is clearly labeled. 
    This is for internal use within the company.""",
    output_key="runbooks",
)

remediation_agent = Agent(
    name='RemediationAgent',
    model=SRE_MODEL,
    instruction="""Execute fixes based on triaged reports. Always verify health after an action. 
    Read the suggested runbooks and use at any external tools you have access to create remediation steps.
    Differentiate between tasks that require human approval such as rollbacks or restarts and tasks that can be done without approval. 
    CRITICAL: If a human approval request is pending (indicated by 'APPROVAL_PENDING' in the tool output), wait for the user's next message. 
    If the user replies with 'no' or 'deny', **immediately stop** the remediation process and provide a final report stating that remediation was halted by the operator. 
    If the user replies with 'yes' or 'approve', proceed with the execution tool call.""",
    tools=[
        request_human_approval, 
        execute_infrastructure_action, 
        verify_canary_health, 
        run_synthetic_probe, 
        track_error_budget, 
        simulate_chaos_test],
    output_key="remediation_results"
)

postmortem_agent = Agent(
    name='PostmortemAgent',
    model=SRE_MODEL,
    instruction="""Compile all logs into a 'Blameless Postmortem' and archive it for internal use within the company.
    Take the triaged incident report, suggested runbook and any other information the user has provided to create a postmortem report.""",
    tools=[archive_validated_report],
    output_key="final_postmortem"
)

status_update_agent = Agent(
    name='StatusUpdateAgent',
    model=SRE_MODEL,
    instruction="Translate technical logs into clear updates for non-technical stakeholders.",
    tools=[send_external_notification]
)

def transfer_to_triage():
    """
    EXECUTE IMMEDIATELY to transfer control to the TriageAgent. 
    Use this when the root cause is unknown or data analysis is required.
    """
    return triage_agent

def transfer_to_remediation():
    """Transfer to the RemediationAgent to apply fixes."""
    return remediation_agent

root_agent = Agent(
    model=SRE_MODEL,
    name='root_agent',
    instruction="""
    You are the SRE Incident Commander. You manage the lifecycle of a P1/P2 incident. 
    Strategic Mandate: Do not perform technical analysis yourself. Orchestrate specialized agents and maintain the 'incident_timeline'.
    Operational Workflow (Follow in strict sequence):
    Initialize & Scope: Call generate_mock_logs. If data is missing, prompt user for metrics, then call save_manual_telemetry and update_incident_timeline. Once logs exist, call analyze_large_logs_for_patterns on service_simulation.log.
    Delegate Triage: Update the timeline, then call transfer_to_triage. Wait for a triage_report.
    Strategize Runbook: Call send_external_notification (Stakeholders), then call transfer_to_runbook to generate a mitigation plan.
    Execute Remediation: Call transfer_to_remediation. Safety Gate: Ensure the agent requests human approval for destructive actions. Update the timeline with specific actions taken.
    Verify & Close: Call send_external_notification (Slack). Call transfer_to_postmortem. Final Step: Call archive_validated_report to officially close the incident. 
    
    Strict Constraints
    Do not announce transfers textually. Execute the tool call only.
    Never identify root causes; always delegate to the TriageAgent.
    Every tool call or agent transfer must be logged via update_incident_timeline.
    If the user requests a specific phase (e.g., "Run triage"), jump directly to that step.
    """,
    tools=[
        archive_validated_report, 
        fetch_telemetry_checkpoint, 
        send_external_notification, 
        update_incident_timeline,
        save_manual_telemetry,
    ],
    sub_agents=[
        triage_agent, 
        runbook_agent,
        remediation_agent,
        postmortem_agent,
        status_update_agent
    ]
)


from google.adk.apps import App

app = App(name="agent_project", root_agent=root_agent)

#app = FastAPI(title="SRE Agent API")

class IncidentRequest(BaseModel):
    report: str
    user_id: str = "sre_user_01"
    session_id: str = str(uuid.uuid4())

#@app.post("/triage")
async def triage_incident(request: IncidentRequest):
    """
    API Endpoint to trigger the SRE agent via HTTP.
    """
    try:
        runner = InMemoryRunner(agent=root_agent)
        final_text = ""
        
        # We use the same logic as your start_sre_session but capture output for JSON response
        async for event in runner.run_async(
            user_id=request.user_id,
            session_id=request.session_id,
            new_message=request.report # Passing the string directly to ADK
        ):
            if event.content and event.content.parts:
                final_text += event.content.parts[0].text + "\n"
        
        return {
            "status": "completed",
            "session_id": request.session_id,
            "resolution": final_text.strip()
        }
    except Exception as e:
        logger.error(f"API Error: {str(e)}")
        raise HTTPException(status_status_code=500, detail=str(e))


import asyncio
from google.adk.runners import Runner, InMemoryRunner
from google.genai.types import Content, Part

async def start_sre_session(initial_report: str):
    """
    Orchestrates the agent using the ADK Runner to handle tool calls and events asynchronously.
    """
    print(f"--- SRE AGENT SESSION STARTING ---")
    
    runner = InMemoryRunner(agent=root_agent)
    
    user_message = Content(role="user", parts=None)
    print(f"Incident: {initial_report}\n")
    
    try:
        async for event in runner.run_async(
            user_id="sre_user_01", 
            session_id="incident_001", 
            new_message=user_message
        ):
            
            if event.content:
                print(f"[{event.author}]: {event.content.parts[0].text}")
            
            if event.is_final_response():
                print("\n--- FINAL INCIDENT RESOLUTION ---")
                print(event.content.parts[0].text)
        
    except Exception as e:
        print(f"\n[FATAL ERROR] System limit reached: {e}")


def start_api_server():
    print("Starting FastAPI server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)


def main():
    print("Choose an option: (1) Run CLI simulation (2) Start API server")
    # choice = input("Enter 1 or 2: ").strip()
    
    choice = '1'
    if choice == '1':
        incident_trigger = "Given a decsription of a DevOps or SRE incident, triage it, suggest runbooks for it, start remediation. After the incident has been resolved, create a postmortem report and a formatted update post."
        asyncio.run(start_sre_session(incident_trigger))
    elif choice == '2':
        start_api_server()

if __name__ == "__main__":
    main()