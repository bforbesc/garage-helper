from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Lock
from typing import Any, Callable

import anthropic

from config import settings
from prompts import SYSTEM_PROMPT
from tools import applescript, audio, composer, computer_control, music_theory, samples


class GarageBandAgent:
    def __init__(self) -> None:
        self._lock = Lock()
        self.provider = "anthropic"
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None
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
                i.get("key", "C"), i.get("progression", "I-V-vi-IV"), i.get("octave", 4), i.get("mode", "major")
            ),
            "get_midi_notes_for_chord": lambda i: music_theory.get_midi_notes_for_chord(i["chord"], i.get("octave", 4)),
            "get_scale_notes": lambda i: music_theory.get_scale_notes(i["root"], i.get("scale_type", "major"), i.get("octave", 4)),
            "suggest_arrangement": lambda i: music_theory.suggest_arrangement(i.get("genre", "pop")),
            "get_tempo_suggestion": lambda i: music_theory.get_tempo_suggestion(i.get("genre", "pop")),
            "transpose_chord": lambda i: music_theory.transpose_chord(i["chord"], i["semitones"], i.get("octave", 4)),
            "invert_chord": lambda i: music_theory.invert_chord(i["midi_notes"], i.get("inversion", 1)),
            "compose_music_idea": lambda i: composer.compose_music_idea(
                genre=i.get("genre", "pop"),
                key=i.get("key", "C"),
                scale_type=i.get("scale_type"),
                bars=i.get("bars", 4),
                bpm=i.get("bpm"),
                seed=i.get("seed"),
                include_tracks=i.get("include_tracks"),
                style_hint=i.get("style_hint"),
            ),
            "create_music_in_garageband": self._tool_create_music_in_garageband,
            "search_freesound": lambda i: samples.search_freesound(i["query"], i.get("page_size", 12)),
            "download_sample": lambda i: samples.download_file(i["url"], i.get("filename")),
            "preview_midi_notes": lambda i: audio.preview_midi_notes(i["midi_notes"], i.get("duration_sec", 1.2)),
            "play_audio_file": lambda i: audio.play_audio_file(i["path"]),
            "set_tempo": self._tool_set_tempo,
            "create_software_instrument_track": self._tool_create_software_instrument_track,
            "select_track": self._tool_select_track,
            "add_drummer_tracks": lambda i: applescript.add_drummer_tracks(i.get("repeats", 2)),
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
                "description": (
                    "Run named GarageBand shortcut quickly. Names: play_pause, record, go_to_beginning, "
                    "new_track_dialog, select_track_above, select_track_below, delete_selected, "
                    "undo, redo, duplicate_region, split_at_playhead, join_regions, select_all, "
                    "open_editor, toggle_library, toggle_smart_controls, toggle_cycle, toggle_metronome, "
                    "zoom_in, zoom_out, musical_typing, save_project, create_new_project, export_song, close_project."
                ),
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
            {
                "name": "get_chord_progression",
                "description": "Get chord progression with MIDI notes. Supports major and minor modes.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "progression": {"type": "string"},
                        "octave": {"type": "integer"},
                        "mode": {"type": "string", "enum": ["major", "minor"]},
                    },
                },
            },
            {"name": "get_midi_notes_for_chord", "description": "Get exact MIDI notes for chord. Supports extended chords: 9, min9, 11, 13, add9, 6, min6.", "input_schema": {"type": "object", "properties": {"chord": {"type": "string"}, "octave": {"type": "integer"}}, "required": ["chord"]}},
            {"name": "get_scale_notes", "description": "Get scale note names and MIDI.", "input_schema": {"type": "object", "properties": {"root": {"type": "string"}, "scale_type": {"type": "string"}, "octave": {"type": "integer"}}, "required": ["root"]}},
            {"name": "suggest_arrangement", "description": "Suggest arrangement sections.", "input_schema": {"type": "object", "properties": {"genre": {"type": "string"}}}},
            {"name": "get_tempo_suggestion", "description": "Suggest BPM/time signature.", "input_schema": {"type": "object", "properties": {"genre": {"type": "string"}}}},
            {"name": "transpose_chord", "description": "Transpose chord and return MIDI notes.", "input_schema": {"type": "object", "properties": {"chord": {"type": "string"}, "semitones": {"type": "integer"}, "octave": {"type": "integer"}}, "required": ["chord", "semitones"]}},
            {
                "name": "invert_chord",
                "description": "Invert a chord by rotating bass notes up an octave.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "midi_notes": {"type": "array", "items": {"type": "integer"}},
                        "inversion": {"type": "integer", "description": "1=first inversion, 2=second, etc."},
                    },
                    "required": ["midi_notes"],
                },
            },
            {
                "name": "compose_music_idea",
                "description": "Create melody/chords/bass/drums and export MIDI + rendered WAV. Returns file paths and note events.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "genre": {"type": "string"},
                        "key": {"type": "string"},
                        "scale_type": {"type": "string"},
                        "bars": {"type": "integer"},
                        "bpm": {"type": "integer"},
                        "seed": {"type": "integer"},
                        "include_tracks": {"type": "array", "items": {"type": "string"}, "description": "e.g. ['melody','bass','drums','chords']"},
                        "style_hint": {"type": "string", "description": "e.g. 'legato', 'sparse', 'busy', 'swing'"},
                    },
                },
            },
            {
                "name": "create_music_in_garageband",
                "description": (
                    "Fast path: compose melody/bass/drums/chords, export MIDI+WAV, optionally open MIDI in GarageBand, "
                    "and optionally play the rendered WAV. Set replace_current_project=true only when user explicitly asks "
                    "for a new/open project."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "genre": {"type": "string"},
                        "key": {"type": "string"},
                        "scale_type": {"type": "string"},
                        "bars": {"type": "integer"},
                        "bpm": {"type": "integer"},
                        "seed": {"type": "integer"},
                        "include_tracks": {"type": "array", "items": {"type": "string"}, "description": "e.g. ['melody','bass','drums','chords']"},
                        "style_hint": {"type": "string", "description": "e.g. 'legato', 'sparse', 'busy', 'swing'"},
                        "open_in_garageband": {"type": "boolean"},
                        "replace_current_project": {"type": "boolean"},
                        "auto_play_rendered_audio": {"type": "boolean"},
                    },
                },
            },
            {"name": "search_freesound", "description": "Search Freesound samples.", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "page_size": {"type": "integer"}}, "required": ["query"]}},
            {"name": "download_sample", "description": "Download sample from URL.", "input_schema": {"type": "object", "properties": {"url": {"type": "string"}, "filename": {"type": "string"}}, "required": ["url"]}},
            {"name": "preview_midi_notes", "description": "Synthesize/play MIDI notes.", "input_schema": {"type": "object", "properties": {"midi_notes": {"type": "array", "items": {"type": "integer"}}, "duration_sec": {"type": "number"}}, "required": ["midi_notes"]}},
            {"name": "play_audio_file", "description": "Play local audio file.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
            {
                "name": "set_tempo",
                "description": "Set GarageBand project tempo (BPM). Double-clicks the LCD tempo display and types the new value.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "bpm": {"type": "integer", "description": "Tempo in beats per minute"},
                        "tempo_x": {"type": "integer", "description": "X coordinate of tempo display (default 550)"},
                        "tempo_y": {"type": "integer", "description": "Y coordinate of tempo display (default 35)"},
                    },
                    "required": ["bpm"],
                },
            },
            {
                "name": "create_software_instrument_track",
                "description": "Open the GarageBand new track dialog. Returns a screenshot of the dialog so you can click the right track type and Create button.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "select_track",
                "description": "Select a track by index (0-based). Navigates using arrow keys. Returns a screenshot showing the selected track.",
                "input_schema": {
                    "type": "object",
                    "properties": {"index": {"type": "integer", "description": "0-based track index"}},
                    "required": ["index"],
                },
            },
            {
                "name": "add_drummer_tracks",
                "description": (
                    "Add GarageBand Drummer tracks using app defaults. "
                    "Use repeats=2 to create a primary and second-beat drummer layer."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "repeats": {"type": "integer", "description": "How many Drummer tracks to add (default 2)"},
                    },
                },
            },
        ]

    def reset(self) -> None:
        with self._lock:
            self.text_history = []
            self.project_initialized = True

    def handle_user_message(self, text: str) -> dict[str, Any]:
        with self._lock:
            if not text.strip():
                return {"text": "Please enter a message.", "tool_events": []}
            return self._handle_with_claude(text)

    def _handle_with_claude(self, text: str) -> dict[str, Any]:
        if not self.client:
            return {"text": "ANTHROPIC_API_KEY missing.", "tool_events": []}

        deadline = time.monotonic() + settings.llm_total_timeout_sec
        tool_events: list[dict[str, Any]] = []
        failure_streak = 0
        retry_after_trim = False
        retry_after_empty = False
        working_messages = self._build_working_messages(text)
        last_tool_signature = ""
        repeated_tool_calls = 0

        for _ in range(settings.max_tool_iterations):
            if time.monotonic() > deadline:
                return {"text": "Timed out waiting for model response. Please try again.", "tool_events": tool_events}
            try:
                response = self.client.messages.create(
                    model=settings.claude_model,
                    max_tokens=settings.claude_max_tokens,
                    system=SYSTEM_PROMPT,
                    messages=working_messages,
                    tools=self.tools,
                )
            except anthropic.BadRequestError as exc:
                msg = str(exc)
                if ("too large" in msg.lower() or "too many" in msg.lower()) and not retry_after_trim:
                    retry_after_trim = True
                    self._trim_history_aggressively()
                    working_messages = self._build_working_messages(text)
                    continue
                return {"text": f"Model call failed: {exc}", "tool_events": tool_events}
            except Exception as exc:
                return {"text": f"Model call failed: {exc}", "tool_events": tool_events}

            # Extract text content from response
            assistant_text_parts: list[str] = []
            has_tool_use = False
            for block in response.content:
                if block.type == "text":
                    assistant_text_parts.append(block.text)
                elif block.type == "tool_use":
                    has_tool_use = True
            assistant_content = "\n".join(assistant_text_parts).strip()

            if not has_tool_use:
                # No tool calls — final response
                if not assistant_content and response.stop_reason == "max_tokens" and not retry_after_empty:
                    retry_after_empty = True
                    working_messages.append({"role": "assistant", "content": response.content})
                    working_messages.append({
                        "role": "user",
                        "content": "Answer directly in <=120 tokens. If needed, call one tool, then respond with a concise result.",
                    })
                    continue
                final_text = assistant_content or "No response text was generated. Please try again with a shorter request."
                self._append_text_turn("user", text)
                self._append_text_turn("assistant", final_text)
                return {"text": final_text, "tool_events": tool_events}

            # Has tool calls — append assistant message then execute tools
            working_messages.append({"role": "assistant", "content": response.content})

            tool_results: list[dict[str, Any]] = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                name = block.name
                tool_input = block.input if isinstance(block.input, dict) else {}
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

                # Build tool result content (text summary + optional screenshot image)
                tool_result_content: list[dict[str, Any]] = [
                    {"type": "text", "text": json.dumps(self._compact_result_for_model(result))}
                ]

                # VISION: if result has a screenshot, include it as an image block
                screenshot_path = result.get("post_action_screenshot") or result.get("path", "")
                if screenshot_path and str(screenshot_path).endswith(".png"):
                    b64 = result.get("base64_png") or self._read_screenshot_base64(str(screenshot_path))
                    if b64:
                        tool_result_content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64,
                            },
                        })

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": tool_result_content,
                })

            working_messages.append({"role": "user", "content": tool_results})

        return {"text": "Stopped after too many tool iterations.", "tool_events": tool_events}

    def _read_screenshot_base64(self, path: str) -> str | None:
        """Read and downscale a screenshot file, returning base64 or None."""
        try:
            p = Path(path)
            if not p.exists():
                return None
            return computer_control._downscale_screenshot(p, settings.screenshot_max_width)
        except Exception:
            return None

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
            response: dict[str, Any] = {"ok": True, "path": shot.get("path", ""), "base64_png": shot.get("base64_png", "")}
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
            include_tracks=tool_input.get("include_tracks"),
            style_hint=tool_input.get("style_hint"),
        )
        if not composition.get("ok"):
            return composition
        open_requested = bool(tool_input.get("open_in_garageband", True))
        replace_current = bool(tool_input.get("replace_current_project", False))
        auto_play = bool(tool_input.get("auto_play_rendered_audio", False))
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
        if auto_play:
            audio_path = composition.get("audio_file_path", "")
            play_result = audio.play_audio_file(audio_path) if audio_path else {"ok": False, "error": "No rendered audio file was produced."}
        else:
            play_result = {"ok": True, "skipped": True}
        played_audio = bool(auto_play and play_result.get("ok"))
        if opened:
            self.project_initialized = True
        return {
            "ok": bool(composition.get("ok"))
            and bool(launch_result.get("ok"))
            and bool(open_result.get("ok"))
            and (bool(play_result.get("ok")) or not auto_play),
            "composition": composition,
            "launch_result": launch_result,
            "open_result": open_result,
            "opened_in_garageband": opened,
            "play_result": play_result,
            "played_rendered_audio": played_audio,
        }

    def _tool_set_tempo(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Set tempo by double-clicking LCD display, typing BPM, pressing Enter."""
        bpm = tool_input.get("bpm", 120)
        focus = self._ensure_focus_for_ui_actions()
        if not focus.get("ok"):
            return {"ok": False, "error": "Cannot set tempo without GarageBand focus.", "focus": focus}
        tempo_x = int(tool_input.get("tempo_x", 550))
        tempo_y = int(tool_input.get("tempo_y", 35))
        computer_control.click(x=tempo_x, y=tempo_y, clicks=2)
        time.sleep(0.3)
        computer_control.key_press("command+a")
        time.sleep(0.1)
        computer_control.type_text(str(int(bpm)))
        computer_control.key_press("return")
        result: dict[str, Any] = {"ok": True, "action": "set_tempo", "bpm": bpm}
        result = self._attach_focus_verification(result)
        result["post_action_screenshot"] = computer_control.screenshot().get("path", "")
        return result

    def _tool_create_software_instrument_track(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Open the new track dialog via shortcut."""
        focus = self._ensure_focus_for_ui_actions()
        if not focus.get("ok"):
            return {"ok": False, "error": "Cannot create track without GarageBand focus.", "focus": focus}
        result = computer_control.garageband_shortcut("new_track_dialog")
        time.sleep(0.5)
        result = self._attach_focus_verification(result)
        result["action"] = "create_software_instrument_track"
        result["post_action_screenshot"] = computer_control.screenshot().get("path", "")
        return result

    def _tool_select_track(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Navigate to track by index using arrow keys."""
        index = max(0, int(tool_input.get("index", 0)))
        focus = self._ensure_focus_for_ui_actions()
        if not focus.get("ok"):
            return {"ok": False, "error": "Cannot select track without GarageBand focus.", "focus": focus}
        for _ in range(20):
            computer_control.key_press("up")
        time.sleep(0.1)
        for _ in range(index):
            computer_control.key_press("down")
            time.sleep(0.05)
        result: dict[str, Any] = {"ok": True, "action": "select_track", "index": index}
        result = self._attach_focus_verification(result)
        result["post_action_screenshot"] = computer_control.screenshot().get("path", "")
        return result

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
