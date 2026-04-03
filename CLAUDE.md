# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

GarageBand AI Agent — a Python/Flask app that acts as an AI music production assistant for GarageBand on macOS. It uses Anthropic tool-calling to control GarageBand via screenshots/clicks/keys, generate compositions (MIDI + rendered WAV), search/download samples from Freesound, and preview/play audio. Voice input is supported but disabled by default.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then set ANTHROPIC_API_KEY (and optionally FREESOUND_API_KEY)

# Run (serves on http://127.0.0.1:5050)
python app.py

# Tests
pytest -q                          # all tests
pytest tests/test_music_theory.py  # single file
pytest -k test_health_endpoint     # single test by name
```

## Architecture

**Request flow:** Browser UI → `POST /api/chat` → `app.py` → `agent.handle_user_message()` → Anthropic Messages API with tools → tool dispatch loop (bounded by `MAX_TOOL_ITERATIONS`) → response with text + tool_events.

**Agent loop** (`agent.py`): `GarageBandAgent` maintains `text_history` (plain text turns only, capped at `HISTORY_MAX_TURNS`). Tool calls and results stay per-request in `working_messages` to avoid malformed histories. Safeguards: 3-failure streak abort, 3-identical-tool-call abort, deadline timeout, and history trimming on oversized request errors.

**Tool dispatch** is a flat `tool_handlers` dict mapping tool names to callables. Tool definitions use Anthropic `input_schema`. After any screen-modifying computer action, a screenshot is auto-injected into the result.

**Tools** live in `tools/` as plain modules (no classes):
- `computer_control.py` — pyautogui + mss; all actions gated by `ENABLE_COMPUTER_CONTROL` env var via `ensure_enabled()`
- `applescript.py` — osascript subprocess; gated by `ALLOW_APPLESCRIPT`
- `music_theory.py` — pure functions for chords/scales/progressions/tempo, returns exact MIDI note numbers (0-127)
- `composer.py` — generates melody/chords/bass/drums using music_theory + random, exports MIDI via `mido`, and renders a WAV mix
- `samples.py` — Freesound API search + download with host allowlist and size cap
- `audio.py` — sine wave MIDI preview via numpy/sounddevice, file playback via soundfile

**Config** (`config.py`): single frozen `Settings` dataclass reading all values from env vars via `python-dotenv`. Imported as `settings` singleton.

## Key Patterns

- All tool functions return `dict` with `"ok": True/False` pattern
- `computer_control` actions require `ENABLE_COMPUTER_CONTROL=true` (default is `false`)
- Music theory tools are structured (not LLM-prompted) to avoid MIDI note hallucination
- GarageBand has minimal AppleScript support — UI automation via pyautogui is the primary control method
- The `create_music_in_garageband` tool composes (MIDI + WAV), can open MIDI in GarageBand, and can optionally auto-play rendered audio
- `create_music_in_garageband` project targeting is controlled by `project_mode`:
  - `auto` (default): keep current project if one is open, otherwise open new
  - `current`: operate only when a project is already open
  - `new`: explicitly open a new project
  - `ask`: request user confirmation when a project is already open
- Screenshots and downloads go to `screenshots/` and `downloads/` dirs respectively
- Flask app disables caching and uses file mtime for asset versioning

## Environment Variables

Required: `ANTHROPIC_API_KEY`

See `.env.example` for all options. Key toggles:
- `ENABLE_COMPUTER_CONTROL` (default `false`) — must be `true` for click/type/key actions
- `ALLOW_APPLESCRIPT` (default `true`)
- `AUTO_OPEN_GARAGEBAND` (default `true`) — launches GarageBand on `python app.py`
- `ENABLE_VOICE_INPUT` (default `false`) — enables browser speech recognition button
