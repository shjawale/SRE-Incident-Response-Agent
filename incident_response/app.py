import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core")

import streamlit as st
import random
from agent_graph import sre_graph

st.set_page_config(page_title="SRE Triage Dashboard", layout="wide")
st.title("SRE Incident Orchestrator")
st.divider()

if "session_id" not in st.session_state:
    st.session_state.session_id = f"INC-{random.randint(1000, 9999)}"

config = {"configurable": {"thread_id": st.session_state.session_id}}
current_state = sre_graph.get_state(config)

if not current_state.values:
    prompt = st.text_area("Describe the incoming active production incident alert details:", height=150)
    if st.button("Trigger Automation Flow Pipeline", type="primary") and prompt:
        inputs = {"incident_data": prompt, "session_id": st.session_state.session_id, "status": "INITIALIZED"}
        with st.spinner("Executing automated Triage & Runbook Lookup phases..."):
            sre_graph.invoke(inputs, config=config)
        st.rerun()
else:
    values = current_state.values
    next_steps = current_state.next
    
    st.subheader(f"Live Incident State Machine [{st.session_state.session_id}]")
    if values.get("incident_id"):
        st.metric(label="Registered Incident ID", value=values["incident_id"])
        
    col1, col2 = st.columns(2)
    with col1:
        if values.get("triage_report"):
            st.markdown(f"### Automated Triage Report\n{values['triage_report']}")
    with col2:
        if values.get("suggested_steps"):
            st.markdown(f"### Matched Runbook Mitigation Steps\n{values['suggested_steps']}")
            
    if "remediation" in next_steps:
        st.error("CRITICAL: Destructive automated environment modification requires human approval.")
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("Approve Infrastructure Remediation", type="primary", use_container_width=True):
                sre_graph.update_state(config, {"approval_granted": True}, as_node="persistence")
                sre_graph.invoke(None, config=config)
                st.rerun()
        with btn_col2:
            if st.button("Reject Infrastructure Remediation", use_container_width=True):
                sre_graph.update_state(config, {"approval_granted": False}, as_node="persistence")
                sre_graph.invoke(None, config=config)
                st.rerun()
    else:
        st.divider()
        st.success(f"🎉 Pipeline process finalized. System Status: {values.get('status')}")
        st.code(values.get("remediation_logs", "No logs returned."), language="text")
        if st.button("Process New Incident"):
            del st.session_state.session_id
            st.rerun()
