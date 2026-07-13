from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from state import SREAgentState
from agent import triage_node, knowledge_node, persistence_node, remediation_node

workflow = StateGraph(SREAgentState)

workflow.add_node("triage", triage_node)
workflow.add_node("knowledge", knowledge_node)
workflow.add_node("persistence", persistence_node)
workflow.add_node("remediation", remediation_node)

workflow.add_edge(START, "triage")
workflow.add_edge("triage", "knowledge")
workflow.add_edge("knowledge", "persistence")
workflow.add_edge("persistence", "remediation")
workflow.add_edge("remediation", END)

memory = MemorySaver()
sre_graph = workflow.compile(
    checkpointer=memory,
    interrupt_after=["persistence"]
)
