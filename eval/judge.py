"""LLM-as-judge faithfulness check, hand-rolled RAGAS-style pass - same
pattern as the Ops Intel Agent's eval/judge.py. Checks that a briefing only
asserts things grounded in the match_result it was given, doesn't invent
skills/details, and (for the no-location case) doesn't fabricate geography
it was never told."""
from __future__ import annotations

import json

import anthropic

from agent.config import settings
from agent.llm_utils import parse_json_response

JUDGE_SYSTEM_PROMPT = """You are a strict faithfulness judge for a job-matching
briefing. You will be given the INPUT data (a posting + match_result) and the
OUTPUT briefing generated from it. Check whether the briefing's claims are
actually grounded in the input - no invented skills, no invented company
facts not in the posting, no invented location claims beyond what's given.

Return ONLY valid JSON, no prose:
{
  "faithful": bool,
  "reasoning": str,
  "unsupported_claims": [str]
}"""


def judge_faithfulness(match_result: dict, briefing: dict) -> dict:
    if not settings.anthropic_api_key:
        return {"faithful": None, "reasoning": "ANTHROPIC_API_KEY not set - judge skipped", "unsupported_claims": []}

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    payload = json.dumps({"input_match_result": match_result, "output_briefing": briefing})
    resp = client.messages.create(
        model=settings.model_name,
        max_tokens=1024,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": payload}],
    )
    return parse_json_response(resp.content[0].text)
