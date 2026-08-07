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

import anthropic

from agent.config import settings
from agent.llm_utils import parse_json_response
from agent.state import AgentState, JobPosting

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
    errors = list(state.get("errors", []))
    postings: list[JobPosting] = []

    if not settings.anthropic_api_key:
        errors.append("extract_node: ANTHROPIC_API_KEY not set")
        return {**state, "postings": postings, "errors": errors}

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    for raw in raw_postings:
        try:
            postings.append(_extract_one(client, raw))
        except Exception as e:  # noqa: BLE001 - one bad posting shouldn't kill the run
            errors.append(f"extract_node: failed on one posting: {e}")

    return {**state, "postings": postings, "errors": errors}
