# Job Intelligence Agent

Multi-agent LangGraph pipeline that searches LinkedIn for job postings,
extracts structured requirements, matches them against a profile, and writes
a SITREP-style briefing (Situation / Assessment / Recommendation) per match.

Rebuild of a prior "AI-Powered Job Matching Agent" whose source repo was
deleted and confirmed unrecoverable (2026-08-06 decision: rebuild from
scratch). See `docs/ADR-0001-langgraph-architecture.md` for the full design
rationale.

**Status: pipeline runs end-to-end live, real bugs found and fixed by
running it, eval suite 3/3 passing.** Not yet installed into Claude Desktop.

## Architecture

```
Search -> Extract -> Match -> Brief-writer
```

- **Search** (`agent/agents/search.py`) - live: `curious_coder/linkedin-jobs-scraper` on Apify.
- **Extract** (`agent/agents/extract.py`) - structured fields copied directly from the actor's real output; only skills are pulled from free text via Claude.
- **Match** (`agent/agents/match.py`) - `JobPosting` vs `Profile` -> fit score + matched/missing skills.
- **Brief-writer** (`agent/agents/brief_writer.py`) - `MatchResult` -> SITREP briefing, same contract as the Operations Intelligence Agent's briefing tool.
- **MCP server** (`mcp_server/server.py`) - wraps the above for any MCP client. See `mcp_server/README.md`.
- **Evals** (`eval/`) - labeled cases + LLM-judge faithfulness check. 3/3 passing as of 2026-08-06.

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

## Open items

- **LangSmith tracing is config-ready but not live-verified** - no LangSmith
  API key was available while building this. Set `LANGCHAIN_API_KEY` and
  `LANGCHAIN_TRACING_V2=true` in `.env` to turn it on; LangChain/LangGraph
  auto-detect these env vars, no code changes needed.
- **Not yet installed into Claude Desktop / tested via MCP Inspector** - see
  `mcp_server/README.md` for the config snippet.
- **Not yet pushed to GitHub** - lives locally at `C:\Users\dream\Job-Agent`.

## Roadmap (Weeks 1-3)

- [x] Resolve source-repo status (rebuild from scratch)
- [x] ADR + repo scaffold
- [x] Real Apify actor + real profile (from `gurinderResume.pdf`)
- [x] Run pipeline end-to-end against live data, fix real bugs found by running it
- [x] MCP server wrapper (mirrors Ops Intel Agent's `mcp_server/`)
- [x] Eval harness (labeled cases + LLM-judge), 3/3 passing
- [ ] LangSmith tracing live-verification (needs API key)
- [ ] Install into Claude Desktop, live-verify
- [ ] Push to GitHub

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # already filled in locally: ANTHROPIC_API_KEY, APIFY_TOKEN, APIFY_ACTOR_ID
uvicorn agent.api:app --reload
# or run the pipeline directly:
python -c "from agent.graph import run; print(run('Data Analyst', location='Berlin, Germany'))"
# or run evals:
python -m eval.run_evals --case-id berlin_data_analyst
python -m eval.run_evals --aggregate
```
