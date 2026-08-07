"""Shared helpers for parsing Claude's JSON responses.

Real bug found by running the pipeline live (2026-08-06): despite explicit
"Return ONLY valid JSON, no prose" system prompts, Claude wraps its output in
markdown code fences (```json ... ```), which breaks a bare json.loads() with
"Expecting value: line 1 column 1". Confirmed via a direct API call before
patching - not guessed. Same class of bug the Ops Intel Agent's eval run hit
(Briefing truncation, schema slips): a prompt instruction alone isn't enough,
the parser has to tolerate the model's actual behavior.
"""
from __future__ import annotations

import json
import re

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


def parse_json_response(text: str) -> dict:
    """Parses a Claude text response as JSON, stripping markdown code fences
    if present. Raises json.JSONDecodeError (same as bare json.loads) if the
    result still isn't valid JSON, so callers' existing except blocks work
    unchanged."""
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    if match:
        stripped = match.group(1).strip()
    return json.loads(stripped)
