from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from openai import OpenAI


def _as_data_url(path: Path) -> str:
    image_bytes = path.read_bytes()
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Fallback: extract first JSON object in the text response.
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        snippet = raw[start : end + 1]
        try:
            parsed = json.loads(snippet)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def analyze_garageband_screenshot(
    *,
    openai_client: OpenAI,
    screenshot_path: str,
    model: str,
    user_goal: str = "",
) -> dict[str, Any]:
    path = Path(screenshot_path).expanduser()
    if not path.exists():
        return {"ok": False, "error": f"Screenshot not found: {path}"}

    prompt = (
        "Analyze this GarageBand screenshot for project-state awareness. "
        "Return JSON only with keys: project_summary, tracks, selection, arrangement, risks, suggested_next_actions, confidence. "
        "project_summary should include view, likely_playback_state, tempo_bpm_guess, key_guess, cycle_enabled_guess. "
        "tracks should be an array of objects with name, type_guess, selected, muted, solo, has_regions. "
        "selection should include selected_track and selected_region_summary. "
        "arrangement should include visible_bar_range and notable_regions. "
        "risks should be short caveats when the screenshot is ambiguous. "
        "suggested_next_actions should be practical production steps. "
        "confidence should be a number from 0 to 1. "
        f"User goal context: {user_goal or 'general production help'}"
    )

    user_content: list[dict[str, Any]] = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": _as_data_url(path)}},
    ]

    response = openai_client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a precise DAW state analyzer. Respond with strict JSON and no markdown.",
            },
            {
                "role": "user",
                "content": user_content,
            },
        ],
        max_completion_tokens=700,
        reasoning_effort="low",
        verbosity="low",
        response_format={"type": "json_object"},
    )

    message = response.choices[0].message
    parsed = _extract_json(message.content or "")
    if not parsed:
        return {
            "ok": False,
            "error": "Vision model response was not valid JSON",
            "raw": (message.content or "")[:1000],
        }

    return {
        "ok": True,
        "screenshot_path": str(path.resolve()),
        "analysis": parsed,
    }
