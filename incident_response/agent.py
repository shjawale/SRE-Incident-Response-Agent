import os
import json
import uuid
import logging
from datetime import datetime
from typing import Optional
import random
import sys
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
from google import adk
from google.adk.tools import AgentTool
from google.adk.agents import Agent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool, ToolContext

import asyncio
from google.adk.runners import Runner
from google.genai.types import Content, Part
from google.adk.sessions import InMemorySessionService

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters


SIMULATION_LOG_FILE = "service_simulation.log"
# Create rotating file handler to limit log file size
log_handler = RotatingFileHandler(SIMULATION_LOG_FILE, maxBytes=10*1024*1024, backupCount=3)  # 10MB max, keep 3 backups

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRE_INCIDENTS_DB = "sre_incidents.db"
RUNBOOK_MCP_SERVER = os.path.join(CURRENT_DIR, "tools/runbook_mcp_server.py")

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SRE-Main-Orchestrator")


# Lazy load the model to defer memory allocation
MODEL_NAME = os.getenv("SRE_MODEL_NAME", "ollama_chat/qwen2.5:7b")
_SRE_MODEL = None


def get_sre_model():
    global _SRE_MODEL
    if _SRE_MODEL is None:
        _SRE_MODEL = LiteLlm(model=MODEL_NAME, api_base="http://localhost:11434", num_ctx=4096,
)
    return _SRE_MODEL



# For backward compatibility with existing code
@property
def SRE_MODEL():
    return get_sre_model()
    

SRE_MODEL = get_sre_model()


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
    file_path = os.path.join(CURRENT_DIR, "incident_timeline.txt")
    with open(file_path, "a") as f:
        f.write(entry)
    return "TIMELINE_UPDATED"


def request_human_approval(action: str, reasoning: str, tool_context: ToolContext) -> str:
    """
    Stops execution to ask a user for permission.
    This function should signal the ADK Runner to request user confirmation in the UI.
    Must be called BEFORE high-risk actions like service restarts or scaling
    It returns a status code that the agent interprets.
    """

    confirmation_details = {
        "action": action,
        "reasoning": reasoning,
        "timestamp": datetime.now().isoformat()
    }

    if not tool_context.tool_confirmation:
        # Pause execution and request confirmation from the user/human
        tool_context.request_confirmation(
            hint="Please review the details before proceeding with the action.",
            payload={"details": confirmation_details}
        )
        # Return a pending status or initial message
        return {"status": "pending", "message": "Awaiting human approval"}
    else:
        # User has responded, proceed with the action using the confirmation payload
        if tool_context.tool_confirmation.payload.get("approved"):
            # Action approved
            return {"status": "completed", "message": "Action approved by human, proceeding."}
        else:
            # Action rejected
            return {"status": "rejected", "message": "Action rejected by human."}


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
    error_rate = random.uniform(0, 0.05)  # Simulate error rate between 0% and 5%

    # Determine canary verification result
    if error_rate < 0.01:
        result = "PASSED"
        observation = f"Traffic stabilized, errors {error_rate:.2%} < 1%."
    else:
        result = "FAILED"
        observation = f"Error rate too high: {error_rate:.2%}."

    return "### CANARY VERIFICATION FOR {service_name.upper()}\nResult: {result}\nObservation: {observation}\n"


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


def generate_mock_logs(service_name: str, num_entries: int = 50):
    """Generates a simulated log entries, including some errors (with rotation to prevent unbounded growth)."""
    error_patterns = ["ConnectionResetError", "503 Service Unavailable", "MemoryLeakWarning", "TimeoutError"]
    logger_local = logging.getLogger(f"mock_logs_{service_name}")
    logger_local.addHandler(log_handler)
    
    for i in range(num_entries):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        log_level = random.choice(["INFO", "WARNING", "ERROR"])
        message = f"[{timestamp}] [{log_level}] [{service_name}] Request ID {uuid.uuid4().hex[:8]}: "
        if log_level == "ERROR" and random.random() < 0.3:
            message += f"{random.choice(error_patterns)} detected."
        else:
            message += "User request processed successfully."
        
        if log_level == "ERROR":
            logger_local.error(message)
        elif log_level == "WARNING":
            logger_local.warning(message)
        else:
            logger_local.info(message)
    
    return f"Generated {num_entries} mock log entries in {SIMULATION_LOG_FILE} (with automatic rotation)."


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


def generate_incident_id():
    # Get the current timestamp formatted as 'YYYYMMDD-HHMMSS'
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    # Generate a unique random UUID
    random_id = str(uuid.uuid4().int)[:6]  # Take first 6 characters to ensure it's manageable
    
    # Combine timestamp and random part to form the incident ID
    incident_id = f"{timestamp}-{random_id}"
    
    return incident_id




#Agents

import os
import sqlite3
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from state import SREAgentState

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(CURRENT_DIR, "sre_incidents.db")

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

primary_llm = ChatOllama(model="qwen2.5:7b", base_url=OLLAMA_URL, temperature=0.2, num_ctx=4096)
fallback_1  = ChatOllama(model="qwen2.5:3b", base_url=OLLAMA_URL, temperature=0.2)
fallback_2  = ChatOllama(model="phi3", base_url=OLLAMA_URL, temperature=0.2)

local_llm_chain = primary_llm.with_fallbacks([fallback_1, fallback_2])

def run_local_inference(prompt: str, system_instruction: str) -> str:
    messages = [SystemMessage(content=system_instruction), HumanMessage(content=prompt)]
    return local_llm_chain.invoke(messages).content

def triage_node(state: SREAgentState) -> dict:
    mock_logs = "Simulated Event: ConnectionResetError, 503 Service Unavailable"
    prompt = f"Incident Input: {state['incident_data']}\nSystem Captured Logs: {mock_logs}"
    instruction = "You are an SRE Triage Expert. Analyze the error trace and write a concise summary."
    report = run_local_inference(prompt, instruction)
    return {"triage_report": report, "status": "TRIAGED"}

def knowledge_node(state: SREAgentState) -> dict:
    found_books = []
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT title, content FROM runbooks WHERE content LIKE ? LIMIT 3", ('%error%',))
        found_books = [{"title": row["title"], "content": row["content"]} for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        print(f"Database error: {e}")

    prompt = f"Active Report: {state['triage_report']}\nMatched Runbooks: {found_books}"
    instruction = "You are an SRE Runbook Matcher. Suggest specific mitigation steps based on context."
    steps = run_local_inference(prompt, instruction)
    return {"found_runbooks": found_books, "suggested_steps": steps, "status": "KNOWLEDGE_MATCHED"}

def persistence_node(state: SREAgentState) -> dict:
    generated_id = f"INC-{os.urandom(4).hex().upper()}"
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS incidentrecord (id TEXT, service TEXT, status TEXT, timestamp TEXT)")
        cursor.execute(
            "INSERT INTO incidentrecord (id, service, status, timestamp) VALUES (?, ?, ?, datetime('now'))",
            (generated_id, "Ollama-Cluster", "AWAITING_APPROVAL")
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database write error: {e}")
    return {"incident_id": generated_id}

def remediation_node(state: SREAgentState) -> dict:
    if not state.get("approval_granted"):
        return {"remediation_logs": "Action aborted by operator.", "status": "ABORTED"}
    action_log = "SUCCESS: Triggered rolling microservice restart. Metrics stabilized."
    return {"remediation_logs": action_log, "status": "REMEDIATED"}


# Database setup using SQLModel
from sqlmodel import Field, SQLModel, create_engine, Session
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

# Define a schema (e.g., Incident tracking)
class IncidentRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    service: str
    status: str
    timestamp: datetime = Field(default_factory=datetime.now)

sqlite_url = "sqlite:///incident_response/sre_incidents.db"
engine = create_engine(sqlite_url)

def init_db():
    SQLModel.metadata.create_all(engine)

# Database logic to be used as a Tool
def log_incident_to_db(service: str, status: str) -> str:
    """Persists incident status into the SQL database."""
    with Session(engine) as session:
        incident = IncidentRecord(service=service, status=status)
        session.add(incident)
        session.commit()
        return f"Database updated: {service} set to {status}"


# Initialize DB before starting
init_db()


APP_NAME = "sre_app"
sessionservice = InMemorySessionService()
sessionservice.app_name = APP_NAME


SHARED_USER_ID = "sre_agent_system"
SHARED_SESSION_ID = f"INC-{uuid.uuid4().hex[:8].upper()}"

   
async def start_sre_session(initial_report: str):
    '''
    Orchestrates the SRE agent session using the ADK Runner.
    '''
    # Initialize session
    session = await sessionservice.create_session(
        app_name=APP_NAME, 
        user_id=SHARED_USER_ID, 
        session_id=SHARED_SESSION_ID
    )
    
    print(f"DEBUG: Successfully created Session ID: {session.id}", file=sys.stderr)
    print(f"--- SRE AGENT SESSION STARTING ---", file=sys.stderr)
    print(f"Incident: {initial_report}\n", file=sys.stderr)

    user_message = Content(role="user", parts=[Part(text=initial_report)])
    
    try:
        # Run the async event loop via the ADK Runner
        async for event in runner.run_async(
            user_id=SHARED_USER_ID,
            session_id=SHARED_SESSION_ID, 
            new_message=user_message
        ):
            #if not event.is_final_response():
            if event.content and event.content.parts:
                print(f"[{event.author}]: {event.content.parts[0].text}", file=sys.stderr)

            if event.is_final_response():
                print("\n--- FINAL INCIDENT RESOLUTION ---", file=sys.stderr)
                if event.content and event.content.parts:
                    print(event.content.parts[0].text, file=sys.stderr)

    except Exception as e:
        print(f"\n[FATAL ERROR] {e}", file=sys.stderr)


def main():
    incident_trigger = "Given a description of a DevOps or SRE incident, triage it, suggest runbooks for it, start remediation. After the incident has been resolved, create a postmortem report and a formatted update post."
    asyncio.run(start_sre_session(incident_trigger))        
        
if __name__ == "__main__":
    main()
