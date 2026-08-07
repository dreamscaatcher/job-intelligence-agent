"""FastAPI endpoint wrapping the LangGraph pipeline, mirroring the Ops Intel
Agent's api.py shape (POST /briefing there -> POST /search here)."""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from agent.graph import run

app = FastAPI(title="Job Intelligence Agent")


class SearchRequest(BaseModel):
    query: str
    location: str = ""
    max_results: int = 20


@app.post("/search")
def search(req: SearchRequest) -> dict:
    result = run(req.query, req.max_results, req.location)
    return {
        "briefings": result.get("briefings", []),
        "match_count": len(result.get("match_results", [])),
        "errors": result.get("errors", []),
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
