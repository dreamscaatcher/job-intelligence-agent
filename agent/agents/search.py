"""Search agent node: fetches raw job postings via Apify."""
from __future__ import annotations

from agent.state import AgentState
from agent.tools.apify_tools import search_job_postings


def search_node(state: AgentState) -> AgentState:
    query = state["query"]
    location = state.get("location", "")
    max_results = state.get("max_results", 20)
    errors = list(state.get("errors", []))

    try:
        raw_postings = search_job_postings(query, max_results, location=location)
    except RuntimeError as e:
        # Not configured yet (no Apify token/actor) - fail into state, not an
        # exception, so the graph can still return a clear error instead of
        # crashing the whole run.
        errors.append(f"search_node: {e}")
        raw_postings = []

    return {**state, "raw_postings": raw_postings, "errors": errors}
