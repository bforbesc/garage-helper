from __future__ import annotations

import json
from threading import Lock
from typing import Any, Callable

import anthropic
try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

from config import settings
from tools import applescript, audio, computer_control, music_theory, samples

SYSTEM_PROMPT = """You are GarageBand Copilot, an AI music production assistant operating GarageBand on macOS.
Rules:
- Prefer keyboard shortcuts before mouse clicks.
- For editing notes/chords, first use music theory tools to get exact MIDI note numbers.
- Use app-level operations through AppleScript; use computer actions for UI manipulation.
- After any screen-modifying computer action, verify state using a screenshot.
- When recommending samples, mention source and license when available.
- Keep instructions concise and production-focused.
"""


class GarageBandAgent:
    def __init__(self) -> None:
        self._lock = Lock()
        self.provider = self._resolve_provider()
        self.anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None
        self.openai_client = OpenAI(api_key=settings.openai_api_key) if (settings.openai_api_key and OpenAI) else None

        self.anthropic_messages: list[dict[str, Any]] = []
        self.openai_messages: list[dict[str, Any]] = []

        self.tool_handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "computer_action": self._tool_computer_action,
            "run_applescript": lambda i: applescript.run_applescript(i["script"]),
            "launch_garageband": lambda i: applescript.launch_garageband(),
            "get_chord_progression": lambda i: music_theory.get_chord_progression(
                i.get("key", "C"), i.get("progression", "I-V-vi-IV"), i.get("octave", 4)
            ),
            "get_midi_notes_for_chord": lambda i: music_theory.get_midi_notes_for_chord(i["chord"], i.get("octave", 4)),
            "get_scale_notes": lambda i: music_theory.get_scale_notes(i["root"], i.get("scale_type", "major"), i.get("octave", 4)),
            "suggest_arrangement": lambda i: music_theory.suggest_arrangement(i.get("genre", "pop")),
            "get_tempo_suggestion": lambda i: music_theory.get_tempo_suggestion(i.get("genre", "pop")),
            "transpose_chord": lambda i: music_theory.transpose_chord(i["chord"], i["semitones"], i.get("octave", 4)),
            "search_freesound": lambda i: samples.search_freesound(i["query"], i.get("page_size", 12)),
            "download_sample": lambda i: samples.download_file(i["url"], i.get("filename")),
            "preview_midi_notes": lambda i: audio.preview_midi_notes(i["midi_notes"], i.get("duration_sec", 1.2)),
            "play_audio_file": lambda i: audio.play_audio_file(i["path"]),
        }

        self.tools = [
            {
                "name": "computer_action",
                "description": "Control the local computer UI: screenshot, click, type, key, scroll, drag.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["screenshot", "click", "type", "key", "scroll", "drag"]},
                        "x": {"type": "integer"},
                        "y": {"type": "integer"},
                        "button": {"type": "string"},
                        "clicks": {"type": "integer"},
                        "text": {"type": "string"},
                        "key": {"type": "string"},
                        "amount": {"type": "integer"},
                        "duration": {"type": "number"},
                    },
                    "required": ["action"],
                },
            },
            {
                "name": "run_applescript",
                "description": "Run an AppleScript snippet.",
                "input_schema": {"type": "object", "properties": {"script": {"type": "string"}}, "required": ["script"]},
            },
            {
                "name": "launch_garageband",
                "description": "Launch and activate GarageBand app.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_chord_progression",
                "description": "Get a progression in a key with MIDI note numbers.",
                "input_schema": {
                    "type": "object",
                    "properties": {"key": {"type": "string"}, "progression": {"type": "string"}, "octave": {"type": "integer"}},
                },
            },
            {
                "name": "get_midi_notes_for_chord",
                "description": "Get exact MIDI notes for a chord.",
                "input_schema": {
                    "type": "object",
                    "properties": {"chord": {"type": "string"}, "octave": {"type": "integer"}},
                    "required": ["chord"],
                },
            },
            {
                "name": "get_scale_notes",
                "description": "Get scale note names and MIDI values.",
                "input_schema": {
                    "type": "object",
                    "properties": {"root": {"type": "string"}, "scale_type": {"type": "string"}, "octave": {"type": "integer"}},
                    "required": ["root"],
                },
            },
            {
                "name": "suggest_arrangement",
                "description": "Suggest genre-aware arrangement sections.",
                "input_schema": {"type": "object", "properties": {"genre": {"type": "string"}}},
            },
            {
                "name": "get_tempo_suggestion",
                "description": "Suggest BPM and time signature by genre.",
                "input_schema": {"type": "object", "properties": {"genre": {"type": "string"}}},
            },
            {
                "name": "transpose_chord",
                "description": "Transpose a chord and return MIDI note numbers.",
                "input_schema": {
                    "type": "object",
                    "properties": {"chord": {"type": "string"}, "semitones": {"type": "integer"}, "octave": {"type": "integer"}},
                    "required": ["chord", "semitones"],
                },
            },
            {
                "name": "search_freesound",
                "description": "Search Freesound for samples.",
                "input_schema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}, "page_size": {"type": "integer"}},
                    "required": ["query"],
                },
            },
            {
                "name": "download_sample",
                "description": "Download a sample file from URL.",
                "input_schema": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}, "filename": {"type": "string"}},
                    "required": ["url"],
                },
            },
            {
                "name": "preview_midi_notes",
                "description": "Synthesize and play MIDI notes through speakers.",
                "input_schema": {
                    "type": "object",
                    "properties": {"midi_notes": {"type": "array", "items": {"type": "integer"}}, "duration_sec": {"type": "number"}},
                    "required": ["midi_notes"],
                },
            },
            {
                "name": "play_audio_file",
                "description": "Play an audio file through speakers.",
                "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            },
        ]

    def reset(self) -> None:
        with self._lock:
            self.anthropic_messages = []
            self.openai_messages = []

    def handle_user_message(self, text: str) -> dict[str, Any]:
        with self._lock:
            if not text.strip():
                return {"text": "Please enter a message.", "tool_events": []}
            if self.provider == "anthropic":
                return self._handle_with_anthropic(text)
            if self.provider == "openai":
                return self._handle_with_openai(text)
            return {
                "text": "No model key configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.",
                "tool_events": [],
            }

    def _handle_with_anthropic(self, text: str) -> dict[str, Any]:
        if not self.anthropic_client:
            return {"text": "ANTHROPIC_API_KEY missing.", "tool_events": []}

        self.anthropic_messages.append({"role": "user", "content": text})
        tool_events: list[dict[str, Any]] = []
        for _ in range(8):
            response = self.anthropic_client.messages.create(
                model=settings.anthropic_model,
                system=SYSTEM_PROMPT,
                messages=self.anthropic_messages,
                tools=self.tools,
                max_tokens=settings.anthropic_max_tokens,
            )
            assistant_blocks = [self._block_to_dict(block) for block in response.content]
            self.anthropic_messages.append({"role": "assistant", "content": assistant_blocks})

            tool_uses = [b for b in assistant_blocks if b.get("type") == "tool_use"]
            if not tool_uses:
                final_text = "".join([b.get("text", "") for b in assistant_blocks if b.get("type") == "text"]).strip()
                self.openai_messages.extend(
                    [
                        {"role": "user", "content": text},
                        {"role": "assistant", "content": final_text or "(No text response)"},
                    ]
                )
                return {"text": final_text or "(No text response)", "tool_events": tool_events}

            results_for_model = []
            for tool_use in tool_uses:
                name = tool_use["name"]
                tool_input = tool_use.get("input", {})
                result = self._safe_tool_execute(name, tool_input)
                tool_events.append({"tool": name, "input": tool_input, "result": result})
                results_for_model.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use["id"],
                        "content": json.dumps(result),
                    }
                )

            self.anthropic_messages.append({"role": "user", "content": results_for_model})

        return {"text": "Stopped after too many tool iterations.", "tool_events": tool_events}

    def _handle_with_openai(self, text: str) -> dict[str, Any]:
        if OpenAI is None:
            return {"text": "OpenAI SDK is not installed. Run: pip install -r requirements.txt", "tool_events": []}
        if not self.openai_client:
            return {"text": "OPENAI_API_KEY missing.", "tool_events": []}

        self.openai_messages.append({"role": "user", "content": text})
        tool_events: list[dict[str, Any]] = []
        for _ in range(8):
            response = self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self.openai_messages,
                tools=self._openai_tools(),
                tool_choice="auto",
            )
            msg = response.choices[0].message
            assistant_content = msg.content or ""

            assistant_message: dict[str, Any] = {"role": "assistant", "content": assistant_content}
            if msg.tool_calls:
                assistant_message["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ]
            self.openai_messages.append(assistant_message)

            if not msg.tool_calls:
                self.anthropic_messages.extend(
                    [
                        {"role": "user", "content": text},
                        {"role": "assistant", "content": [{"type": "text", "text": assistant_content or "(No text response)"}]},
                    ]
                )
                return {"text": assistant_content or "(No text response)", "tool_events": tool_events}

            for tc in msg.tool_calls:
                name = tc.function.name
                tool_input = json.loads(tc.function.arguments or "{}")
                result = self._safe_tool_execute(name, tool_input)
                tool_events.append({"tool": name, "input": tool_input, "result": result})
                self.openai_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result),
                    }
                )

        return {"text": "Stopped after too many tool iterations.", "tool_events": tool_events}

    def _safe_tool_execute(self, name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._execute_tool(name, tool_input)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in self.tool_handlers:
            raise ValueError(f"Unknown tool: {tool_name}")
        return self.tool_handlers[tool_name](tool_input)

    def _tool_computer_action(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        action = tool_input.get("action")
        if action == "screenshot":
            return computer_control.screenshot()
        if action == "click":
            result = computer_control.click(
                x=int(tool_input["x"]),
                y=int(tool_input["y"]),
                button=tool_input.get("button", "left"),
                clicks=int(tool_input.get("clicks", 1)),
            )
            result["post_action_screenshot"] = computer_control.screenshot()["path"]
            return result
        if action == "type":
            result = computer_control.type_text(tool_input["text"])
            result["post_action_screenshot"] = computer_control.screenshot()["path"]
            return result
        if action == "key":
            result = computer_control.key_press(tool_input["key"])
            result["post_action_screenshot"] = computer_control.screenshot()["path"]
            return result
        if action == "scroll":
            result = computer_control.scroll(int(tool_input.get("amount", -400)))
            result["post_action_screenshot"] = computer_control.screenshot()["path"]
            return result
        if action == "drag":
            result = computer_control.drag(
                x=int(tool_input["x"]),
                y=int(tool_input["y"]),
                duration=float(tool_input.get("duration", 0.2)),
            )
            result["post_action_screenshot"] = computer_control.screenshot()["path"]
            return result
        raise ValueError(f"Unsupported action: {action}")

    def _openai_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
            for tool in self.tools
        ]

    @staticmethod
    def _block_to_dict(block: Any) -> dict[str, Any]:
        if hasattr(block, "model_dump"):
            return block.model_dump()
        return dict(block)

    @staticmethod
    def _resolve_provider() -> str:
        requested = settings.llm_provider.strip().lower()
        if requested in {"anthropic", "openai"}:
            return requested
        if settings.openai_api_key and OpenAI is not None:
            return "openai"
        if settings.anthropic_api_key:
            return "anthropic"
        return "none"
