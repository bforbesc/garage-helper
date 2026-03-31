from __future__ import annotations

import json
import time
from threading import Lock
from typing import Any, Callable

from openai import OpenAI

from config import settings
from tools import applescript, audio, composer, computer_control, music_theory, samples

SYSTEM_PROMPT = """You are GarageBand Copilot, an AI music production assistant operating GarageBand on macOS.
Rules:
- Keep work in the currently open GarageBand project by default.
- Do not open/replace/create a different project unless the user explicitly asks (for example: "new project", "open project").
- Act quickly: prefer `garageband_shortcut` or `computer_action` with `key_sequence` before click-heavy flows.
- For "create melody/beat/song" requests, prefer `create_music_in_garageband` so the user gets an actual MIDI loaded fast.
- Use music tools to create real musical output (melody/chords/bass/drums) and export MIDI when useful.
- For note/chord precision, use music theory tools before UI entry.
- After any screen-modifying computer action, verify with a screenshot path.
- Do not claim UI edits are done unless tool results show `ok=true` and `focus_confirmed=true`.
- If the same action fails, do not retry more than once; ask user to refocus GarageBand.
- Keep replies concise and execution-focused.
"""


class GarageBandAgent:
    def __init__(self) -> None:
        self._lock = Lock()
        self.provider = "openai"
        self.openai_client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        # Keep only plain text turns in memory; tool chatter remains per-request to avoid malformed histories.
        self.text_history: list[dict[str, str]] = []
        # Safety default: assume user is already working in a project; avoid silent project replacement.
        self.project_initialized = True

        self.tool_handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "computer_action": self._tool_computer_action,
            "garageband_shortcut": self._tool_garageband_shortcut,
            "get_frontmost_app": lambda i: applescript.get_frontmost_app(),
            "ensure_garageband_focus": lambda i: applescript.ensure_garageband_frontmost(i.get("timeout_ms", 1500)),
            "new_garageband_project": self._tool_new_garageband_project,
            "run_applescript": lambda i: applescript.run_applescript(i["script"]),
            "launch_garageband": lambda i: applescript.launch_garageband(),
            "open_file_in_garageband": self._tool_open_file_in_garageband,
            "get_chord_progression": lambda i: music_theory.get_chord_progression(
                i.get("key", "C"), i.get("progression", "I-V-vi-IV"), i.get("octave", 4)
            ),
            "get_midi_notes_for_chord": lambda i: music_theory.get_midi_notes_for_chord(i["chord"], i.get("octave", 4)),
            "get_scale_notes": lambda i: music_theory.get_scale_notes(i["root"], i.get("scale_type", "major"), i.get("octave", 4)),
            "suggest_arrangement": lambda i: music_theory.suggest_arrangement(i.get("genre", "pop")),
            "get_tempo_suggestion": lambda i: music_theory.get_tempo_suggestion(i.get("genre", "pop")),
            "transpose_chord": lambda i: music_theory.transpose_chord(i["chord"], i["semitones"], i.get("octave", 4)),
            "compose_music_idea": lambda i: composer.compose_music_idea(
                genre=i.get("genre", "pop"),
                key=i.get("key", "C"),
                scale_type=i.get("scale_type"),
                bars=i.get("bars", 4),
                bpm=i.get("bpm"),
                seed=i.get("seed"),
            ),
            "create_music_in_garageband": self._tool_create_music_in_garageband,
            "search_freesound": lambda i: samples.search_freesound(i["query"], i.get("page_size", 12)),
            "download_sample": lambda i: samples.download_file(i["url"], i.get("filename")),
            "preview_midi_notes": lambda i: audio.preview_midi_notes(i["midi_notes"], i.get("duration_sec", 1.2)),
            "play_audio_file": lambda i: audio.play_audio_file(i["path"]),
        }

        self.tools = [
            {
                "name": "computer_action",
                "description": "Control local UI: screenshot, click, type, key, key_sequence, scroll, drag.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["screenshot", "click", "type", "key", "key_sequence", "scroll", "drag"]},
                        "x": {"type": "integer"},
                        "y": {"type": "integer"},
                        "button": {"type": "string"},
                        "clicks": {"type": "integer"},
                        "text": {"type": "string"},
                        "key": {"type": "string"},
                        "keys": {"type": "array", "items": {"type": "string"}},
                        "inter_key_delay_ms": {"type": "integer"},
                        "amount": {"type": "integer"},
                        "duration": {"type": "number"},
                    },
                    "required": ["action"],
                },
            },
            {
                "name": "garageband_shortcut",
                "description": "Run named GarageBand shortcut quickly. Names: play_pause, new_track_dialog, open_editor, toggle_library, toggle_smart_controls, toggle_cycle, toggle_metronome, undo, redo, duplicate_region, split_at_playhead, save_project.",
                "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
            },
            {"name": "get_frontmost_app", "description": "Return current frontmost macOS app name.", "input_schema": {"type": "object", "properties": {}}},
            {
                "name": "ensure_garageband_focus",
                "description": "Activate GarageBand and confirm it is frontmost before UI actions.",
                "input_schema": {"type": "object", "properties": {"timeout_ms": {"type": "integer"}}},
            },
            {
                "name": "new_garageband_project",
                "description": "Open GarageBand new project dialog. Use only when user explicitly asks for a new project.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {"name": "run_applescript", "description": "Run AppleScript snippet.", "input_schema": {"type": "object", "properties": {"script": {"type": "string"}}, "required": ["script"]}},
            {"name": "launch_garageband", "description": "Launch and activate GarageBand app.", "input_schema": {"type": "object", "properties": {}}},
            {"name": "open_file_in_garageband", "description": "Open local file (for example MIDI) in GarageBand.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
            {"name": "get_chord_progression", "description": "Get progression with MIDI notes.", "input_schema": {"type": "object", "properties": {"key": {"type": "string"}, "progression": {"type": "string"}, "octave": {"type": "integer"}}}},
            {"name": "get_midi_notes_for_chord", "description": "Get exact MIDI notes for chord.", "input_schema": {"type": "object", "properties": {"chord": {"type": "string"}, "octave": {"type": "integer"}}, "required": ["chord"]}},
            {"name": "get_scale_notes", "description": "Get scale note names and MIDI.", "input_schema": {"type": "object", "properties": {"root": {"type": "string"}, "scale_type": {"type": "string"}, "octave": {"type": "integer"}}, "required": ["root"]}},
            {"name": "suggest_arrangement", "description": "Suggest arrangement sections.", "input_schema": {"type": "object", "properties": {"genre": {"type": "string"}}}},
            {"name": "get_tempo_suggestion", "description": "Suggest BPM/time signature.", "input_schema": {"type": "object", "properties": {"genre": {"type": "string"}}}},
            {"name": "transpose_chord", "description": "Transpose chord and return MIDI notes.", "input_schema": {"type": "object", "properties": {"chord": {"type": "string"}, "semitones": {"type": "integer"}, "octave": {"type": "integer"}}, "required": ["chord", "semitones"]}},
            {
                "name": "compose_music_idea",
                "description": "Create melody/chords/bass/drums and export a MIDI file. Returns MIDI path and note events.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "genre": {"type": "string"},
                        "key": {"type": "string"},
                        "scale_type": {"type": "string"},
                        "bars": {"type": "integer"},
                        "bpm": {"type": "integer"},
                        "seed": {"type": "integer"},
                    },
                },
            },
            {
                "name": "create_music_in_garageband",
                "description": "Fast path: compose melody/bass/drums MIDI and optionally open it in GarageBand. Set replace_current_project=true only when user explicitly asks for a new/open project.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "genre": {"type": "string"},
                        "key": {"type": "string"},
                        "scale_type": {"type": "string"},
                        "bars": {"type": "integer"},
                        "bpm": {"type": "integer"},
                        "seed": {"type": "integer"},
                        "open_in_garageband": {"type": "boolean"},
                        "replace_current_project": {"type": "boolean"},
                    },
                },
            },
            {"name": "search_freesound", "description": "Search Freesound samples.", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "page_size": {"type": "integer"}}, "required": ["query"]}},
            {"name": "download_sample", "description": "Download sample from URL.", "input_schema": {"type": "object", "properties": {"url": {"type": "string"}, "filename": {"type": "string"}}, "required": ["url"]}},
            {"name": "preview_midi_notes", "description": "Synthesize/play MIDI notes.", "input_schema": {"type": "object", "properties": {"midi_notes": {"type": "array", "items": {"type": "integer"}}, "duration_sec": {"type": "number"}}, "required": ["midi_notes"]}},
            {"name": "play_audio_file", "description": "Play local audio file.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
        ]

    def reset(self) -> None:
        with self._lock:
            self.text_history = []
            self.project_initialized = True

    def handle_user_message(self, text: str) -> dict[str, Any]:
        with self._lock:
            if not text.strip():
                return {"text": "Please enter a message.", "tool_events": []}
            return self._handle_with_openai(text)

    def _handle_with_openai(self, text: str) -> dict[str, Any]:
        if not self.openai_client:
            return {"text": "OPENAI_API_KEY missing.", "tool_events": []}

        deadline = time.monotonic() + settings.llm_total_timeout_sec
        tool_events: list[dict[str, Any]] = []
        failure_streak = 0
        retry_after_trim = False
        retry_after_empty = False
        working_messages = self._build_working_messages(text)
        last_tool_signature = ""
        repeated_tool_calls = 0

        for _ in range(8):
            if time.monotonic() > deadline:
                return {"text": "Timed out waiting for model response. Please try again.", "tool_events": tool_events}
            try:
                response = self.openai_client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}] + working_messages,
                    tools=self._openai_tools(),
                    tool_choice="auto",
                    timeout=settings.llm_request_timeout_sec,
                    max_completion_tokens=settings.openai_max_output_tokens,
                    reasoning_effort=settings.openai_reasoning_effort,
                    verbosity=settings.openai_verbosity,
                    parallel_tool_calls=False,
                )
            except Exception as exc:
                msg = str(exc)
                if ("Request too large" in msg or "tokens per min" in msg or "rate_limit_exceeded" in msg) and not retry_after_trim:
                    retry_after_trim = True
                    self._trim_history_aggressively()
                    working_messages = self._build_working_messages(text)
                    continue
                return {"text": f"Model call failed: {exc}", "tool_events": tool_events}

            assistant_msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason
            assistant_content = (assistant_msg.content or "").strip()

            assistant_entry: dict[str, Any] = {"role": "assistant", "content": assistant_content}
            if assistant_msg.tool_calls:
                assistant_entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in assistant_msg.tool_calls
                ]
            working_messages.append(assistant_entry)

            if not assistant_msg.tool_calls:
                if not assistant_content and finish_reason == "length" and not retry_after_empty:
                    retry_after_empty = True
                    working_messages.append(
                        {
                            "role": "user",
                            "content": "Answer directly in <=120 tokens. If needed, call one tool, then respond with a concise result.",
                        }
                    )
                    continue
                final_text = assistant_content or "No response text was generated. Please try again with a shorter request."
                self._append_text_turn("user", text)
                self._append_text_turn("assistant", final_text)
                return {"text": final_text, "tool_events": tool_events}

            for tc in assistant_msg.tool_calls:
                name = tc.function.name
                try:
                    tool_input = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    tool_input = {}
                tool_signature = f"{name}:{json.dumps(tool_input, sort_keys=True)}"
                if tool_signature == last_tool_signature:
                    repeated_tool_calls += 1
                else:
                    repeated_tool_calls = 1
                    last_tool_signature = tool_signature
                if repeated_tool_calls >= 3:
                    return {
                        "text": "Stopped after repeated identical tool calls. Please refocus GarageBand and retry.",
                        "tool_events": tool_events,
                    }
                result = self._safe_tool_execute(name, tool_input)
                tool_events.append({"tool": name, "input": tool_input, "result": result})

                if result.get("ok") is False:
                    failure_streak += 1
                else:
                    failure_streak = 0
                if failure_streak >= 3:
                    return {
                        "text": "Stopped after repeated tool failures. Please confirm GarageBand is focused and computer control is enabled.",
                        "tool_events": tool_events,
                    }

                working_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(self._compact_result_for_model(result)),
                    }
                )

        return {"text": "Stopped after too many tool iterations.", "tool_events": tool_events}

    def _build_working_messages(self, user_text: str) -> list[dict[str, Any]]:
        turns = settings.history_max_turns * 2
        history_tail = self.text_history[-turns:]
        msgs: list[dict[str, Any]] = [{"role": item["role"], "content": item["content"]} for item in history_tail]
        msgs.append({"role": "user", "content": user_text})
        return msgs

    def _append_text_turn(self, role: str, content: str) -> None:
        self.text_history.append({"role": role, "content": content})
        turns = settings.history_max_turns * 2
        if len(self.text_history) > turns:
            self.text_history = self.text_history[-turns:]

    def _trim_history_aggressively(self) -> None:
        # Used only on request-too-large errors.
        keep_turns = max(2, settings.history_max_turns // 2) * 2
        self.text_history = self.text_history[-keep_turns:]

    def _safe_tool_execute(self, name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._execute_tool(name, tool_input)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in self.tool_handlers:
            raise ValueError(f"Unknown tool: {tool_name}")
        return self.tool_handlers[tool_name](tool_input)

    def _ensure_focus_for_ui_actions(self) -> dict[str, Any]:
        if not settings.allow_applescript:
            return {"ok": True, "focus_check_skipped": True, "reason": "AppleScript disabled"}
        if settings.auto_focus_garageband:
            return applescript.ensure_garageband_frontmost(timeout_ms=1500)
        front = applescript.get_frontmost_app()
        if front.get("ok") and front.get("app", "").lower() == "garageband":
            return {"ok": True, "frontmost_app": front.get("app", "")}
        return {
            "ok": False,
            "error": "GarageBand is not frontmost and AUTO_FOCUS_GARAGEBAND=false",
            "frontmost_app": front.get("app", ""),
            "focus_error": front.get("stderr", "") or front.get("error", ""),
        }

    def _attach_focus_verification(self, result: dict[str, Any]) -> dict[str, Any]:
        if not settings.allow_applescript:
            result["focus_check_skipped"] = True
            return result
        front = applescript.get_frontmost_app()
        result["frontmost_after"] = front.get("app", "")
        result["focus_query_ok"] = bool(front.get("ok"))
        focus_confirmed = bool(front.get("ok")) and front.get("app", "").lower() == "garageband"
        result["focus_confirmed"] = focus_confirmed
        if not focus_confirmed:
            result["ok"] = False
            result["error"] = result.get("error") or "Action sent but GarageBand focus was not confirmed."
        return result

    def _tool_garageband_shortcut(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        focus = self._ensure_focus_for_ui_actions()
        if not focus.get("ok"):
            return {"ok": False, "error": "Cannot run shortcut without GarageBand focus.", "focus": focus}
        result = computer_control.garageband_shortcut(tool_input["name"])
        result = self._attach_focus_verification(result)
        result["post_action_screenshot"] = computer_control.screenshot().get("path", "")
        return result

    def _tool_new_garageband_project(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        result = applescript.new_garageband_project_dialog()
        if result.get("ok"):
            self.project_initialized = True
        return result

    def _tool_open_file_in_garageband(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        result = applescript.open_file_in_garageband(tool_input["path"])
        if result.get("ok"):
            self.project_initialized = True
        return result

    def _tool_computer_action(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        action = tool_input.get("action")
        if action == "screenshot":
            shot = computer_control.screenshot()
            response = {"ok": True, "path": shot.get("path", "")}
            if settings.allow_applescript:
                front = applescript.get_frontmost_app()
                response["frontmost_app"] = front.get("app", "")
                response["focus_query_ok"] = bool(front.get("ok"))
            return response
        focus = self._ensure_focus_for_ui_actions()
        if not focus.get("ok"):
            return {
                "ok": False,
                "error": "Blocked UI action because GarageBand focus is not confirmed.",
                "focus": focus,
                "post_action_screenshot": computer_control.screenshot().get("path", ""),
            }
        if action == "click":
            result = computer_control.click(
                x=int(tool_input["x"]),
                y=int(tool_input["y"]),
                button=tool_input.get("button", "left"),
                clicks=int(tool_input.get("clicks", 1)),
            )
            result = self._attach_focus_verification(result)
            result["post_action_screenshot"] = computer_control.screenshot().get("path", "")
            return result
        if action == "type":
            result = computer_control.type_text(tool_input["text"])
            result = self._attach_focus_verification(result)
            result["post_action_screenshot"] = computer_control.screenshot().get("path", "")
            return result
        if action == "key":
            result = computer_control.key_press(tool_input["key"])
            result = self._attach_focus_verification(result)
            result["post_action_screenshot"] = computer_control.screenshot().get("path", "")
            return result
        if action == "key_sequence":
            result = computer_control.key_sequence(
                keys=tool_input.get("keys", []),
                inter_key_delay_ms=int(tool_input.get("inter_key_delay_ms", 70)),
            )
            result = self._attach_focus_verification(result)
            result["post_action_screenshot"] = computer_control.screenshot().get("path", "")
            return result
        if action == "scroll":
            result = computer_control.scroll(int(tool_input.get("amount", -400)))
            result = self._attach_focus_verification(result)
            result["post_action_screenshot"] = computer_control.screenshot().get("path", "")
            return result
        if action == "drag":
            result = computer_control.drag(
                x=int(tool_input["x"]),
                y=int(tool_input["y"]),
                duration=float(tool_input.get("duration", 0.2)),
            )
            result = self._attach_focus_verification(result)
            result["post_action_screenshot"] = computer_control.screenshot().get("path", "")
            return result
        raise ValueError(f"Unsupported action: {action}")

    def _tool_create_music_in_garageband(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        composition = composer.compose_music_idea(
            genre=tool_input.get("genre", "pop"),
            key=tool_input.get("key", "C"),
            scale_type=tool_input.get("scale_type"),
            bars=tool_input.get("bars", 4),
            bpm=tool_input.get("bpm"),
            seed=tool_input.get("seed"),
        )
        if not composition.get("ok"):
            return composition
        open_requested = bool(tool_input.get("open_in_garageband", True))
        replace_current = bool(tool_input.get("replace_current_project", False))
        if open_requested and self.project_initialized and not replace_current:
            return {
                "ok": False,
                "error": (
                    "Refusing to replace current project without explicit permission. "
                    "Set replace_current_project=true only when the user explicitly asks for a new/open project."
                ),
                "composition": composition,
                "opened_in_garageband": False,
            }
        launch_result = applescript.launch_garageband() if open_requested else {"ok": True, "skipped": True}
        open_result = applescript.open_file_in_garageband(composition["midi_file_path"]) if open_requested else {"ok": True, "skipped": True}
        opened = bool(open_requested and launch_result.get("ok") and open_result.get("ok"))
        if opened:
            self.project_initialized = True
        return {
            "ok": bool(composition.get("ok")) and bool(launch_result.get("ok")) and bool(open_result.get("ok")),
            "composition": composition,
            "launch_result": launch_result,
            "open_result": open_result,
            "opened_in_garageband": opened,
        }

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

    def _compact_result_for_model(self, data: Any) -> Any:
        if isinstance(data, dict):
            compact: dict[str, Any] = {}
            for k, v in data.items():
                if k.lower() in {"base64_png", "image_base64", "screenshot_base64"}:
                    continue
                compact[k] = self._compact_result_for_model(v)
            return compact
        if isinstance(data, list):
            return [self._compact_result_for_model(v) for v in data[:120]]
        if isinstance(data, str):
            return data if len(data) <= 1400 else data[:1400] + "...(truncated)"
        return data
