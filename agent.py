from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
import os
from dotenv import load_dotenv

load_dotenv()

triage_incident = Agent(
    name = 'TriageAgent',
    model = LiteLlm(model="huggingface/MiniMaxAI/MiniMax-M2"),
    instruction="""You are a specialized triage agent. 
    Your only job is to gather and analyze incident data for handoff to runbook creation. 
    Create a short incident report. Identify the core technical issues. 
    Acknowledge missing data and if needed, ask specific technical questions before attempting a transfer. 
    Use minimal tokens, with no filler. Provide structured facts or request missing data.""",
    output_key="triage-incident-reports",
)

create_runbook = Agent(
    name = 'CreateRunbookAgent',
    model = LiteLlm(model="huggingface/MiniMaxAI/MiniMax-M2"),
    instruction="""You are a specialized report creating agent. 
    Your only job is to take the triaged incident report and create a suggested runbook that is clearly labeled. 
    This is for internal use within the company.""",
    output_key="create-runbook",
)

remediation_steps = Agent(
    name = 'RemediationAgent',
    model = LiteLlm(model="huggingface/MiniMaxAI/MiniMax-M2"),
    instruction="""You are a specialized remediation agent. 
    Your only job is to read the suggested runbooks and look at any external tools you have access to create remediation steps.
    Differentiate between tasks that require human approval such as rollbacks and restarts and tasks that can be done without approval. 
    Each step requiring human approval needs to be explicitly authorized by the user. Be brief. Use minimal tokens for reasoning""",
    output_key="do-remediation",
)

create_postmortem_report = Agent(
    name = 'CreatePostmortemReportAgent',
    model = LiteLlm(model="huggingface/MiniMaxAI/MiniMax-M2"),
    instruction="""You are a specialized report creating agent. 
    Your only job is to take the triaged incident report, suggested runbook and any other information the user has provided to create a postmortem report. 
    This is for internal use within the company.""",
    output_key="create-runbook",
)

create_update_post = Agent(
    name = 'CreateUpdatePostAgent',
    model = LiteLlm(model="huggingface/MiniMaxAI/MiniMax-M2"),
    instruction="""You are a specialized update post creating agent. 
    Your only job is to create a formatted post for updates about the incident using information available to you from the other agents and the user.""",
    output_key="create-update-post",
)

root_agent = Agent(
    model = LiteLlm(model="huggingface/MiniMaxAI/MiniMax-M2"),
    name='root_agent',
    instruction="Your only job is to decide which sub agent to run based on what the user says. " \
    "Expect the topic to be about a devops or sre incident. " \
    "Present all information from the agents. Do not answer it yourself. " \
    "Limit yourself to only calling each agent once for each incident the user tells you.",
    sub_agents=[triage_incident, create_runbook, remediation_steps, create_postmortem_report, create_update_post],
)
