from typing import TypedDict, List, Optional

class SREAgentState(TypedDict):
    incident_data: str
    session_id: str
    status: str
    triage_report: Optional[str]
    found_runbooks: Optional[List[dict]]
    suggested_steps: Optional[str]
    incident_id: Optional[str]
    approval_granted: Optional[bool]
    remediation_logs: Optional[str]

