# ADR-0001: LangGraph Orchestration for the Job Intelligence Agent

Status: Accepted (scaffolding phase)
Date: 2026-08-06

## Context

This is a from-scratch rebuild. The original "AI-Powered Job Matching Agent" repo
referenced on the resume was deleted (likely during a GitHub cleanup) and is not
recoverable — confirmed absent from the 32-repo GitHub audit on 2026-07-25.
Decision made 2026-08-06: rebuild rather than pursue GitHub's restore window.

The only surviving prior art is a 2022 Colab notebook
(`Resume_job_description_matcher.ipynb`, Google Drive) that compared a resume to a
single pasted job description using `CountVectorizer` + cosine similarity
(score: 0.656 on the one example run). That approach is a bag-of-words baseline,
not a multi-agent system, and is not reused directly here — it's referenced only
as the historical starting point.

This follows the pattern validated by the Operations Intelligence Agent
(`bigquery-defense-logistics-y42`): LangGraph multi-agent pipeline, FastAPI
endpoint, MCP server wrapper, labeled eval harness, LangSmith tracing. That
project shipped items 1-5 of its roadmap live-verified; this project reuses the
same shape rather than inventing a new one.

## Decision

Four LangGraph agent nodes, run as a linear pipeline (Search -> Extract -> Match
-> Brief-writer), state passed via a shared `AgentState` TypedDict:

1. **Search** — fetches raw job postings for a given query (role, location,
   filters). Calls an Apify actor via the Apify MCP/API rather than scraping
   directly. **Open item:** actor not yet selected — the Apify MCP connector
   returned an invalid-token error when queried during scaffolding
   (`search-actors` call failed 2026-08-06), so no live actor search has
   happened yet. `agent/tools/apify_tools.py` is written against Apify's
   generic actor-run interface so the actor ID is a config value, not a
   hardcoded assumption — swap in `APIFY_ACTOR_ID` once the token is fixed and
   a real actor (LinkedIn/Indeed job search) is chosen and verified.
2. **Extract** — takes raw postings (HTML/text from Search) and produces a
   structured `JobPosting` (title, company, location, seniority, required
   skills, nice-to-have skills, salary if present, raw URL) via a Claude
   structured-output call. No regex/heuristic parsing — postings are too
   inconsistently formatted across sources.
3. **Match** — compares each `JobPosting` against a structured `Profile`
   (target roles, skills, years of experience, positioning summary) and
   produces a fit score plus matched/missing skills. **Open item:** no current
   AI/ML-positioned resume was found in Google Drive during scaffolding — only
   a 2020 GIS Officer CV (`cv_clipboard.docx`, no AI/tech content) turned up.
   `agent/profile/profile.example.json` defines the schema the Match agent
   expects; Gurinder needs to supply real profile content (paste, or a real
   resume file) before Match can run against anything but placeholder data.
4. **Brief-writer** — synthesizes a SITREP-style briefing per matched job:
   Situation (what the posting says) / Assessment (fit, gaps, caveats) /
   Recommendation (apply, tailor resume how, or skip). Mirrors the Ops Intel
   Agent's Retriever/Analyst/Briefing output contract intentionally, so the
   eventual eval harness and MCP tool shapes can reuse that pattern.

LLM: Claude (Anthropic), consistent with Ops Intel Agent. No new vendor
introduced.

Storage: no database yet. `Profile` is a local JSON file; job-match results are
returned per-run, not persisted. A persistence layer is deferred the same way
Ops Intel Agent deferred streaming/RBAC (items 6-7) — descope until there's a
real reason (multiple runs to compare, a UI to serve) to add it.

## Consequences

- Nothing here has been run against a live Apify actor or a real profile yet.
  Two explicit blockers are called out above rather than papered over with
  invented actor IDs or fabricated resume content — that's the same discipline
  the Ops Intel Agent audit enforced (unverified R² numbers had to be pulled
  from that README until re-run for real).
- MCP server wrapper, eval harness, and LangSmith tracing are Week 2-3 work,
  not scaffolded yet — same order Ops Intel Agent followed (build the
  pipeline first, verify it runs, then wrap/eval/trace it).
- Repo lives at `C:\Users\dream\Job-Agent` (local folder), not yet pushed to
  GitHub — no repo has been created for it yet.
