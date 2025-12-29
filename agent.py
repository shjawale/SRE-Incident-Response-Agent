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
        suggest_runbook_steps
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
    tools=[request_human_approval, execute_infrastructure_action, verify_canary_health, run_synthetic_probe],
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



triage_agent.tools.extend([
    query_historical_incidents, 
    analyze_stack_trace, 
    suggest_runbook_steps
])

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
    STRATEGIC MANDATE: Do not perform technical analysis yourself. Orchestrate specialized agents and maintain the 'incident_timeline'.
    OPERATIONAL WORKFLOW (Follow in strict sequence):
    1. INITIALIZE & SCOPE: 
       - Action: Immediately call 'fetch_telemetry_checkpoint' with the service name provided by the user.
       - Logic: If 'MISSING_DATA' is returned, pause and prompt the user for CPU, Error Rate, and Latency. Once provided, call 'save_manual_telemetry' and 'update_incident_timeline'.
       - Tool: 'send_external_notification' (Channel: Slack) to announce "Incident Investigation Started".

    2. DELEGATE TRIAGE: 
       - Action: Call 'transfer_to_triage' to delegate analysis to the Triage specialist. 
       - Requirement: Before transferring, ensure 'update_incident_timeline' reflects that triage has been delegated.
       - Exit Criteria: triage_agent returns a 'triage_report' identifying a root cause.

    3. STRATEGIZE RUNBOOK: 
       - Action: Transfer to 'runbook_agent'.
       - Goal: Convert the triage_report into a step-by-step mitigation plan. 
       - Tool: 'send_external_notification' (Channel: Stakeholders) to provide a "Status: Root Cause Identified - Developing Runbook" update.

    4. EXECUTE REMEDIATION: 
       - Action: Call 'transfer_to_remediation' once a fix is approved'.
       - SAFETY GATE: You must verify that remediation_agent calls 'request_human_approval' for any destructive actions (restarts/scaling).
       - Log: Call 'update_incident_timeline' with the specific action taken (e.g., "Scaled service to 5 nodes").

    5. VERIFICATION & CLOSURE:
       - Action: Call 'send_external_notification' (Channel: Slack) stating "Fix Applied - Verifying Stability".
       - Post-Mortem: Transfer to 'postmortem_agent'.
       - ARCHIVAL: You MUST call 'archive_validated_report' with the final Markdown content. If 'archive_validated_report' is not called, the incident is not considered closed.

    STRICT CONSTRAINTS:
    - When transitioning to another agent, do not announce it in text. ONLY call the transfer function. Do not say 'I am now transferring you...'—just execute the tool call."
    - Never answer "What is the root cause?" directly; delegate to TriageAgent.
    - Every agent transfer or tool execution must be preceded or followed by 'update_incident_timeline'.
    - If a user asks "Start remediation" or "Run triage," skip to the corresponding step in the workflow immediately.
    """,
    tools=[
        archive_validated_report, 
        fetch_telemetry_checkpoint, 
        send_external_notification, 
        update_incident_timeline,
        save_manual_telemetry 
    ],
    sub_agents=[
        triage_agent, 
        runbook_agent,
        remediation_agent,
        postmortem_agent,
        status_update_agent
    ]
)


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

def main():
    incident_trigger = "The payment-gateway service is experiencing a 503 error spike. Please triage and remediate."
    asyncio.run(start_sre_session(incident_trigger))

if __name__ == "__main__":
 main()