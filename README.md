# SRE Incident Response Agent (ADK & MiniMax-M2)
This system is an enterprise-level agentic workflow built with the Google Agent Development Kit (ADK). It automates SRE incident management. The system uses a multi-agent hierarchy to research, triage, remediate, and report on DevOps incidents. It uses Gemini 2.0 Flash Lite for speed and MiniMax-M2 for complex reasoning.

## Overview
This project automates the end-to-end incident response pipeline. The RootAgent serves as an orchestrator, dynamically routing user alerts to specialized sub-agents based on the state of the incident. It also supports running ADK Web for a user-friendly web interface to interact with the agents.

### Key Components
  *  Orchestration: A hierarchical routing model using the Agent class.
  *  LLM: MiniMax-M2: Powers complex triage, runbook generation, and remediation logic via LiteLlm.

## Agent Roles
| Agent          |     Model   |    Responsibility
-----------------|:------------|:---------------------
| TriageAgent    |      MiniMax-M2 |  Analyzes raw data, identifies core issues, and flags missing facts.
| RunbookAgent   |      MiniMax-M2 |  Generates internal suggested runbooks for the engineering team.
| RemediationAgent |    MiniMax-M2 |  Proposes fixes, distinguishing between auto-tasks and manual rollbacks.
| PostmortemAgent  |    MiniMax-M2 |  Compiles final internal reports once the incident is resolved.
| UpdatePostAgent  |    MiniMax-M2 |  Formats external/internal status updates for stakeholders.

## Configuration & Installation
Prerequisites
   * Python 3.10+
   * Google Cloud Project (for Gemini and ADK infrastructure)
   * Hugging Face API Token (for MiniMax-M2 access)

**Setup**
1. Clone the repository and install dependencies:
```
    bash
    pip install google-adk python-dotenv
```
2. Create a .env file in the root directory similar to:
```
HUGGINGFACE_API_TOKEN=your_hf_token
```

**Usage**

To utilize the agents, instantiate the RootAgent and provide user queries regarding incidents. The RootAgent will manage the delegation to the appropriate sub-agent. You can also run ADK Web for an interactive web interface.
```
python
from google.adk.agents import Agent
from google.adk.models.lite\_llm import LiteLlm

# Example of initiating the root agent
root\_agent.run(user\_input)
```
