# GarageBand AI Agent

Python + Flask assistant for music production in GarageBand with:
- Anthropic chat + tool calling
- OpenAI chat + tool calling (optional provider)
- Computer control (screenshot/click/type/key/scroll/drag)
- Music theory tools with exact MIDI note output
- Voice input via browser speech recognition
- TTS via macOS `say`
- Freesound sample search/download
- Audio preview (synthesized MIDI notes + local sample playback)

## Defaults Chosen
- UI framework: Flask web app
- Sample source: Freesound API first
- Voice input: browser Web Speech API
- Audio playback: `numpy + sounddevice + soundfile`

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set at minimum:
- `OPENAI_API_KEY`
- `FREESOUND_API_KEY` (for sample search/download)

Optional:
- `LLM_PROVIDER=openai|anthropic|auto` (default is `openai`)
- `ENABLE_COMPUTER_CONTROL=true` to allow click/type/key/screenshot actions
- `ALLOW_APPLESCRIPT=true|false`
- `ALLOWED_DOWNLOAD_HOSTS` comma-separated host allowlist
- `MAX_DOWNLOAD_MB` max per-file download size

## Run
```bash
python app.py
```

Open [http://127.0.0.1:5050](http://127.0.0.1:5050).

One-click launcher:
- Double-click [launch_garage_ai.command](/Users/bernardo/Desktop/CODE/garage-ai/launch_garage_ai.command)
- It creates `.venv` (if missing), installs deps once, ensures `.env` exists, opens browser, and starts the app

Desktop shortcut/icon (macOS):
```bash
ln -sf /Users/bernardo/Desktop/CODE/garage-ai/launch_garage_ai.command ~/Desktop/GarageAI.command
```
Then you can double-click `GarageAI.command` from Desktop.

## Test
```bash
pytest -q
```

## Core Files
- `app.py`: Flask API + UI server
- `agent.py`: Anthropic loop + tool dispatch
- `tools/music_theory.py`: MIDI-aware chord/scale/arrangement tools
- `tools/computer_control.py`: screenshot and UI controls
- `tools/applescript.py`: app-level automation via `osascript`
- `tools/samples.py`: Freesound search/download
- `tools/audio.py`: MIDI synth preview and sample playback
- `templates/index.html`, `static/`: browser UI

## Notes
- GarageBand automation is macOS-only.
- `pyautogui` fail-safe is enabled (move mouse to top-left to abort).
- Freesound results include license metadata; verify usage rights before publishing tracks.
- Check runtime status at `GET /api/health`.
