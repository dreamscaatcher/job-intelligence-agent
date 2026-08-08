"""Seniority filtering for the Search agent (2026-08-08).

Applied BEFORE the brief_limit slice in extract_node, not after briefing -
seniority is only reliably known post-Extract (LLM-inferred for Xing/Indeed,
see extract.py), but extract_node truncates raw_postings to brief_limit
*before* extraction runs. Filtering after the fact would mean a low
brief_limit (3, per the MCP timeout tuning) could return zero results even
when matches exist in the wider fetched pool - filtering here, on the raw
pool, avoids that.

Because this runs pre-Extract, it can't use the LLM-inferred seniority
extract.py produces. LinkedIn's raw items carry a real structured
`seniorityLevel` field (e.g. "Entry level", "Mid-Senior level", "Director"),
which is used when present. Xing and Indeed don't expose anything usable
pre-extraction (same opaque-taxonomy-code problem documented in
apify_tools.py), so for those two - and as a LinkedIn fallback when
seniorityLevel is empty/"Not Applicable" - this falls back to a keyword scan
of the posting title. This is a real, named approximation, not a hidden one:
a posting with no seniority word in its title (common - plenty of "Data
Analyst" postings are entry-level without saying so) is kept rather than
dropped, on the theory that silently losing an unlabeled-but-relevant
posting is worse than occasionally showing one that doesn't match the
filter. Only a title that clearly signals a *different* bucket gets
excluded.
"""
from __future__ import annotations

BUCKETS = {
    "entry": ["entry level", "entry-level", "junior", "graduate", "intern", "internship", "trainee", "working student", "werkstudent"],
    "mid": ["mid level", "mid-level", "mid-senior", "associate"],
    "senior": ["senior", "sr.", "sr "],
    "lead": ["lead", "principal", "staff", "head of", "director", "manager", "vp ", "vice president", "chief"],
}

# LinkedIn's own seniorityLevel vocabulary, mapped onto the same buckets.
_LINKEDIN_MAP = {
    "internship": "entry",
    "entry level": "entry",
    "associate": "mid",
    "mid-senior level": "senior",
    "director": "lead",
    "executive": "lead",
}


def _bucket_from_text(text: str) -> str | None:
    text_lower = text.lower()
    for bucket, keywords in BUCKETS.items():
        if any(kw in text_lower for kw in keywords):
            return bucket
    return None


def _posting_bucket(item: dict) -> str | None:
    """Best-effort bucket for a normalized raw posting item. Returns None if
    no signal is found (title has no recognizable seniority keyword and
    there's no usable structured field) - callers should treat None as
    "unknown, don't exclude" rather than "no match"."""
    structured = (item.get("seniorityLevel") or "").strip().lower()
    if structured and structured != "not applicable":
        mapped = _LINKEDIN_MAP.get(structured)
        if mapped:
            return mapped
    return _bucket_from_text(item.get("title", ""))


def filter_by_seniority(items: list[dict], seniority: str) -> list[dict]:
    """seniority: one of "entry"/"mid"/"senior"/"lead", or "" / "any" for no filtering."""
    bucket = (seniority or "").strip().lower()
    if not bucket or bucket == "any":
        return items
    if bucket not in BUCKETS:
        return items  # unrecognized filter value - fail open rather than silently returning nothing

    kept = []
    for item in items:
        posting_bucket = _posting_bucket(item)
        if posting_bucket is None or posting_bucket == bucket:
            kept.append(item)
    return kept
