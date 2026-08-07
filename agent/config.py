"""Configuration for the Job Intelligence Agent.

Loads from environment variables (.env). No secrets or IDs are hardcoded here -
values that are still unverified (e.g. APIFY_ACTOR_ID) default to None/empty
and the code that uses them should fail loudly rather than silently proceeding
with a guessed value.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    # LLM
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    model_name: str = field(default_factory=lambda: os.getenv("MODEL_NAME", "claude-sonnet-4-5"))

    # Apify (Search agent)
    apify_token: str = field(default_factory=lambda: os.getenv("APIFY_TOKEN", ""))
    # NOT SET on purpose: no actor has been verified yet (see ADR-0001, open
    # item 1). Set this only after confirming a real actor via the Apify MCP
    # `search-actors` / `fetch-actor-details` tools.
    apify_actor_id: str = field(default_factory=lambda: os.getenv("APIFY_ACTOR_ID", ""))

    # Profile (Match agent)
    profile_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("PROFILE_PATH", str(PROJECT_ROOT / "agent" / "profile" / "profile.json"))
        )
    )

    # LangSmith tracing (wired later - Week 3, matching Ops Intel Agent roadmap)
    langsmith_tracing: bool = field(
        default_factory=lambda: os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    )
    langsmith_project: str = field(
        default_factory=lambda: os.getenv("LANGCHAIN_PROJECT", "job-intelligence-agent")
    )

    def require_apify(self) -> None:
        if not self.apify_token:
            raise RuntimeError(
                "APIFY_TOKEN not set. The Apify MCP connector needs re-authorizing "
                "(previous search-actors call failed with an invalid-token error)."
            )
        if not self.apify_actor_id:
            raise RuntimeError(
                "APIFY_ACTOR_ID not set - no job-search actor has been chosen and "
                "verified yet. See ADR-0001 open item 1."
            )

    def require_profile(self) -> None:
        if not self.profile_path.exists():
            raise RuntimeError(
                f"No profile found at {self.profile_path}. Copy "
                "agent/profile/profile.example.json to profile.json and fill in "
                "real profile content - see ADR-0001 open item 2."
            )


settings = Settings()
