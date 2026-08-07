"""MCP server wrapping the Job Intelligence Agent, mirroring the Ops Intel
Agent's mcp_server/ pattern - pure glue over agent.graph and agent.tools, no
reimplementation.

SDK gotcha (same one already found and fixed in the Ops Intel Agent, verified
again here 2026-08-06): the installed `mcp` PyPI package (2.0.0) has renamed
FastMCP to MCPServer and moved it from mcp.server.fastmcp to
mcp.server.mcpserver. Most tutorials still document the old path, which does
not exist in this version.

Tools:
- job_intel_search_and_brief: full pipeline (Search -> Extract -> Match ->
  Brief-writer). Slower, costs Anthropic + Apify usage, but gives real
  SITREP-style briefings.
- job_intel_search_postings: Search agent only, no LLM calls. Fast, cheap,
  useful when you just want raw postings.
- job_intel_get_profile: read-only passthrough of the loaded profile, useful
  for confirming what the Match agent is actually scoring against.
"""
from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from agent.agents.match import _load_profile
from agent.graph import run as run_pipeline
from agent.tools.apify_tools import search_job_postings

server = MCPServer("job-intelligence-agent")


class SearchAndBriefInput(BaseModel):
    query: str = Field(description="Job title / keywords, e.g. 'Data Analyst'. Do NOT include location here.")
    location: str = Field(default="", description="e.g. 'Berlin, Germany'. Kept separate from query - see search.py for why.")
    max_results: int = Field(default=10, ge=10, description="Actor enforces a minimum of 10.")


class SearchOnlyInput(BaseModel):
    query: str = Field(description="Job title / keywords, e.g. 'Data Analyst'.")
    location: str = Field(default="", description="e.g. 'Berlin, Germany'.")
    max_results: int = Field(default=10, ge=10)


@server.tool(annotations=ToolAnnotations(read_only_hint=False))  # calls Anthropic + Apify, costs API spend
def job_intel_search_and_brief(params: SearchAndBriefInput) -> str:
    """Runs the full Job Intelligence Agent pipeline: searches LinkedIn for
    matching postings, extracts structured requirements, scores them against
    Gurinder's profile, and writes a SITREP-style briefing per posting.

    Use this for "find me jobs matching X" - for raw postings without the
    LLM synthesis, use job_intel_search_postings instead (faster, cheaper).
    """
    result = run_pipeline(params.query, params.max_results, params.location)
    return json.dumps(
        {
            "briefings": result.get("briefings", []),
            "match_count": len(result.get("match_results", [])),
            "errors": result.get("errors", []),
        }
    )


@server.tool(annotations=ToolAnnotations(read_only_hint=True))
def job_intel_search_postings(params: SearchOnlyInput) -> str:
    """Raw LinkedIn job search only - no extraction, matching, or briefing.
    Fast and cheap (no Anthropic calls). Use when you just need listings."""
    items = search_job_postings(params.query, params.max_results, params.location)
    return json.dumps(items)


@server.tool(annotations=ToolAnnotations(read_only_hint=True))
def job_intel_get_profile() -> str:
    """Returns the profile the Match agent currently scores postings against.
    Read-only, no LLM/API calls."""
    return json.dumps(_load_profile())


if __name__ == "__main__":
    server.run()
