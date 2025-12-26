# SRE Incident Response Agent (ADK & MiniMax-M2)
This system is an agentic workflow built with the Google Agent Development Kit (ADK). It automates SRE incident management. The system uses a multi-agent hierarchy to research, triage, remediate, and report on DevOps incidents. Complex reasoning tasks, including detailed incident analysis and root cause identification, are powered by the MiniMax-M2 model.

## Overview
This project automates the end-to-end incident response pipeline. The RootAgent serves as a central orchestrator, dynamically routing user alerts to specialized sub-agents based on the state of the incident. To facilitate real-time monitoring and human-in-the-loop (HITL) oversight, the project integrates ADK Web. This provides a graphical interface to visualize agent reasoning paths, monitor sub-agent handoffs, and manually approve remediation steps (like rollbacks) that the agents propose.

### Key Components
  *  Orchestration: A hierarchical routing model using the Agent class.
  *  LLM: MiniMax-M2: Powers complex triage, runbook generation, and remediation logic via LiteLlm.

## Agent Roles
| Agent          |    Purpose
-----------------|:---------------------
| TriageAgent    |  Analyzes incident data, identifies core issues, and flags data gaps.
| RunbookAgent   |  Generates internal suggested runbooks for the engineering review.
| RemediationAgent |  Proposes fixes, distinguishing between auto-tasks and manual rollbacks.
| PostmortemAgent  |  Compiles final internal post-incident reports.
| UpdatePostAgent  |  Formats status updates for internal and external stakeholders.

## Configuration & Installation
Prerequisites
   * Python 3.10+
   * Hugging Face API Token (for MiniMax-M2 access)
   * Google Account (Optional): Only needed if you choose to deploy the agent to Google Cloud services like Vertex AI Agent Engine later. Local development with Hugging Face models does not require this setup.

**Setup**
1. Clone the repository:
```
git clone https://github.com/shjawale/SRE-Incident-Response-Agent.git
cd sre-incident-agent
```

2. Create and activate a Virtual Environment:

    A virtual environment ensures that the ADK and LiteLLM dependencies do not conflict with the global Python installation.
```
# Create the environment
python -m venv venv

# Activate it (Windows)
.\venv\Scripts\activate

# Activate it (macOS/Linux)
source venv/bin/activate
```

3. Install dependencies:
```
pip install google-adk litellm httpx python-dotenv 
```
4. Configure Environment Variables:

    Create a .env file in the root directory and add credentials. Refer to .env.example for the required format:
```
HUGGINGFACE_API_TOKEN=your_hf_token
```

**Usage**

1. To utilize the agents directly in code, instantiate the RootAgent and provide user queries regarding incidents. The RootAgent will manage the delegation to the appropriate sub-agent.
python
```
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

# Example of initiating the root agent
root_agent.run("We are seeing 500 errors in the checkout service.")
```

2. Interactive UI via ADK Web
For an enterprise-grade experience, you can launch the ADK Web interface. This is highly recommended for SRE teams as it provides:
  *  Traceability: View the step-by-step reasoning logs of the MiniMax-M2 model.
  *  Agent Monitoring: Watch the RootAgent "delegate" tasks to the Triage or Remediation agents in real-time.
  *  Human Approval: A dedicated interface to review and authorize the RemediationAgent’s suggested tasks before they are executed.

To start the web interface, run:
```
# Command to launch the ADK Web server
python -m google.adk.web --agent root_agent
```
