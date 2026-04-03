from __future__ import annotations

import time
import traceback
from collections import deque
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

from agent import GarageBandAgent
from config import settings
from tools import applescript, audio, music_theory, samples

app = Flask(__name__)
app.secret_key = settings.app_secret
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
agent = GarageBandAgent()
recent_debug_events: deque[dict] = deque(maxlen=50)


@app.context_processor
def inject_asset_version():
    app_js = Path(app.root_path) / "static" / "app.js"
    style_css = Path(app.root_path) / "static" / "style.css"
    version = int(max(app_js.stat().st_mtime, style_css.stat().st_mtime))
    return {
        "asset_version": version,
        "ui_request_timeout_ms": settings.ui_request_timeout_ms,
        "voice_input_enabled": settings.enable_voice_input,
    }


@app.get("/api/health")
def api_health():
    return jsonify(
        {
            "ok": True,
            "provider": agent.provider,
            "api_key_loaded": bool(settings.anthropic_api_key),
            "computer_control_enabled": settings.enable_computer_control,
            "applescript_enabled": settings.allow_applescript,
        }
    )


@app.get("/api/debug/events")
def api_debug_events():
    return jsonify({"ok": True, "events": list(recent_debug_events)})


@app.get("/")
def index():
    return render_template("index.html")


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _compact_debug_payload(data, max_items: int = 20):
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            if k.lower() in {"base64_png", "image_base64", "screenshot_base64"}:
                continue
            out[k] = _compact_debug_payload(v, max_items=max_items)
        return out
    if isinstance(data, list):
        return [_compact_debug_payload(v, max_items=max_items) for v in data[:max_items]]
    if isinstance(data, str):
        return data if len(data) <= 500 else data[:500] + "...(truncated)"
    return data


@app.post("/api/chat")
def api_chat():
    payload = request.get_json(force=True, silent=True) or {}
    message = payload.get("message", "")
    try:
        started = time.time()
        result = agent.handle_user_message(message)
        elapsed_ms = int((time.time() - started) * 1000)
        compact_tool_events = _compact_debug_payload(result.get("tool_events", []), max_items=8)
        recent_debug_events.append(
            {
                "ts": int(time.time()),
                "message": message,
                "provider": agent.provider,
                "elapsed_ms": elapsed_ms,
                "tool_events": compact_tool_events,
                "text_preview": (result.get("text", "") or "")[:200],
            }
        )
        response_payload = dict(result)
        response_payload["tool_events"] = compact_tool_events
        return jsonify({"ok": True, **response_payload})
    except Exception as exc:
        recent_debug_events.append(
            {
                "ts": int(time.time()),
                "message": message,
                "provider": agent.provider,
                "error": str(exc),
            }
        )
        return jsonify({"ok": False, "error": str(exc), "trace": traceback.format_exc()}), 500


@app.post("/api/reset")
def api_reset():
    agent.reset()
    return jsonify({"ok": True})


@app.post("/api/workflow/create-jungle")
def api_workflow_create_jungle():
    payload = request.get_json(force=True, silent=True) or {}
    bars = int(payload.get("bars", 8))
    bpm = int(payload.get("bpm", 120))
    key = payload.get("key", "C")
    project_mode = str(payload.get("project_mode", "")).strip().lower()
    replace_current_project = payload.get("replace_current_project")
    if not project_mode:
        if replace_current_project is True:
            project_mode = "new"
        elif replace_current_project is False:
            project_mode = "auto"
        else:
            project_mode = "auto"
    auto_play = bool(payload.get("auto_play_rendered_audio", False))
    try:
        result = agent._tool_create_music_in_garageband(
            {
                "genre": "jungle",
                "key": key,
                "scale_type": "minor",
                "bars": bars,
                "bpm": bpm,
                "include_tracks": ["melody", "bass", "drums"],
                "style_hint": "busy",
                "open_in_garageband": True,
                "project_mode": project_mode,
                "auto_play_rendered_audio": auto_play,
            }
        )
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/workflow/add-drummer-second-beat")
def api_workflow_add_drummer_second_beat():
    payload = request.get_json(force=True, silent=True) or {}
    repeats = int(payload.get("repeats", 2))
    try:
        drummer_result = applescript.add_drummer_tracks(repeats=repeats)
        return jsonify(
            {
                "ok": bool(drummer_result.get("ok")),
                "result": drummer_result,
                "note": "Drummer tracks use GarageBand default type set to NTCDrummer.",
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/workflow/play-latest")
def api_workflow_play_latest():
    try:
        latest = sorted(Path(settings.downloads_dir).glob("idea_*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not latest:
            return jsonify({"ok": False, "error": "No rendered WAV files found in downloads."}), 404
        play_result = audio.play_audio_file(str(latest[0]))
        return jsonify({"ok": bool(play_result.get("ok")), "latest_audio": str(latest[0].resolve()), "play_result": play_result})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.get("/api/samples/search")
def api_samples_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"ok": False, "error": "Missing query parameter q"}), 400
    try:
        result = samples.search_freesound(query)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/samples/download")
def api_samples_download():
    payload = request.get_json(force=True, silent=True) or {}
    url = payload.get("url", "").strip()
    filename = payload.get("filename")
    if not url:
        return jsonify({"ok": False, "error": "Missing url"}), 400
    try:
        result = samples.download_file(url, filename=filename)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/audio/preview-chord")
def api_preview_chord():
    payload = request.get_json(force=True, silent=True) or {}
    chord = payload.get("chord", "Cm7")
    octave = int(payload.get("octave", 4))
    duration_sec = float(payload.get("duration_sec", 1.2))
    try:
        chord_data = music_theory.get_midi_notes_for_chord(chord=chord, octave=octave)
        result = audio.preview_midi_notes(chord_data["midi_notes"], duration_sec=duration_sec)
        return jsonify({"ok": True, "chord": chord_data, "audio": result})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/audio/play-file")
def api_play_file():
    payload = request.get_json(force=True, silent=True) or {}
    path = payload.get("path", "")
    if not path:
        return jsonify({"ok": False, "error": "Missing path"}), 400
    if not Path(path).exists():
        return jsonify({"ok": False, "error": "File not found"}), 404
    try:
        result = audio.play_audio_file(path)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


if __name__ == "__main__":
    if settings.auto_open_garageband:
        applescript.launch_garageband()
    app.run(host="127.0.0.1", port=settings.ui_port, debug=settings.flask_debug)
