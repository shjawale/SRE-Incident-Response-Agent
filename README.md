# SRE Incident Response Agent (ADK & mistral)
This system is an agentic workflow built with the Google Agent Development Kit (ADK). It automates SRE incident management using a multi-agent hierarchy to research, triage, remediate, and report on DevOps incidents. Complex reasoning tasks are powered by the mistral:7b model.

## Overview
This project automates the end-to-end incident response pipeline. The RootAgent acts as a central orchestrator, dynamically routing user alerts to specialized sub-agents based on the incident state.

Integration with ADK Web provides a graphical interface for real-time monitoring and human-in-the-loop (HITL) oversight, allowing visualization of agent reasoning paths, monitoring sub-agent handoffs, and manual approval of remediation steps

### Key Components
  *  Orchestration: A hierarchical routing model using the Agent class.
  *  LLM: mistral:7b powers complex triage, runbook generation, and remediation logic via LiteLlm.

## Agent Roles
| Agent          |    Purpose
-----------------|:---------------------
| TriageAgent    |  Analyzes incident data, identifies core issues, and flags data gaps.
| RunbookAgent   |  Generates internal suggested runbooks for the engineering review.
| RemediationAgent |  Proposes fixes and actions, distinguishing between auto-tasks and manual rollbacks.
| PostmortemAgent  |  Compiles final internal post-incident reports and root cause analysis.
| StatusUpdateAgent  |  Formats status updates for both internal teams and external stakeholders.

## Configuration & Installation
Prerequisites
   * Python 3.10+
   * Ollama: access to the mistral:7b model.
   * LiteLLM: initializes an LLM instance allowing you to interact with a model.
   * Google Account (Optional): Only needed if you choose to deploy the agent to Google Cloud services like Vertex AI Agent Engine later. Local development with Ollama models does not require this setup.

**Setup**
1. Clone the repository:
    ```
    git clone https://github.com/shjawale/SRE-Incident-Response-Agent.git
    cd sre-incident-agent
    ```

2. Install Ollama and the Mistral model:

    Download and install Ollama from the official website.
    Open your terminal or command prompt and run the following command to download the mistral model:
    ```
    ollama pull mistral:7b
    ```

3. Create and activate a Virtual Environment:

    A virtual environment ensures that the ADK and LiteLLM dependencies do not conflict with the global Python installation.

    ```
    # Create the environment
    python -m venv venv

    # Activate it
    .\venv\Scripts\activate     (Windows)
    source venv/bin/activate    (macOS/Linux)
    ```

4. Install dependencies:

    ```
    pip install google-adk litellm httpx python-dotenv
    ```

5. Configure Environment Variables:

    Create a .env file in the root directory and add credentials. Refer to .env.example for the required format:
    ```
    OPENAI_API_KEY=<your key>
    ```

**Usage**

1. Direct Execution in Code

    To utilize the agents directly in code, instantiate the RootAgent and provide user queries regarding incidents. The RootAgent will manage the delegation to the appropriate sub-agent.
    python
    ```
    from google.adk.agents import Agent
    from google.adk.models.lite_llm import LiteLlm

    # LiteLLM automatically uses the local Ollama API for the 'ollama/mistral' model
    SRE_MODEL = LiteLlm(model="ollama/mistral:7b", api_base="http://localhost:11434")

    # Example of initiating the root agent
    root_agent.run("We are seeing Error 503 in the checkout service.")
    ```

2. Interactive UI via ADK Web

    For an enterprise-grade experience, you can launch the ADK Web interface to get traceability, agent monitoring, and human approval interfaces. Ensure your Ollama application is running in the background.

    To start the web interface, run:
    ```
    # Command to launch the ADK Web server
    python -m google.adk.web --agent root_agent
    ```

**Generated Files**

When the agent is run locally, specific Python functions write various incident-related documents to the filesystem. The following functions create the corresponding files:

  *  incident_state.json: Created and updated by the save_manual_telemetry function.
  *  incident_timeline.txt: Appended to by the update_incident_timeline function to maintain a chronological log of actions.
  *  notification_broadcast.log: Appended to by the send_external_notification function when broadcasting status updates.
  *  {report_type}_{uuid}.md (e.g., postmortem_report_{uuid}.md): Created by the archive_validated_report function, which saves the final postmortem report with a unique identifier.
