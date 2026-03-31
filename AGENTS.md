# GarageBand AI Agent

## Project Overview
A Python-based AI agent with a visual UI that helps produce music in GarageBand on macOS. The agent sits in a window next to GarageBand and combines:
1. **Direct GarageBand control** via local computer control tools (screenshots, clicks, keypresses)
2. **Music theory assistance** via custom tools (chord progressions, scales, MIDI note numbers, arrangements)
3. **Voice interaction** — speech-to-text input so the user can talk to the agent hands-free
4. **Web access** — browse sample sites (freesound.org, looperman.com, splice.com, YouTube) to find and download samples
5. **Audio preview** — the agent can play back sounds (both its own synthesized previews of MIDI notes/chords AND samples from the web) so the user can hear ideas before committing them in GarageBand

## Tech Stack
- **Language**: Python
- **AI**: OpenAI SDK with tool-calling orchestration
- **UI**: Flask web app (`templates/index.html` + `static/`)
- **Computer control**: `pyautogui` for executing clicks/keys, `mss` for screenshots
- **Audio**: Needs a library for MIDI synthesis/playback (e.g., `pygame.midi`, `fluidsynth`, or `sounddevice`)
- **Voice**: Speech-to-text (browser Web Speech API)
- **Web**: `requests` or browser automation for sample sites; freesound.org has an API

## Architecture

### Agent Loop (`agent.py`)
- Maintains in-memory message history for the session
- Calls OpenAI Chat Completions with function tools
- Dispatches tool calls: computer control, music theory, AppleScript, web search, audio playback, composition
- Auto-injects screenshot after screen-modifying actions so Codex never acts on stale UI state
- Configurable delays for GarageBand UI animation settling

### Tools
1. **Computer control** (`computer_action`) — screenshot, click, type, key, key sequence, scroll, drag
2. **AppleScript** (`run_applescript`) — launch/activate GarageBand, open projects, trigger menu items (GarageBand's AppleScript support is minimal — use computer control tools for MIDI/track editing)
3. **Music theory** (custom tools):
   - `get_chord_progression` — returns chords with MIDI note numbers
   - `get_midi_notes_for_chord` — chord name → exact MIDI numbers
   - `get_scale_notes` — scale → note names + MIDI numbers
   - `suggest_arrangement` — genre-aware song structure
   - `get_tempo_suggestion` — genre → BPM + time signature
   - `transpose_chord` — transpose with MIDI output
4. **Composition** (`compose_music_idea`, `create_music_in_garageband`) — generate melody/bass/drums and open MIDI in GarageBand
5. **Web/samples** — search and download from sample sites
6. **Audio playback** — synthesize and play MIDI notes or downloaded samples through speakers

### UI
A visual interface (web app or native) running alongside GarageBand with:
- Chat history display
- Microphone button for voice input (speech-to-text)
- Text input as fallback

### System Prompt
Instructs Codex to: always screenshot before acting, prefer keyboard shortcuts, use music theory tools for precise MIDI data before drawing in piano roll, verify each action with screenshots, use AppleScript only for app-level operations.

## Key Design Decisions
- Music theory as structured tools (not just prompting) to get exact MIDI note numbers (0-127) and avoid hallucination
- GarageBand has very limited AppleScript — primary control is via computer use
- Flat file structure, no over-engineering
- Audio preview is critical so user can hear ideas before the agent commits them in GarageBand

## Current Defaults
- UI framework: Flask web app
- Sample source: Freesound API
- Voice input: Browser Web Speech API
- Audio synthesis/playback: `numpy` + `sounddevice` + `soundfile`
