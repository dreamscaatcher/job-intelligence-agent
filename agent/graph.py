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


def run(query: str, max_results: int = 20, location: str = "", brief_limit: int = 3, seniority: str = "") -> AgentState:
    """brief_limit defaults to 3, not max_results - see state.py's comment on
    why (MCP client timeout hit running the full 10-posting pipeline live
    2026-08-07). Dropped from an initial 5 to 3 after the Search stage alone
    proved to have real, LinkedIn-retry-driven variance (22-90s observed
    across runs, outside this code's control) - 3 leaves more margin against
    a slow Search run still blowing the total past a client timeout. Set
    brief_limit=max_results to brief every fetched posting, at the cost of a
    much longer and less predictable run.

    seniority ("" | "any" | "entry" | "mid" | "senior" | "lead") is applied
    in search_node, before the brief_limit slice - see
    agent/tools/seniority.py."""
    app = build_graph()
    initial_state: AgentState = {
        "query": query,
        "location": location,
        "max_results": max_results,
        "seniority": seniority,
        "brief_limit": brief_limit,
        "errors": [],
    }
    return app.invoke(initial_state)
