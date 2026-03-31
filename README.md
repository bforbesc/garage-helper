# GarageBand AI Agent

Python + Flask assistant for music production in GarageBand with:
- OpenAI chat + tool calling
- Computer control (screenshot/click/type/key/scroll/drag)
- Fast keyboard automation (`garageband_shortcut` and `key_sequence`)
- Music theory tools with exact MIDI note output
- Composition tool that generates melody/chords/bass/drums and exports MIDI (`compose_music_idea`)
- One-step compose+import flow (`create_music_in_garageband`) for fast GarageBand results
- Voice input via browser speech recognition
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
- `LLM_PROVIDER=openai` (default is `openai`)
- `LLM_REQUEST_TIMEOUT_SEC` timeout per model API call (default `25`)
- `LLM_TOTAL_TIMEOUT_SEC` max total agent turn time (default `55`)
- `OPENAI_REASONING_EFFORT` (`low|medium|high`, default `low`)
- `OPENAI_VERBOSITY` (`low|medium|high`, default `low`)
- `OPENAI_MAX_OUTPUT_TOKENS` model output cap per call (default `900`)
- `HISTORY_MAX_TURNS` retained text turns for context (default `10`)
- `ENABLE_COMPUTER_CONTROL=true` to allow click/type/key/screenshot actions
- `ALLOW_APPLESCRIPT=true|false`
- `ALLOWED_DOWNLOAD_HOSTS` comma-separated host allowlist
- `MAX_DOWNLOAD_MB` max per-file download size
- `AUTO_OPEN_GARAGEBAND=true|false` (default `true`)

## Run
```bash
python app.py
```

Open [http://127.0.0.1:5050](http://127.0.0.1:5050).

One-click launcher:
- Double-click [launch_garage_ai.command](/Users/bernardo/Desktop/CODE/garage-ai/launch_garage_ai.command)
- It creates `.venv` (if missing), installs deps once, ensures `.env` exists, opens browser, and starts the app
- It auto-reinstalls deps when `requirements.txt` changes

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
- `agent.py`: OpenAI loop + tool dispatch
- `tools/music_theory.py`: MIDI-aware chord/scale/arrangement tools
- `tools/composer.py`: melody/bass/drums generator + MIDI export
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
