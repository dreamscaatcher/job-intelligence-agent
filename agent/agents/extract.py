"""Extract agent node: turns raw postings (from curious_coder/linkedin-jobs-scraper,
see apify_tools.py) into structured JobPosting records.

Field mapping verified against a live actor run on 2026-08-06 (raw item keys:
id, trackingId, refId, link, title, companyName, companyLinkedinUrl,
companyLogo, location, postedAt, benefits, descriptionHtml, applicantsCount,
applyUrl, salary, descriptionText, seniorityLevel, employmentType,
jobFunction, industries, ...). title/company/location/seniority/salary/url
are already structured on the raw item, so they're copied directly rather
than re-derived by an LLM. Only required_skills/nice_to_have_skills are
genuinely unstructured (buried in descriptionText prose) and need a Claude
call to pull out."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

from agent.config import settings
from agent.llm_utils import parse_json_response
from agent.state import AgentState, JobPosting

MAX_WORKERS = 5  # bounded concurrency, not unlimited - stay polite to the Anthropic API

SKILLS_SYSTEM_PROMPT = """You extract skill requirements from a job posting description.
Return ONLY valid JSON, no prose: {"required_skills": [str], "nice_to_have_skills": [str]}
Use short skill/technology names (e.g. "Python", "SQL", "Power BI"), not full sentences.
Only include skills actually mentioned in the text. Do not invent skills that aren't there."""


def _extract_skills(client: anthropic.Anthropic, description_text: str) -> dict:
    if not description_text.strip():
        return {"required_skills": [], "nice_to_have_skills": []}
    resp = client.messages.create(
        model=settings.model_name,
        max_tokens=1024,
        system=SKILLS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": description_text[:8000]}],
    )
    return parse_json_response(resp.content[0].text)


def _extract_one(client: anthropic.Anthropic, raw: dict) -> JobPosting:
    description_text = raw.get("descriptionText", "") or ""
    skills = _extract_skills(client, description_text)

    return {
        "url": raw.get("link") or raw.get("applyUrl", ""),
        "title": raw.get("title", ""),
        "company": raw.get("companyName", ""),
        "location": raw.get("location", ""),
        "seniority": raw.get("seniorityLevel", ""),
        "required_skills": skills.get("required_skills", []),
        "nice_to_have_skills": skills.get("nice_to_have_skills", []),
        "salary": raw.get("salary") or None,
        "raw_text": description_text,
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
