"""Brief-writer agent node: synthesizes a SITREP-style briefing per matched
job (Situation / Assessment / Recommendation), mirroring the Ops Intel
Agent's briefing contract.

Real bug found by eval/judge.py's faithfulness check (2026-08-06, case
berlin_ai_engineer): a posting listing "San Francisco (US) or Berlin (GER)"
got collapsed to just "in Berlin" in the situation field - a real factual
distortion, not a hallucination out of nowhere, but a lossy paraphrase the
judge correctly flagged. Fixed with an explicit instruction below."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

from agent.config import settings
from agent.llm_utils import parse_json_response
from agent.state import AgentState, Briefing

MAX_WORKERS = 5

BRIEF_SYSTEM_PROMPT = """You write a SITREP-style briefing for a job match.
Return ONLY valid JSON matching this schema, no prose:
{
  "situation": str,       // what the posting says, factually
  "assessment": str,      // fit given the match data provided - name specific
                           // matched/missing skills, don't generalize
  "recommendation": str,  // apply as-is / tailor resume how / skip, and why
  "sources": [str],       // the posting URL(s) used
  "no_data_warning": str | null
}
Only use the match data given to you. Do not invent skills, experience, or
posting details not present in the input. If the posting lists multiple
possible locations (e.g. "San Francisco (US) or Berlin (GER)"), state all of
them in "situation" - do not collapse a multi-location posting down to just
one city.

If the input includes a non-empty "transferable_signals" list, treat those
as real, evidence-backed context (readiness to learn / adaptability /
cross-domain problem-solving) and weave them into "assessment" alongside
the hard skill overlap - do not ignore them just because they aren't
technical skills. But do not let them override an honest read of a low
fit_score: a strong adaptability signal on a role requiring years of
specific technical depth the candidate doesn't have is still a "tailor
carefully or skip" case, not an "apply" case - say so plainly rather than
inflating the recommendation. If "transferable_signals" is empty or
absent, don't mention it."""


def _write_one(client: anthropic.Anthropic, match_result: dict) -> Briefing:
    resp = client.messages.create(
        model=settings.model_name,
        max_tokens=1024,
        system=BRIEF_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(match_result)}],
    )
    return parse_json_response(resp.content[0].text)


def brief_writer_node(state: AgentState) -> AgentState:
    match_results = state.get("match_results", [])
    errors = list(state.get("errors", []))
    briefings: list[Briefing] = []

    if not settings.anthropic_api_key:
        errors.append("brief_writer_node: ANTHROPIC_API_KEY not set")
        return {**state, "briefings": briefings, "errors": errors}

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    # Parallelized 2026-08-07 alongside extract_node - same timeout root cause.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_to_mr = {pool.submit(_write_one, client, mr): mr for mr in match_results}
        for future in as_completed(future_to_mr):
            try:
                briefings.append(future.result())
            except Exception as e:  # noqa: BLE001
                errors.append(f"brief_writer_node: failed on one match: {e}")

    return {**state, "briefings": briefings, "errors": errors}
