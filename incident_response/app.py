import streamlit as st
import asyncio
import uuid
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from agent import root_agent


SHARED_USER_ID = "sre_agent_app"
APP_NAME = "SRE_Triage_App"

if "session_service" not in st.session_state:
    st.session_state.session_service = InMemorySessionService()

if "runner" not in st.session_state:
    st.session_state.runner = Runner(
        app_name=APP_NAME,
        agent=root_agent,
        session_service=st.session_state.session_service,
    )

runner = st.session_state.runner

if "session_id" not in st.session_state:
    st.session_state.session_id = f"INC-{uuid.uuid4().hex[:8].upper()}"

    asyncio.run(
        st.session_state.session_service.create_session(
            app_name=APP_NAME,
            user_id=SHARED_USER_ID,
            session_id=st.session_state.session_id,
        )
    )

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

# Age out old messages to limit memory (keep last 20 messages per session)
MAX_MESSAGES_PER_SESSION = 20
if len(st.session_state.messages) > MAX_MESSAGES_PER_SESSION:
    st.session_state.messages = st.session_state.messages[-MAX_MESSAGES_PER_SESSION:]

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

full_text = ""
# User Input
if prompt := st.chat_input("Describe the incident (e.g., 'Payment service 503 errors')"):
    # Display User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Agent Processing
    with st.chat_message("assistant"):
        response_placeholder = st.empty()  # Create an empty container for the text
        
        # Create a content object with the required 'user' role
        user_content = types.Content(
            role="user",
            parts=[types.Part(text=prompt)]
        )

        def stream_response():
            response_parts = []
            # Use the persisted session_id
            for event in runner.run(
                new_message=user_content,
                user_id=SHARED_USER_ID,
                session_id=st.session_state.session_id
            ):
                # ADK events usually carry text in .text or .content
                chunk = ""
                if hasattr(event, 'text') and event.text:
                    chunk = event.text

                elif hasattr(event, 'content') and event.content and event.content.parts:
                    for part in event.content.parts:
                        if getattr(part, "text", None):
                            chunk += part.text

                        elif getattr(part, "function_call", None):
                            print(f"Agent is calling tool: {part.function_call.name}"
            )
                
                # Update UI only if we actually found text
                if chunk:
                    response_parts.append(chunk)
                    full_text = ''.join(response_parts)
                    response_placeholder.markdown(full_text + "▌")
                
                # DEBUG: Print to your terminal so you can see if tools are running
                print(f"ADK Event Received: {type(event)}")
            
            return ''.join(response_parts)

        # Execute the async function within the sync Streamlit flow
        final_response = stream_response()
        
        if final_response:
            response_placeholder.markdown(final_response)
            st.session_state.messages.append({"role": "assistant", "content": final_response})
        else:
            response_placeholder.error("Agent returned an empty response. Check terminal for tool-call logs.")
