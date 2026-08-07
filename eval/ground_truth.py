"""Ground-truth checks computed against real data, not hardcoded expectations
- mirrors the Ops Intel Agent eval harness's approach of fetching expected
values live via the same tool functions the agent uses."""
from __future__ import annotations


def geo_fidelity_check(location: str, raw_postings: list[dict]) -> dict:
    """For a case with a location filter, checks what fraction of raw
    postings actually landed in that geography. This is the direct
    regression check for the location-folded-into-query bug found
    2026-08-06 (see apify_tools.py / state.py comments)."""
    if not location or not raw_postings:
        return {"applicable": False}

    # e.g. "Berlin, Germany" -> ["berlin", "germany"]
    parts = [p.strip().lower() for p in location.split(",") if p.strip()]

    matches = 0
    mismatches = []
    for p in raw_postings:
        posting_location = (p.get("location") or "").lower()
        if any(part in posting_location for part in parts):
            matches += 1
        else:
            mismatches.append({"title": p.get("title"), "location": p.get("location")})

    fraction = matches / len(raw_postings)
    return {
        "applicable": True,
        "total": len(raw_postings),
        "matches": matches,
        "fraction": round(fraction, 2),
        "passed": fraction >= 0.8,  # allow some slack for actor noise, not a hard 100%
        "mismatches": mismatches[:5],
    }
