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


class MatchResult(TypedDict, total=False):
    """Output of the Match agent for a single posting."""
    posting: JobPosting
    fit_score: Optional[float]  # 0-1, or None if no skills data was extracted to score against
    matched_skills: list[str]
    missing_skills: list[str]
    notes: str


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
