from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "anthropic")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")
    claude_max_tokens: int = int(os.getenv("CLAUDE_MAX_TOKENS", "2048"))
    max_tool_iterations: int = int(os.getenv("MAX_TOOL_ITERATIONS", "25"))
    screenshot_max_width: int = int(os.getenv("SCREENSHOT_MAX_WIDTH", "1280"))
    llm_request_timeout_sec: float = float(os.getenv("LLM_REQUEST_TIMEOUT_SEC", "25"))
    llm_total_timeout_sec: float = float(os.getenv("LLM_TOTAL_TIMEOUT_SEC", "120"))
    ui_request_timeout_ms: int = int(os.getenv("UI_REQUEST_TIMEOUT_MS", "180000"))
    history_max_turns: int = int(os.getenv("HISTORY_MAX_TURNS", "10"))
    ui_port: int = int(os.getenv("PORT", "5050"))
    flask_debug: bool = os.getenv("FLASK_DEBUG", "false").lower() in {"1", "true", "yes"}
    app_secret: str = os.getenv("APP_SECRET", "garage-ai-local-dev")
    screenshots_dir: str = os.getenv("SCREENSHOTS_DIR", "screenshots")
    downloads_dir: str = os.getenv("DOWNLOADS_DIR", "downloads")
    freesound_api_key: str = os.getenv("FREESOUND_API_KEY", "")
    post_action_delay_ms: int = int(os.getenv("POST_ACTION_DELAY_MS", "400"))
    enable_computer_control: bool = os.getenv("ENABLE_COMPUTER_CONTROL", "false").lower() in {"1", "true", "yes"}
    auto_focus_garageband: bool = os.getenv("AUTO_FOCUS_GARAGEBAND", "true").lower() in {"1", "true", "yes"}
    allow_applescript: bool = os.getenv("ALLOW_APPLESCRIPT", "true").lower() in {"1", "true", "yes"}
    allowed_download_hosts: str = os.getenv(
        "ALLOWED_DOWNLOAD_HOSTS",
        "freesound.org,cdn.freesound.org,freesoundcdn.org",
    )
    max_download_mb: int = int(os.getenv("MAX_DOWNLOAD_MB", "25"))
    auto_open_garageband: bool = os.getenv("AUTO_OPEN_GARAGEBAND", "true").lower() in {"1", "true", "yes"}


settings = Settings()
