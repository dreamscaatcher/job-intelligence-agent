"""Apify integration for the Search agent - now multi-source (2026-08-08).

Originally LinkedIn-only. Extended to also search Xing (DACH-region
professional network) and Indeed (broad aggregator), per Gurinder's question
about why only LinkedIn was covered - a real, correct gap: the original
scoping (ADR-0001) picked one actor and moved on without evaluating
alternatives.

Actors, chosen the same way the LinkedIn one was (highest usage/rating on
the Apify Store, verified via the API, not guessed):
- LinkedIn: curious_coder/linkedin-jobs-scraper (id hKByXkMQaC5Qt9UMN)
- Xing: shahidirfan/Xing-Jobs-Scraper - 634 users, 4.45* (10 reviews), 99.8%
  success - next-closest Xing actor had under half the usage.
- Indeed: valig/indeed-jobs-scraper - 22,393 users, 5.0* (16 reviews), 99.9%
  success - edges out the next-closest (borderline/indeed-scraper, 20,302
  users, 4.58*) on both axes.

Design: each source has its own actor-input builder and a normalizer that
maps that platform's real (API-verified) output fields onto a common shape
matching what extract.py already expects from the original LinkedIn raw
items (title/companyName/location/seniorityLevel/link/applyUrl/salary/
descriptionText), plus a new `source` tag. This means extract.py needed
only a one-line change (passing `source` through) rather than learning
three different schemas itself.

Known limitations, found during schema verification (not guessed):
- Xing's `career_level_id` (e.g. "3.2ebf16") and Indeed's `attributes.*` /
  `jobTypes.*` fields are opaque hashed taxonomy codes, not human-readable
  strings, and aren't guaranteed stable across queries. Left unmapped
  (seniorityLevel="") rather than risk a wrong/fragile mapping - the Extract
  agent's existing LLM skill-extraction pass over descriptionText is where
  any seniority signal actually gets picked up for these two sources.
- Indeed's baseSalary.min/max/currencyCode were null on every sample item
  checked during verification - salary data appears to be sparse/inconsistent
  on Indeed specifically, not a bug in this integration.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode

from apify_client import ApifyClient

from agent.config import settings

XING_ACTOR_ID = "shahidirfan/Xing-Jobs-Scraper"
INDEED_ACTOR_ID = "valig/indeed-jobs-scraper"


def _dataset_id(run) -> str:
    """apify-client v3+ (Python 3.11+, Pydantic models) returns run as an
    object with .default_dataset_id; v2.x (still what installs on Python
    3.10, since v3 requires 3.11+) returns a dict with ['defaultDatasetId'].
    Real bug found running this live 2026-08-07: requirements.txt had
    apify-client>=1.7.0 unpinned, so the Cowork sandbox (Python 3.10) and
    Gurinder's Windows machine (Python 3.14) silently resolved to different
    major versions with different return types - 'Run' object is not
    subscriptable in production even though it worked in the sandbox.
    Confirmed via Apify's official v3 upgrade guide
    (docs.apify.com/api/client/python/docs/upgrading/upgrading-to-v3)
    rather than guessed. Handling both rather than pinning one version,
    since pinning apify-client<3 would break on Gurinder's actual (3.11+)
    Python and pinning >=3 would break anywhere still on 3.10."""
    if hasattr(run, "default_dataset_id"):
        return run.default_dataset_id
    return run["defaultDatasetId"]


def _run_actor(actor_id: str, run_input: dict) -> list[dict]:
    settings.require_apify()
    client = ApifyClient(settings.apify_token)
    run = client.actor(actor_id).call(run_input=run_input)
    dataset_id = _dataset_id(run)
    return list(client.dataset(dataset_id).iterate_items())


# ---------------------------------------------------------------------------
# LinkedIn
# ---------------------------------------------------------------------------

def _build_linkedin_search_url(query: str, location: str = "") -> str:
    """Builds a public LinkedIn jobs-search URL from keywords (+ optional
    location), matching the actor's documented input format."""
    params = {"keywords": query}
    if location:
        params["location"] = location
    return f"https://www.linkedin.com/jobs/search/?{urlencode(params)}"


def _build_linkedin_actor_input(query: str, max_results: int, location: str = "") -> dict:
    """Real input schema for curious_coder/linkedin-jobs-scraper, verified
    2026-08-06 via the Apify API (required: urls; count min is 10).

    scrapeCompany=False as of 2026-08-07: this flag makes the actor fire an
    extra scraping request per job for company detail fields (description,
    website, slogan, employee count). extract.py only ever reads
    companyName, which is present on the base job record without the extra
    fetch - so scrapeCompany=True was pure latency for data we discard, and
    a real contributor to job_intel_search_and_brief timing out through the
    Claude Desktop MCP client."""
    return {
        "urls": [_build_linkedin_search_url(query, location)],
        "scrapeCompany": False,
        "count": max(max_results, 10),  # actor enforces a minimum of 10
    }


def _normalize_linkedin_item(raw: dict) -> dict:
    return {
        "source": "linkedin",
        "title": raw.get("title", ""),
        "companyName": raw.get("companyName", ""),
        "location": raw.get("location", ""),
        "seniorityLevel": raw.get("seniorityLevel", ""),
        "link": raw.get("link") or raw.get("applyUrl", ""),
        "applyUrl": raw.get("applyUrl", ""),
        "salary": raw.get("salary") or None,
        "descriptionText": raw.get("descriptionText", "") or "",
    }


def search_linkedin_postings(query: str, max_results: int = 20, location: str = "") -> list[dict]:
    """`location` must be passed separately from `query` - real bug found
    running this live 2026-08-06: a query of "Data Analyst Berlin" (location
    folded into keywords) returned mostly US defense/finance postings,
    because LinkedIn's public search silently ignores location text embedded
    in the keywords param. Splitting it into the URL's own `location` param
    is what actually filters by geography."""
    raw_items = _run_actor(settings.apify_actor_id, _build_linkedin_actor_input(query, max_results, location))
    return [_normalize_linkedin_item(it) for it in raw_items]


# ---------------------------------------------------------------------------
# Xing
# ---------------------------------------------------------------------------

def _build_xing_actor_input(query: str, max_results: int, location: str = "") -> dict:
    """Real input schema for shahidirfan/Xing-Jobs-Scraper, verified
    2026-08-08 via the Apify API. Unlike LinkedIn, this actor takes
    keyword/location as plain fields, not a pre-built search URL."""
    return {
        "keyword": query,
        "location": location,  # schema: "Leave empty for all locations" - no hardcoded fallback needed
        "date_posted": "LAST_MONTH",
        "results_wanted": max(max_results, 5),
        "max_pages": 5,
    }


def _normalize_xing_item(raw: dict) -> dict:
    return {
        "source": "xing",
        "title": raw.get("title", ""),
        "companyName": raw.get("company", ""),
        "location": raw.get("location", ""),
        "seniorityLevel": "",  # career_level_id is an opaque coded value (e.g. "3.2ebf16") - see module docstring
        "link": raw.get("apply_url") or raw.get("url", ""),
        "applyUrl": raw.get("apply_url", ""),
        "salary": raw.get("salary") or None,
        "descriptionText": raw.get("description_text", "") or "",
    }


def search_xing_postings(query: str, max_results: int = 20, location: str = "") -> list[dict]:
    raw_items = _run_actor(XING_ACTOR_ID, _build_xing_actor_input(query, max_results, location))
    return [_normalize_xing_item(it) for it in raw_items]


# ---------------------------------------------------------------------------
# Indeed
# ---------------------------------------------------------------------------

def _build_indeed_actor_input(query: str, max_results: int, location: str = "") -> dict:
    """Real input schema for valig/indeed-jobs-scraper, verified 2026-08-08
    via the Apify API. `country` defaults to "us" if omitted - hardcoding
    "de" here deliberately, otherwise this would repeat the exact class of
    bug already found and fixed for LinkedIn location handling (silently
    returning results from the wrong geography)."""
    return {
        "country": "de",
        "title": query,
        "location": location,
        "limit": max(max_results, 5),
        "datePosted": "14",  # actor requires one of "1"/"3"/"7"/"14" - no "all time" option
    }


def _normalize_indeed_item(raw: dict) -> dict:
    employer = raw.get("employer") or {}
    location = raw.get("location") or {}
    base_salary = raw.get("baseSalary") or {}
    salary = None
    if base_salary.get("min") or base_salary.get("max"):
        currency = base_salary.get("currencyCode", "")
        salary = f"{currency} {base_salary.get('min', '')}-{base_salary.get('max', '')}".strip()
    description = raw.get("description") or {}
    return {
        "source": "indeed",
        "title": raw.get("title", ""),
        "companyName": employer.get("name", ""),
        "location": location.get("city", ""),
        "seniorityLevel": "",  # jobTypes.*/attributes.* are opaque hashed taxonomy codes - see module docstring
        "link": raw.get("jobUrl") or raw.get("url", ""),
        "applyUrl": raw.get("url", ""),
        "salary": salary,  # frequently None - Indeed's salary data was sparse across every sample checked
        "descriptionText": description.get("text", "") or "",
    }


def search_indeed_postings(query: str, max_results: int = 20, location: str = "") -> list[dict]:
    raw_items = _run_actor(INDEED_ACTOR_ID, _build_indeed_actor_input(query, max_results, location))
    return [_normalize_indeed_item(it) for it in raw_items]


# ---------------------------------------------------------------------------
# Multi-source
# ---------------------------------------------------------------------------

_SOURCES = {
    "linkedin": search_linkedin_postings,
    "xing": search_xing_postings,
    "indeed": search_indeed_postings,
}


def _dedup_key(item: dict) -> tuple[str, str]:
    return (item.get("title", "").strip().lower(), item.get("companyName", "").strip().lower())


def search_all_sources(query: str, max_results: int = 20, location: str = "") -> tuple[list[dict], list[str]]:
    """Runs all three sources in parallel (ThreadPoolExecutor, not
    sequential) - sequential would roughly triple Search-stage latency on
    top of the already-documented 22-90s LinkedIn-alone variance, making the
    MCP timeout problem (see brief_writer/extract parallelization) worse,
    not better. Wall-clock is now bounded by the single slowest source, not
    the sum of all three.

    Each source is wrapped individually so one failing actor (rate limit,
    schema change, timeout) doesn't take down the other two - same
    error-accumulation philosophy used throughout this pipeline (errors list
    grows, the run still returns whatever it could get). Returns
    (merged_deduped_items, errors).

    Dedup is a simple (title, company) case-insensitive key match, applied
    after normalization - catches identical crossposts across platforms, not
    near-duplicates with slightly different titles. Known approximation, not
    a full fuzzy-match dedup."""
    items: list[dict] = []
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=len(_SOURCES)) as pool:
        future_to_source = {
            pool.submit(fn, query, max_results, location): name
            for name, fn in _SOURCES.items()
        }
        for future in as_completed(future_to_source):
            name = future_to_source[future]
            try:
                items.extend(future.result())
            except Exception as e:  # noqa: BLE001
                errors.append(f"search_all_sources: {name} failed: {e}")

    seen = set()
    deduped = []
    for item in items:
        key = _dedup_key(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return deduped, errors
