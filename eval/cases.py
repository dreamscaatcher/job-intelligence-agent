"""Labeled eval cases for the Job Intelligence Agent.

Each case exercises a real thing this pipeline has actually gotten wrong
before (see agent/state.py and apify_tools.py comments for the location bug,
llm_utils.py for the JSON-fence bug) - not synthetic happy-path checks.
Kept to a small `briefed_subset` per case (postings actually run through
Extract/Match/Brief-writer) to bound Anthropic/Apify cost and wall time;
`max_results` still fetches a full real page from Search so geo-fidelity
checks (case 1) have enough real data to check against.
"""
from __future__ import annotations

from typing import TypedDict


class EvalCase(TypedDict):
    id: str
    query: str
    location: str
    max_results: int
    briefed_subset: int  # how many of the fetched postings to run through Extract/Match/Brief-writer
    checks: list[str]  # which ground-truth/judge checks apply to this case


CASES: list[EvalCase] = [
    {
        "id": "berlin_data_analyst",
        "query": "Data Analyst",
        "location": "Berlin, Germany",
        "max_results": 10,
        "briefed_subset": 2,
        "checks": ["geo_fidelity", "faithfulness"],
    },
    {
        "id": "berlin_ai_engineer",
        "query": "AI Engineer",
        "location": "Berlin, Germany",
        "max_results": 10,
        "briefed_subset": 2,
        "checks": ["geo_fidelity", "faithfulness"],
    },
    {
        "id": "no_location_global",
        "query": "Data Analyst",
        "location": "",
        "max_results": 10,
        "briefed_subset": 1,
        "checks": ["faithfulness", "no_location_fabrication"],
    },
]
