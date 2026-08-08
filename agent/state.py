"""Shared state passed between LangGraph nodes."""
from __future__ import annotations

from typing import Optional, TypedDict


class JobPosting(TypedDict, total=False):
    """Structured output of the Extract agent."""
    url: str
    title: str
    company: str
    location: str
    seniority: str
    required_skills: list[str]
    nice_to_have_skills: list[str]
    salary: Optional[str]
    raw_text: str
    source: str  # "linkedin" | "xing" | "indeed" - added 2026-08-08 (multi-source search)


class MatchResult(TypedDict, total=False):
    """Output of the Match agent for a single posting."""
    posting: JobPosting
    fit_score: Optional[float]  # 0-1, or None if no skills data was extracted to score against
    matched_skills: list[str]
    missing_skills: list[str]
    notes: str
    transferable_signals: list[str]  # profile.transferable_strengths that matched this
                                      # posting's text (adaptability/learning-agility/
                                      # generalist keywords) - kept separate from
                                      # fit_score's hard skill-overlap math, added
                                      # 2026-08-07 per Gurinder's instruction to weigh
                                      # readiness-to-learn/flexibility/adaptability,
                                      # since the pure skill-overlap scorer was giving
                                      # 0.0 fit to postings that explicitly value these
                                      # traits but don't list them as "skills".


class Briefing(TypedDict, total=False):
    """SITREP-style output of the Brief-writer agent, mirrors the Ops Intel
    Agent's Situation/Assessment/Recommendation briefing contract."""
    situation: str
    assessment: str
    recommendation: str
    sources: list[str]
    no_data_warning: Optional[str]


class AgentState(TypedDict, total=False):
    # input
    query: str          # keywords only, e.g. "Data Analyst" - NOT "Data Analyst Berlin"
    location: str       # e.g. "Berlin, Germany" - kept separate from query.
                         # Real bug found running this live (2026-08-06): folding
                         # location into the free-text query got it silently
                         # ignored by LinkedIn's public search, returning mostly
                         # US postings for a "Data Analyst Berlin" query. Splitting
                         # it into its own URL param fixed it - see search.py.
    max_results: int
    seniority: str       # "" | "any" | "entry" | "mid" | "senior" | "lead" - added 2026-08-08.
                          # Filtered pre-Extract in search_node, not post-briefing - see
                          # agent/tools/seniority.py for why.
    brief_limit: int    # how many of the fetched postings actually go through
                         # Extract/Match/Brief-writer (the expensive LLM stages).
                         # Real bug found 2026-08-07: job_intel_search_and_brief
                         # timed out through the Claude Desktop MCP client because
                         # the actor's minimum count=10 meant up to 20 sequential
                         # Claude calls (10 extract + 10 brief) - way past a normal
                         # MCP request timeout. search still fetches max_results
                         # postings; only the top brief_limit get the full pipeline.

    # Search -> Extract
    raw_postings: list[dict]

    # Extract -> Match
    postings: list[JobPosting]

    # Match -> Brief-writer
    match_results: list[MatchResult]

    # Brief-writer output
    briefings: list[Briefing]

    # error accumulation (each node appends here instead of raising, so a
    # single bad posting doesn't kill the whole run)
    errors: list[str]
