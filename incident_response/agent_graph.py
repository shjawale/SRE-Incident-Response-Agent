import os
import asyncio
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from agent import root_agent 

# Import the core Runner and Session Service alongside native GenAI types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# 1. Define the LangGraph State
class SREState(TypedDict):
    incident_data: str
    final_report: str

# 2. Define the orchestration Node wrapping your giant agent
def execution_node(state: SREState):
    session_service = InMemorySessionService()
    
    runner = Runner(
        app_name="SRE_Triage_App",
        agent=root_agent,
        session_service=session_service
    )
    
    user_message = types.Content(
        role="user", 
        parts=[types.Part(text=state["incident_data"])]
    )
    
    async def init_and_run_async():
        # Establish the session context in memory
        await session_service.create_session(
            app_name="SRE_Triage_App",
            user_id="sre_graph_user",
            session_id="GRAPH-SESSION"
        )
        
        response_text = ""
        
        # **CRITICAL FIX**: Replaced 'runner.run' with 'runner.run_async' to support tool-loop streams natively
        async for event in runner.run_async(
            new_message=user_message, 
            user_id="sre_graph_user", 
            session_id="GRAPH-SESSION"
        ):
            chunk = ""
            # Inspect the incoming event structure for text
            if hasattr(event, 'text') and event.text:
                chunk = event.text
            elif hasattr(event, 'content') and hasattr(event.content, 'parts') and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        chunk += part.text
            
            if chunk:
                response_text += chunk
                
        return response_text

    # Execute the asynchronous generator flow safely inside LangGraph's execution thread
    try:
        final_output_text = asyncio.run(init_and_run_async())
    except Exception as inner_err:
        import sys
        print(f"INNER ADK RUNNER CRASH: {inner_err}", file=sys.stderr)
        final_output_text = f"ADK Runner Pipeline Error: {str(inner_err)}"
            
    return {"final_report": final_output_text}

# 3. Compile the Graph
workflow = StateGraph(SREState)
workflow.add_node("sre_commander", execution_node)

workflow.add_edge(START, "sre_commander")
workflow.add_edge("sre_commander", END)

sre_graph = workflow.compile()

