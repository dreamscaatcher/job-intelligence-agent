"""FastAPI endpoint wrapping the LangGraph pipeline, mirroring the Ops Intel
Agent's api.py shape (POST /briefing there -> POST /search here), including
its GET-page-vs-POST-API split: GET /search serves the browser UI,
POST /search is the JSON API that page's own fetch() call hits (and what
mcp_server/server.py and direct callers use)."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from agent.graph import run

app = FastAPI(title="Job Intelligence Agent")

STATIC_DIR = Path(__file__).parent / "static"


class SearchRequest(BaseModel):
    query: str
    location: str = ""
    max_results: int = 20
    brief_limit: int = 3


@app.post("/search")
def search(req: SearchRequest) -> dict:
    result = run(req.query, req.max_results, req.location, req.brief_limit)
    match_results = result.get("match_results", [])
    briefings = result.get("briefings", [])

    # Zip by index, not by re-matching on content - safe because brief_writer_node
    # was fixed (2026-08-07) to preserve match_results order via indexed futures
    # rather than as_completed() append order. Before that fix, briefings[i] had
    # no guaranteed correspondence to match_results[i], so this zip would have
    # silently paired the wrong fit_score with the wrong briefing.
    results = []
    for i, briefing in enumerate(briefings):
        mr = match_results[i] if i < len(match_results) else {}
        posting = mr.get("posting", {})
        results.append(
            {
                "title": posting.get("title", ""),
                "company": posting.get("company", ""),
                "location": posting.get("location", ""),
                "seniority": posting.get("seniority", ""),
                "salary": posting.get("salary"),
                "url": posting.get("url", ""),
                "source": posting.get("source", ""),
                "fit_score": mr.get("fit_score"),
                "matched_skills": mr.get("matched_skills", []),
                "missing_skills": mr.get("missing_skills", []),
                "transferable_signals": mr.get("transferable_signals", []),
                "situation": briefing.get("situation", ""),
                "assessment": briefing.get("assessment", ""),
                "recommendation": briefing.get("recommendation", ""),
                "sources": briefing.get("sources", []),
                "no_data_warning": briefing.get("no_data_warning"),
            }
        )

    return {
        "results": results,
        "briefings": briefings,  # kept for backward compat with any other consumer
        "match_count": len(match_results),
        "errors": result.get("errors", []),
    }


@app.get("/search")
def search_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "search.html")


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/search")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
