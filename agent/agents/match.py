"""Match agent node: scores each JobPosting against the user's Profile.

Requires agent/profile/profile.json to exist with real content (see
ADR-0001 open item 2 - no current AI/tech resume was found in Drive during
scaffolding, so profile.example.json is a placeholder schema only)."""
from __future__ import annotations

import json

from agent.config import settings
from agent.state import AgentState, MatchResult


def _load_profile() -> dict:
    settings.require_profile()
    return json.loads(settings.profile_path.read_text())


def _detect_transferable_signals(posting: dict, profile: dict) -> list[str]:
    """Scans posting text for keywords tied to profile.transferable_strengths
    (adaptability, readiness to learn, cross-domain/generalist problem-solving).

    Added 2026-08-07 per Gurinder's instruction to add these traits "to the
    mix" - the pure hard-skill overlap in _score_posting was returning 0.0
    fit_score for postings that explicitly ask for adaptability/comfort with
    ambiguity/fast learners (e.g. the Beam AI EIR posting listed "comfort
    with ambiguity and fast-paced environments" as a requirement), because
    those traits aren't "skills" in the technical sense _score_posting
    matches on. Deliberately kept as a SEPARATE field from fit_score rather
    than blended into it - inflating the hard-skill number would repeat the
    exact mistake fixed in the fit_score=None case (fabricated confidence).
    This is a keyword scan, not an LLM judgment call - it can false-negative
    on paraphrased requirements, but won't fabricate a match that isn't
    textually present."""
    haystack = " ".join(
        [
            posting.get("title", ""),
            posting.get("raw_text", ""),
            " ".join(posting.get("required_skills", [])),
            " ".join(posting.get("nice_to_have_skills", [])),
        ]
    ).lower()

    signals = []
    for strength in profile.get("transferable_strengths", []):
        keywords = strength.get("keywords", [])
        if any(kw.lower() in haystack for kw in keywords):
            signals.append(f"{strength.get('label', '')}: {strength.get('evidence', '')}")
    return signals


def _score_posting(posting: dict, profile: dict) -> MatchResult:
    posting_skills = {
        s.lower()
        for s in (posting.get("required_skills", []) + posting.get("nice_to_have_skills", []))
    }
    profile_skills = {
        s.lower()
        for group in profile.get("skills", {}).values()
        for s in group
    }

    matched = sorted(posting_skills & profile_skills)
    missing = sorted(posting_skills - profile_skills)
    transferable_signals = _detect_transferable_signals(posting, profile)

    notes = "Skill-overlap score only (no LLM judgment yet)."
    if profile.get("_comment"):
        notes += " Placeholder profile in use."

    if not posting_skills:
        # Real bug found running the eval harness (2026-08-06): scoring an
        # empty skills list as fit_score=0.0 silently conflated "no skills
        # data extracted" with "zero match" - the Brief-writer then presented
        # that as a confident negative assessment for postings that just had
        # a sparse description, not an actual bad fit. None + a note is
        # honest about what's actually known.
        fit_score = None
        notes += " No skills extracted from this posting - fit score not computable, review manually."
    else:
        fit_score = round(len(matched) / len(posting_skills), 2)

    return {
        "posting": posting,
        "fit_score": fit_score,
        "matched_skills": matched,
        "missing_skills": missing,
        "notes": notes,
        "transferable_signals": transferable_signals,
    }


def match_node(state: AgentState) -> AgentState:
    postings = state.get("postings", [])
    errors = list(state.get("errors", []))

    try:
        profile = _load_profile()
    except RuntimeError as e:
        errors.append(f"match_node: {e}")
        return {**state, "match_results": [], "errors": errors}

    match_results = [_score_posting(p, profile) for p in postings]
    return {**state, "match_results": match_results, "errors": errors}
