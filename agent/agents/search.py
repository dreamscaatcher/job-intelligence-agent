"""Search agent node: fetches raw job postings via Apify.

Multi-source as of 2026-08-08 (was LinkedIn-only) - see apify_tools.py's
module docstring for why and how. search_all_sources runs LinkedIn/Xing/
Indeed in parallel and returns (items, errors); a single source failing
(rate limit, actor error) doesn't fail the whole search."""
from __future__ import annotations

from agent.state import AgentState
from agent.tools.apify_tools import search_all_sources


def search_node(state: AgentState) -> AgentState:
    query = state["query"]
    location = state.get("location", "")
    max_results = state.get("max_results", 20)
    errors = list(state.get("errors", []))

    try:
        raw_postings, source_errors = search_all_sources(query, max_results, location=location)
        errors.extend(source_errors)
    except RuntimeError as e:
        # Not configured yet (no Apify token/actor) - fail into state, not an
        # exception, so the graph can still return a clear error instead of
        # crashing the whole run.
        errors.append(f"search_node: {e}")
        raw_postings = []

    return {**state, "raw_postings": raw_postings, "errors": errors}
