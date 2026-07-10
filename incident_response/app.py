import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core")

import streamlit as st
import asyncio
import uuid
import sys
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from agent import root_agent

SHARED_USER_ID = "sre_agent_app"
APP_NAME = "SRE_Triage_App"

# Cache the session service and runner to avoid recreating on every rerun
@st.cache_resource
def get_session_service():
    service = InMemorySessionService()
    service.max_sessions = 10  
    return service

@st.cache_resource
def get_runner(_session_service):
    return Runner(
        app_name=APP_NAME,
        agent=root_agent, 
        session_service=_session_service
    )


# Initialize the Session Service (Global for the app)
if "session_service" not in st.session_state:
    st.session_state.session_service = get_session_service()

if "session_id" not in st.session_state:
    st.session_state.session_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    
    async def create_new_session():
        await st.session_state.session_service.create_session(
            app_name=APP_NAME,
            user_id=SHARED_USER_ID,
            session_id=st.session_state.session_id
        )
    asyncio.run(create_new_session())

# Setup the Runner
runner = get_runner(st.session_state.session_service)

# Page Configuration
st.set_page_config(page_title="SRE Triage Dashboard", layout="wide")
st.title("SRE Incident Response Agent")
st.write("Enter a description of your incident to get started.")
st.divider()

if "agent" not in st.session_state:
    st.session_state.agent = root_agent

# Initialize Session State for Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

# Age out old messages to limit memory
MAX_MESSAGES_PER_SESSION = 20
if len(st.session_state.messages) > MAX_MESSAGES_PER_SESSION:
    st.session_state.messages = st.session_state.messages[-MAX_MESSAGES_PER_SESSION:]

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


if prompt := st.chat_input("Describe the incident (e.g., 'Payment service 503 errors')"):
    # Display User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Agent Processing Block
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        
        # Move your LangGraph compilation calls strictly inside this scoped execution loop
        from agent_graph import sre_graph
        inputs = {"incident_data": prompt}

        with st.spinner("LangGraph state machine executing the multi-agent system..."):
            try:
                # Execute the wrapped ADK pipeline through LangGraph
                result = sre_graph.invoke(inputs)
                final_response = result.get("final_report", "")
            except Exception as e:
                st.error(f"Execution failed: {str(e)}")
                final_response = ""
        
        if final_response:
            response_placeholder.markdown(final_response)
            st.session_state.messages.append({"role": "assistant", "content": final_response})
        else:
            response_placeholder.error("Agent returned an empty response. Check your terminal logs for details.")
