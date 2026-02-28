# SRE Incident Response Agent
This system is an agentic workflow built with the Google Agent Development Kit (ADK). It automates SRE incident management using a multi-agent hierarchy to research, triage, remediate, and report on DevOps incidents. Complex reasoning tasks are powered by the mistral-nemo:12b model.

## Overview
This project automates the end-to-end incident response pipeline. The RootAgent acts as a central orchestrator, dynamically routing user alerts to specialized sub-agents based on the incident state.

Integration with ADK Web provides a graphical interface for real-time monitoring and human-in-the-loop (HITL) oversight, allowing visualization of agent reasoning paths, monitoring sub-agent handoffs, and manual approval of remediation steps

### Key Components
  *  Orchestration: A hierarchical routing model using the Agent class.
  *  LLM: mistral-nemo:12b powers complex triage, runbook generation, and remediation logic via LiteLlm.


## Architecture & Workflow

The system implements a deterministic, sequential incident-response architecture orchestrated by a central RootAgent. The RootAgent functions exclusively as an incident commander, coordinating specialized agents while enforcing execution order, safety constraints, and audit logging. It does not perform technical analysis directly.

### Incident Lifecycle
1. **Initialization and Scoping**

    The operator manually provides telemetry, logs, and other incident information to the RootAgent. If data is missing, the system will prompt the operator for required metrics. All actions are recorded in the incident timeline.

2. **Triage**

    Control is delegated to the TriageAgent, which analyzes logs, stack traces, and historical incidents. Data gaps are explicitly identified, and a concise triage report is produced.

3. **Runbook Generation**

    Based on triage findings, an internal mitigation runbook is generated for engineering use.

4. **Remediation**

    The RemediationAgent proposes corrective actions and categorizes them by risk. Low-risk actions may proceed automatically, while high-risk or destructive actions require human approval. Post-action validation is mandatory.

5. **Verification and Closure**

    System stability is verified before declaring the incident resolved. Stakeholder notifications are issued for key state changes.

6. **Post-Incident Review and Archival**

    A blameless post-incident report is compiled and archived, formally closing the incident lifecycle.

### Architectural Principles

* Separation of responsibilities: Each agent performs a single, clearly defined function.
* Strict sequencing: Incident phases execute in a fixed, enforced order.
* Operational transparency: All actions are logged for traceability and review.
* Human authority: Final control over production changes remains with operators.



## Example Incident Flows

These examples illustrate typical incident lifecycles handled by the SRE Incident Response Agent, showing agent delegation, human-in-the-loop checkpoints, and reporting.

### Flow 1: Low-Risk Incident (Automatic Remediation)

1. **Initialization**: Operator provides logs, system metrics, and incident description to RootAgent.

2. **Triage**: TriageAgent analyzes the data and identifies a misconfigured cache.

3. **Knowledge**: KnowledgeAgent queries the MCP database to find similar historical incidents and known fixes.

4. **Runbook Generation**: RunbookAgent generates a mitigation runbook recommending a cache reset.

5. **Persistence**: PersistenceAgent generates a unique incident ID and saves any newly created runbooks back to the SQL database.

6. **Remediation**:

   * Action classified as low-risk → auto-approved.

   * RemediationAgent resets the cache automatically.

7. **Verification**: System metrics confirm latency normalized.

8. **Closure**: Incident is marked resolved; postmortem report archived.

Key Points: No human approval required; timeline fully logged for audit.

### Flow 2: High-Risk Incident (Human-in-the-Loop Required)

1. **Initialization**: Operator reports elevated error rates and provides logs to RootAgent.

2. **Triage**: TriageAgent identifies a misconfigured database failover as the root cause.

3. **Knowledge**: KnowledgeAgent queries the internal documentation and past incident logs to identify existing runbooks or similar historical failure patterns.

4. **Runbook Generation**: RunbookAgent produces a mitigation runbook with high-risk actions (e.g., manual failover).

5. **Persistence**: RunbookPersistenceAgent saves the newly generated or modified runbook to the database with a unique incident ID and a clear title for future reference.

6. **Remediation**:

    * High-risk action → requires operator approval.

    * RemediationAgent submits approval request with justification and risk assessment.

    * Operator reviews and approves execution.

7. **Execution**: Action is performed; agent validates database integrity.

8. **Verification & Closure**: Stability confirmed, stakeholders notified, postmortem compiled.

Key Points: HITL ensures operational safety; all decisions logged for compliance.


## Agent Roles
| Agent           |    Purpose
------------------|:---------------------
| TriageAgent     |  Analyzes incident data, identifies core issues, and flags data gaps.
| Knowledge Agent |  Queries the MCP Runbook database for historical fixes.
| RunbookAgent    |  Generates internal suggested runbooks for the engineering review.
| Persistence Agent | Ensures new runbooks are saved to the DB for future use.
| RemediationAgent |  Proposes fixes and actions, distinguishing between auto-tasks and manual rollbacks.
| PostmortemAgent  |  Compiles final internal post-incident reports and root cause analysis.
| StatusUpdateAgent  |  Formats status updates for both internal teams and external stakeholders.


## Human-in-the-Loop Safety

 The system enforces mandatory human authorization for any action that may materially impact service availability or infrastructure state. Autonomous execution of high-risk operations is explicitly prohibited.

### Approval Controls

Before execution, the RemediationAgent must invoke an approval request containing:

* The proposed action
* The technical and operational justification
* A timestamped approval record

### Execution Guarantees

* Agent execution is suspended while approval is pending.
* Agents are technically incapable of self-approving actions.
* Operator decisions are enforced as follows:
    * Approval granted → execution proceeds.
    * Approval denied → remediation halts immediately and a final report is generated.

No further actions are taken while approval remains unresolved.

The Human-in-the-Loop design enables controlled automation while preserving the reliability and governance standards required for production SRE operations.


## Model Context Protocol Runbook Server
Certain agents leverage a dedicated Model Context Protocol (MCP) Server to bridge the gap between the LLM and the runbooks database. This allows for standardized, secure, and context-rich tool execution. 

### Knowledge Retrieval & Persistence

   * ```search_runbooks```: Performs semantic search across historical incident records to find the most relevant past resolutions based on the current triage report.
   * ```save_runbook```: Automatically persists newly generated mitigation plans if no existing runbook matches the current incident.
   * Standardized Interface: Uses a unified protocol to interact with the SQLite backend, ensuring consistent data formatting and reducing the risk of SQL injection. 

### Configuration & Toolset
The orchestrator connects to the server via ```StdioConnectionParams```. Ensure the ```RUNBOOK_MCP_SERVER``` path points to the correct script in your environment:

```
McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="python3",
            args=[RUNBOOK_MCP_SERVER]        # should point to tools/runbook_mcp_server.py
        )
    ),
    tool_filter=["save_runbook"]
)
```

### Potential Extensions
   * Cross-Service Indexing: Scale the server to index runbooks across multiple git repositories or Confluence spaces using MCP-compatible connectors.
   * Vector Search: Integrate a vector database (e.g., ChromaDB or Pinecone) into the MCP server for advanced RAG-based similarity matching.
   * Schema Enforcement: Add strict Pydantic validation to the MCP tools to ensure all saved runbooks follow a mandatory "Symptoms/Fix/Verification" structure.


## Agent Governance & Safety
This orchestrator follows strict SRE "Human-in-the-Loop" (HITL) principles to prevent rogue automation and ensure blameless accountability.

### Implemented Guardrails
   * Mandatory Approval Gates: High-risk tools (e.g., execute_infrastructure_action) are programmatically locked. The agent must receive an approved payload via ToolContext before execution.
   * State-Aware Termination: If a human operator denies a request, the RemediationAgent is logic-bound to immediately halt all workflows to prevent system drift.
   * Immutable Audit Trail: Every agent decision and human intervention is appended to incident_timeline.txt, ensuring a non-repudiable log for Postmortems.

### Potential Extensions

   * RBAC Integration: Connect request_human_approval to an Identity Provider (IDP) to restrict approval authority to the active On-Call Lead.
   * Policy-as-Code: Integrate Open Policy Agent (OPA) to define "No-Fly Zones" (e.g., "Block restarts during peak traffic") that the agent checks before prompting a human.
   * Redaction Layer: Add a middleware tool to strip PII or secrets from logs before they are processed by the StatusUpdateAgent.


## Configuration & Installation
Prerequisites
   * Python 3.10+
   * Ollama: access to the mistral-nemo:12b model (or your chosen model).
   * LiteLLM: initializes an LLM instance allowing you to interact with a model.
   * MCP Server: provides a standardized interface for the agent to query and persist runbooks in the SQLite database.
   * Google Account (Optional): Only needed if you choose to deploy the agent to Google Cloud services like Vertex AI Agent Engine later. Local development with Ollama models does not require this setup.

### Setup
1. Clone the repository:
    ```
    git clone https://github.com/shjawale/SRE-Incident-Response-Agent.git
    cd sre-incident-agent
    ```

2. Install Ollama and the Mistral model:

    Download and install Ollama from the official website https://ollama.com/download/linux.
    
    Open your terminal or command prompt and run the following command to download the mistral model:
    ```
    ollama pull mistral-nemo:12b
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

## Usage

1. Direct Execution in Code

    To utilize the agents directly in code, instantiate the RootAgent and provide user queries regarding incidents. The RootAgent will manage the delegation to the appropriate sub-agent.
    python
    ```
    from google.adk.agents import Agent
    from google.adk.models.lite_llm import LiteLlm

    # LiteLLM automatically uses the local Ollama API for the 'ollama/mistral' model
    SRE_MODEL = LiteLlm(model="ollama/mistral-nemo:12b", api_base="http://localhost:11434")
    ```

2. Interactive UI via ADK Web

    For an enterprise-grade experience, you can launch the ADK Web interface to get traceability, agent monitoring, and human approval interfaces. Ensure your Ollama application is running in the background.

    To start the web interface, run:
    ```
    # Command to launch the ADK Web server
    python -m google.adk.web --agent root_agent
    ```

3. CLI Simulation

You can also run a local simulation of incidents in your terminal via Python. Run the following command from outside your agent directory.
```
python3 incident_response/agent.py
```

Follow the prompts to trigger incidents, run triage, apply remediation, and generate postmortems.


## Generated Files

When the agent is run locally, specific Python functions write various incident-related documents to the filesystem. The following functions create the corresponding files:

  *  ```incident_state.json```: Created and updated by the save_manual_telemetry function.
  *  ``incident_timeline.txt```: Appended to by the update_incident_timeline function to maintain a chronological log of actions.
  *  ```notification_broadcast.log```: Appended to by the send_external_notification function when broadcasting status updates.
  *  ```{report_type}_{uuid}.md``` (e.g., postmortem_report_{uuid}.md): Created by the archive_validated_report function, which saves the final postmortem report with a unique identifier.


## Development Notes
* Agents are orchestrated via SequentialAgent, enforcing strict stepwise execution. RootAgent delegates all technical work to sub-agents.
* Supports both CLI simulations (incident_response/agent.py) and interactive workflows via ADK Web.
* LLM interactions handled through LiteLlm, which interfaces with the local Ollama Mistral model.
* Human-in-the-Loop logic enforced in RemediationAgent: high-risk actions cannot execute without explicit operator approval.
* Incident data persists in JSON, text, and Markdown files (incident_state.json, incident_timeline.txt, {report_type}_{uuid}.md) for auditability.
* Virtual environments recommended (venv) to isolate dependencies.
* Logging is handled via the agents’ update functions; all actions are appended to the incident timeline.
* RootAgent never performs technical analysis directly; it orchestrates the other agents to perform specialized tasks.
