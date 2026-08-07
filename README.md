# Job Intelligence Agent

Multi-agent LangGraph pipeline that searches LinkedIn for job postings,
extracts structured requirements, matches them against a profile, and writes
a SITREP-style briefing (Situation / Assessment / Recommendation) per match.

Rebuild of a prior "AI-Powered Job Matching Agent" whose source repo was
deleted and confirmed unrecoverable (2026-08-06 decision: rebuild from
scratch). See `docs/ADR-0001-langgraph-architecture.md` for the full design
rationale.

**Status: fully live.** Pipeline, MCP server, evals, and LangSmith tracing
are all running and verified on Gurinder's actual machine (not just the dev
sandbox) - see "Real bugs found by running this" below for what that
actually took. Public repo: github.com/dreamscaatcher/job-intelligence-agent.

## Architecture

```
Search -> Extract -> Match -> Brief-writer
```

- **Search** (`agent/agents/search.py`) - live: `curious_coder/linkedin-jobs-scraper` on Apify.
- **Extract** (`agent/agents/extract.py`) - structured fields copied directly from the actor's real output; only skills are pulled from free text via Claude. Parallelized (`ThreadPoolExecutor`, 5 workers).
- **Match** (`agent/agents/match.py`) - `JobPosting` vs `Profile` -> fit score + matched/missing skills.
- **Brief-writer** (`agent/agents/brief_writer.py`) - `MatchResult` -> SITREP briefing, same contract as the Operations Intelligence Agent's briefing tool. Also parallelized.
- **MCP server** (`mcp_server/server.py`) - wraps the above, installed in Claude Desktop and verified from an independent Cowork session. See `mcp_server/README.md`.
- **Evals** (`eval/`) - labeled cases + LLM-judge faithfulness check. 3/3 passing.

Only the top `brief_limit` (default 5) of the fetched postings go through
Extract/Match/Brief-writer - see bug 5 below for why.

## Real bugs found by running this (not caught by review)

1. **Location silently ignored.** Folding location into the free-text query
   (`"Data Analyst Berlin"`) got it ignored by LinkedIn's public search,
   returning mostly US postings. Fixed by giving `location` its own field
   through state/search/API.
2. **Claude wraps JSON in markdown fences** despite "no prose" instructions,
   breaking bare `json.loads`. Fixed with `agent/llm_utils.py`.
3. **Multi-location postings collapsed to one city** in the briefing (e.g.
   "San Francisco (US) or Berlin (GER)" became "in Berlin") - caught by the
   eval harness's faithfulness judge, fixed with an explicit prompt
   instruction in `brief_writer.py`.
4. **`fit_score=0.0` for postings with no extracted skills** conflated "no
   data" with "zero match," which the Brief-writer then presented as a
   confident negative. Fixed: `fit_score` is `None` (with a note) when no
   skills were extracted, not a fabricated zero.
5. **`apify-client` v2/v3 return-type mismatch.** Only surfaced when Gurinder
   ran the MCP tool on his real machine: `requirements.txt` had
   `apify-client>=1.7.0` unpinned, so the dev sandbox (Python 3.10) silently
   resolved to 2.5.1 (dict-based) while Gurinder's machine (Python 3.14)
   resolved to 3.1.1 (Pydantic models - `run.default_dataset_id`, not
   `run['defaultDatasetId']`). Every sandbox test passed; production broke on
   the first real run. Fixed with a version-agnostic helper in
   `apify_tools.py`, confirmed against the real 3.1.1 install after.
6. **`job_intel_search_and_brief` timed out through the Claude Desktop MCP
   client.** Briefing all 10 fetched postings meant up to 20 sequential
   Claude calls. Fixed two ways: `brief_limit` (default 5) caps how many
   postings get the full LLM treatment, and Extract/Brief-writer calls are
   now parallelized (5 workers each). Cut a real run from timing out past 3
   minutes to 61 seconds for 5 postings, 0 errors.

## Open items

- **`job_intel_search_and_brief` at higher `brief_limit` values may still be
  slow** - raising it back toward `max_results` reintroduces the original
  timeout risk, just later. Not yet tested at the boundary.
- **Roadmap items 6-7 (streaming/alerting, RBAC)** - not started, same as
  Ops Intel Agent, intentionally deferred until there's a concrete reason.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # ANTHROPIC_API_KEY, APIFY_TOKEN, APIFY_ACTOR_ID, LANGCHAIN_* (EU endpoint if applicable)
cp agent/profile/profile.example.json agent/profile/profile.json  # fill in real profile content
uvicorn agent.api:app --reload
# or run the pipeline directly:
python -c "from agent.graph import run; print(run('Data Analyst', location='Berlin, Germany', brief_limit=5))"
# or run evals:
python -m eval.run_evals --case-id berlin_data_analyst
python -m eval.run_evals --aggregate
```

MCP server: see `mcp_server/README.md` for the Claude Desktop config -
already installed and live-verified locally.
