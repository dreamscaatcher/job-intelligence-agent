"""Extract agent node: turns raw postings into structured JobPosting records.

As of 2026-08-08, raw postings come from three sources (LinkedIn, Xing,
Indeed - see apify_tools.py), each normalized at the source layer to a
common shape (title/companyName/location/seniorityLevel/link/applyUrl/
salary/descriptionText/source) so this file doesn't need to know about three
different platform schemas. Field mapping originally verified against a live
LinkedIn actor run on 2026-08-06; Xing/Indeed schemas verified 2026-08-08 -
see apify_tools.py's module docstring for the real field names.
title/company/location/salary/url are already structured on the normalized
item, so they're copied directly rather than re-derived by an LLM.

Seniority (2026-08-08): LinkedIn's `seniorityLevel` is real structured text
and is trusted as-is when present. Xing (`career_level_id`, e.g. "3.2ebf16")
and Indeed (`attributes.*`/`jobTypes.*`, e.g. "attributes.75GKK") expose it
only as opaque hashed taxonomy codes with no public mapping and no guarantee
they're stable across queries - rather than guess at that mapping, seniority
for those two sources is inferred from the same title+description text the
skills extraction already reads, via the same Claude call (no second API
call, no extra latency). LinkedIn's own field always wins when non-empty, so
this LLM fallback only fires where the platform genuinely doesn't give us
usable structured data."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

from agent.config import settings
from agent.llm_utils import parse_json_response
from agent.state import AgentState, JobPosting

MAX_WORKERS = 5  # bounded concurrency, not unlimited - stay polite to the Anthropic API

EXTRACT_SYSTEM_PROMPT = """You extract structured requirements from a job posting.
Return ONLY valid JSON, no prose:
{"required_skills": [str], "nice_to_have_skills": [str], "seniority": str}
Use short skill/technology names (e.g. "Python", "SQL", "Power BI"), not full sentences.
Only include skills actually mentioned in the text. Do not invent skills that aren't there.
For "seniority", infer one short label from the title and text (e.g. "Entry-level",
"Junior", "Mid-level", "Senior", "Lead/Principal", "Internship"). If the posting gives
no real signal either way, return an empty string - do not guess."""


def _extract_skills_and_seniority(client: anthropic.Anthropic, title: str, description_text: str) -> dict:
    if not description_text.strip() and not title.strip():
        return {"required_skills": [], "nice_to_have_skills": [], "seniority": ""}
    content = f"Title: {title}\n\n{description_text[:8000]}"
    resp = client.messages.create(
        model=settings.model_name,
        max_tokens=1024,
        system=EXTRACT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    return parse_json_response(resp.content[0].text)


def _extract_one(client: anthropic.Anthropic, raw: dict) -> JobPosting:
    title = raw.get("title", "")
    description_text = raw.get("descriptionText", "") or ""
    extracted = _extract_skills_and_seniority(client, title, description_text)

    seniority = raw.get("seniorityLevel", "") or extracted.get("seniority", "")

    return {
        "url": raw.get("link") or raw.get("applyUrl", ""),
        "title": title,
        "company": raw.get("companyName", ""),
        "location": raw.get("location", ""),
        "seniority": seniority,
        "required_skills": extracted.get("required_skills", []),
        "nice_to_have_skills": extracted.get("nice_to_have_skills", []),
        "salary": raw.get("salary") or None,
        "raw_text": description_text,
        "source": raw.get("source", "unknown"),  # added 2026-08-08 - which platform this posting came from
    }  # type: ignore[return-value]


def extract_node(state: AgentState) -> AgentState:
    raw_postings = state.get("raw_postings", [])
    brief_limit = state.get("brief_limit")
    if brief_limit is not None:
        raw_postings = raw_postings[:brief_limit]

    errors = list(state.get("errors", []))
    postings: list[JobPosting] = []

    if not settings.anthropic_api_key:
        errors.append("extract_node: ANTHROPIC_API_KEY not set")
        return {**state, "postings": postings, "errors": errors}

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    # Parallelized 2026-08-07: sequential calls were the main contributor to
    # job_intel_search_and_brief timing out through the Claude Desktop MCP
    # client (up to 10 extract + 10 brief calls run one at a time). Each
    # posting is independent, so there's no ordering requirement to preserve
    # here beyond collecting results.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_to_raw = {pool.submit(_extract_one, client, raw): raw for raw in raw_postings}
        for future in as_completed(future_to_raw):
            try:
                postings.append(future.result())
            except Exception as e:  # noqa: BLE001 - one bad posting shouldn't kill the run
                errors.append(f"extract_node: failed on one posting: {e}")

    return {**state, "postings": postings, "errors": errors}
