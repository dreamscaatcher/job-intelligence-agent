"""Apify integration for the Search agent.

Actor: curious_coder/linkedin-jobs-scraper (id hKByXkMQaC5Qt9UMN). Chosen
2026-08-06 after the Apify MCP auth was fixed and the Store was queried
directly: highest usage by far among LinkedIn job-search actors (122,958
users, 4.32/5 over 119 reviews, 3.1M total runs, actively running the day it
was checked). Input schema fetched live via
GET /v2/acts/curious_coder~linkedin-jobs-scraper/builds/default - the only
required field is `urls`, a list of LinkedIn public jobs-search URLs (NOT a
free-text keyword param), which is why `_build_actor_input` constructs a
LinkedIn search URL rather than passing the query straight through.
"""
from __future__ import annotations
from urllib.parse import urlencode

from apify_client import ApifyClient

from agent.config import settings


def _build_search_url(query: str, location: str = "") -> str:
    """Builds a public LinkedIn jobs-search URL from keywords (+ optional
    location), matching the actor's documented input format."""
    params = {"keywords": query}
    if location:
        params["location"] = location
    return f"https://www.linkedin.com/jobs/search/?{urlencode(params)}"


def _build_actor_input(query: str, max_results: int, location: str = "") -> dict:
    """Real input schema for curious_coder/linkedin-jobs-scraper, verified
    2026-08-06 via the Apify API (required: urls; count min is 10)."""
    return {
        "urls": [_build_search_url(query, location)],
        "scrapeCompany": True,
        "count": max(max_results, 10),  # actor enforces a minimum of 10
    }


def search_job_postings(query: str, max_results: int = 20, location: str = "") -> list[dict]:
    """Run the configured Apify actor and return raw dataset items.

    Raises RuntimeError via settings.require_apify() if not configured yet.

    `location` must be passed separately from `query` - real bug found
    running this live 2026-08-06: a query of "Data Analyst Berlin" (location
    folded into keywords) returned mostly US defense/finance postings,
    because LinkedIn's public search silently ignores location text embedded
    in the keywords param. Splitting it into the URL's own `location` param
    is what actually filters by geography.
    """
    settings.require_apify()

    client = ApifyClient(settings.apify_token)
    run = client.actor(settings.apify_actor_id).call(
        run_input=_build_actor_input(query, max_results, location)
    )
    dataset_id = run["defaultDatasetId"]
    items = list(client.dataset(dataset_id).iterate_items())
    return items
