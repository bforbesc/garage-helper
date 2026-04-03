# GarageBand AI Agent

Python + Flask assistant for music production in GarageBand on macOS.

## What It Does
- Anthropic Claude tool-calling agent (`agent.py`)
- GarageBand control via screenshots, clicks, keys, drags (`tools/computer_control.py`)
- App-level automation with AppleScript (`tools/applescript.py`)
- Music theory helpers with exact MIDI note numbers (`tools/music_theory.py`)
- Composition generation for melody, bass, drums, chords (`tools/composer.py`)
- Exports both MIDI and rendered WAV for each composition
- Optional auto-play of the rendered finished song
- Freesound search/download tools (`tools/samples.py`)
- Voice input in browser UI (Web Speech API)

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Required minimum:
- `ANTHROPIC_API_KEY`

Optional for sample search/download:
- `FREESOUND_API_KEY`

## Key Environment Variables
- `CLAUDE_MODEL` (default `claude-sonnet-4-5`)
- `CLAUDE_MAX_TOKENS` (default `2048`)
- `MAX_TOOL_ITERATIONS` (default `25`)
- `LLM_TOTAL_TIMEOUT_SEC` (default `120`)
- `UI_REQUEST_TIMEOUT_MS` (default `180000`)
- `ENABLE_COMPUTER_CONTROL` (default `false`)
- `AUTO_FOCUS_GARAGEBAND` (default `true`)
- `ALLOW_APPLESCRIPT` (default `true`)
- `AUTO_OPEN_GARAGEBAND` (default `true`)
- `ALLOWED_DOWNLOAD_HOSTS`
- `MAX_DOWNLOAD_MB`

## Run
```bash
python app.py
```

Then open [http://127.0.0.1:5050](http://127.0.0.1:5050).

## Launcher (macOS)
- Double-click [launch_garage_ai.command](/Users/bernardo/Desktop/CODE/garage-ai/launch_garage_ai.command)
- It bootstraps `.venv`, installs dependencies, ensures `.env`, and starts the app.

## Test
```bash
pytest -q
```

## Main API Endpoints
- `GET /api/health`
- `POST /api/chat`
- `POST /api/reset`
- `GET /api/samples/search`
- `POST /api/samples/download`
- `POST /api/audio/preview-chord`
- `POST /api/audio/play-file`

## Notes
- GarageBand control/playback is macOS-only.
- `pyautogui` fail-safe is on (move cursor to top-left to abort automation).
- Freesound licenses must be reviewed before release use.
