"""Orchestrates eval cases: fetch real postings, run a bounded subset through
the full pipeline, check geo-fidelity + faithfulness, write a JSON report.

Supports running one case at a time (--case-id) since a full case involves a
live Apify run + several live Anthropic calls, which can exceed a single
execution window - each case is independently resumable/rerunnable rather
than requiring one unbroken run of the whole suite.

Usage:
    python -m eval.run_evals --case-id berlin_data_analyst
    python -m eval.run_evals --aggregate   # summarize all case results found in eval/results/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.agents.extract import extract_node
from agent.agents.match import match_node
from agent.agents.brief_writer import brief_writer_node
from agent.tools.apify_tools import search_job_postings
from eval.cases import CASES
from eval.ground_truth import geo_fidelity_check
from eval.judge import judge_faithfulness

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def run_case(case: dict) -> dict:
    raw_postings = search_job_postings(case["query"], case["max_results"], case["location"])

    result: dict = {"case_id": case["id"], "query": case["query"], "location": case["location"]}

    if "geo_fidelity" in case["checks"]:
        result["geo_fidelity"] = geo_fidelity_check(case["location"], raw_postings)

    subset = raw_postings[: case["briefed_subset"]]
    state = {"query": case["query"], "raw_postings": subset, "errors": []}
    state = extract_node(state)
    state = match_node(state)
    state = brief_writer_node(state)
    result["pipeline_errors"] = state["errors"]

    if "faithfulness" in case["checks"] and state.get("match_results") and state.get("briefings"):
        judgments = [
            judge_faithfulness(mr, br)
            for mr, br in zip(state["match_results"], state["briefings"])
        ]
        result["faithfulness_judgments"] = judgments
        result["faithfulness_passed"] = all(j.get("faithful") for j in judgments)

    if "no_location_fabrication" in case["checks"] and state.get("briefings"):
        # No location was given - the briefing shouldn't invent one. Cheap
        # heuristic check (not an LLM call) rather than over-engineering this.
        flagged = [
            b for b in state["briefings"]
            if "germany" in (b.get("situation", "") + b.get("assessment", "")).lower()
            and "germany" not in json.dumps(subset).lower()
        ]
        result["no_location_fabrication_passed"] = len(flagged) == 0
        result["no_location_fabrication_flagged"] = flagged

    passed_flags = []
    if "geo_fidelity" in result and result["geo_fidelity"].get("applicable"):
        passed_flags.append(result["geo_fidelity"]["passed"])
    if "faithfulness_passed" in result:
        passed_flags.append(result["faithfulness_passed"])
    if "no_location_fabrication_passed" in result:
        passed_flags.append(result["no_location_fabrication_passed"])
    result["overall_passed"] = all(passed_flags) if passed_flags else None

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", help="Run a single case by id")
    parser.add_argument("--aggregate", action="store_true", help="Summarize existing results instead of running")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(exist_ok=True)

    if args.aggregate:
        results = []
        for f in sorted(RESULTS_DIR.glob("*.json")):
            results.append(json.loads(f.read_text()))
        passed = sum(1 for r in results if r.get("overall_passed"))
        print(f"{passed}/{len(results)} cases passed")
        for r in results:
            print(f"  [{'PASS' if r.get('overall_passed') else 'FAIL'}] {r['case_id']}")
        return

    cases_to_run = [c for c in CASES if not args.case_id or c["id"] == args.case_id]
    if not cases_to_run:
        print(f"No case matching id={args.case_id!r}")
        return

    for case in cases_to_run:
        print(f"Running case: {case['id']}")
        result = run_case(case)
        out_path = RESULTS_DIR / f"{case['id']}.json"
        out_path.write_text(json.dumps(result, indent=2, default=str))
        print(f"  overall_passed={result['overall_passed']} -> {out_path}")


if __name__ == "__main__":
    main()
