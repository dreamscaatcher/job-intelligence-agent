"""LangGraph wiring: Search -> Extract -> Match -> Brief-writer, linear."""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from agent.agents.brief_writer import brief_writer_node
from agent.agents.extract import extract_node
from agent.agents.match import match_node
from agent.agents.search import search_node
from agent.state import AgentState


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("search", search_node)
    graph.add_node("extract", extract_node)
    graph.add_node("match", match_node)
    graph.add_node("brief_writer", brief_writer_node)

    graph.set_entry_point("search")
    graph.add_edge("search", "extract")
    graph.add_edge("extract", "match")
    graph.add_edge("match", "brief_writer")
    graph.add_edge("brief_writer", END)

    return graph.compile()


def run(query: str, max_results: int = 20, location: str = "") -> AgentState:
    app = build_graph()
    initial_state: AgentState = {
        "query": query,
        "location": location,
        "max_results": max_results,
        "errors": [],
    }
    return app.invoke(initial_state)
