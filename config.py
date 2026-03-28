from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-7-sonnet-latest")
    anthropic_max_tokens: int = int(os.getenv("ANTHROPIC_MAX_TOKENS", "1200"))
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5")
    ui_port: int = int(os.getenv("PORT", "5050"))
    app_secret: str = os.getenv("APP_SECRET", "garage-ai-local-dev")
    screenshots_dir: str = os.getenv("SCREENSHOTS_DIR", "screenshots")
    downloads_dir: str = os.getenv("DOWNLOADS_DIR", "downloads")
    freesound_api_key: str = os.getenv("FREESOUND_API_KEY", "")
    say_voice: str = os.getenv("SAY_VOICE", "Samantha")
    post_action_delay_ms: int = int(os.getenv("POST_ACTION_DELAY_MS", "400"))
    enable_computer_control: bool = os.getenv("ENABLE_COMPUTER_CONTROL", "false").lower() in {"1", "true", "yes"}
    allow_applescript: bool = os.getenv("ALLOW_APPLESCRIPT", "true").lower() in {"1", "true", "yes"}
    allowed_download_hosts: str = os.getenv(
        "ALLOWED_DOWNLOAD_HOSTS",
        "freesound.org,cdn.freesound.org,freesoundcdn.org",
    )
    max_download_mb: int = int(os.getenv("MAX_DOWNLOAD_MB", "25"))


settings = Settings()
