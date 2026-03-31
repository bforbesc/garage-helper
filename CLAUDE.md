# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

GarageBand AI Agent — a Python/Flask app that acts as an AI music production assistant for GarageBand on macOS. It uses OpenAI tool-calling to control GarageBand via screenshots/clicks/keys, generate MIDI compositions, search/download samples from Freesound, and preview audio. Voice input via browser Web Speech API.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then set OPENAI_API_KEY and FREESOUND_API_KEY

# Run (serves on http://127.0.0.1:5050)
python app.py

# Tests
pytest -q                          # all tests
pytest tests/test_music_theory.py  # single file
pytest -k test_health_endpoint     # single test by name
```

## Architecture

**Request flow:** Browser UI → `POST /api/chat` → `app.py` → `agent.handle_user_message()` → OpenAI Chat Completions with tools → tool dispatch loop (up to 8 iterations) → response with text + tool_events.

**Agent loop** (`agent.py`): `GarageBandAgent` maintains `text_history` (plain text turns only, capped at `HISTORY_MAX_TURNS`). Tool calls and results stay per-request in `working_messages` to avoid malformed histories. The loop has safeguards: 3-failure streak abort, 3-identical-tool-call abort, deadline timeout, and automatic history trimming on token limit errors.

**Tool dispatch** is a flat `tool_handlers` dict mapping tool names to callables. Tool definitions use `input_schema` format (converted to OpenAI function format in `_openai_tools()`). After any screen-modifying computer action, a screenshot is auto-injected into the result.

**Tools** live in `tools/` as plain modules (no classes):
- `computer_control.py` — pyautogui + mss; all actions gated by `ENABLE_COMPUTER_CONTROL` env var via `ensure_enabled()`
- `applescript.py` — osascript subprocess; gated by `ALLOW_APPLESCRIPT`
- `music_theory.py` — pure functions for chords/scales/progressions/tempo, returns exact MIDI note numbers (0-127)
- `composer.py` — generates melody/chords/bass/drums using music_theory + random, exports MIDI via `mido`
- `samples.py` — Freesound API search + download with host allowlist and size cap
- `audio.py` — sine wave MIDI preview via numpy/sounddevice, file playback via soundfile

**Config** (`config.py`): single frozen `Settings` dataclass reading all values from env vars via `python-dotenv`. Imported as `settings` singleton.

## Key Patterns

- All tool functions return `dict` with `"ok": True/False` pattern
- `computer_control` actions require `ENABLE_COMPUTER_CONTROL=true` (default is `false`)
- Music theory tools are structured (not LLM-prompted) to avoid MIDI note hallucination
- GarageBand has minimal AppleScript support — UI automation via pyautogui is the primary control method
- The `create_music_in_garageband` tool is a composition of `compose_music_idea` + `launch_garageband` + `open_file_in_garageband`
- Screenshots and downloads go to `screenshots/` and `downloads/` dirs respectively
- Flask app disables caching and uses file mtime for asset versioning

## Environment Variables

Required: `OPENAI_API_KEY`, `FREESOUND_API_KEY`

See `.env.example` for all options. Key toggles:
- `ENABLE_COMPUTER_CONTROL` (default `false`) — must be `true` for click/type/key actions
- `ALLOW_APPLESCRIPT` (default `true`)
- `AUTO_OPEN_GARAGEBAND` (default `true`) — launches GarageBand on `python app.py`
