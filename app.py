from __future__ import annotations

import traceback
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from agent import GarageBandAgent
from config import settings
from tools import audio, music_theory, samples

app = Flask(__name__)
app.secret_key = settings.app_secret
agent = GarageBandAgent()


@app.get("/api/health")
def api_health():
    return jsonify(
        {
            "ok": True,
            "provider": agent.provider,
            "computer_control_enabled": settings.enable_computer_control,
            "applescript_enabled": settings.allow_applescript,
        }
    )


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/chat")
def api_chat():
    payload = request.get_json(force=True, silent=True) or {}
    message = payload.get("message", "")
    try:
        result = agent.handle_user_message(message)
        return jsonify({"ok": True, **result})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc), "trace": traceback.format_exc()}), 500


@app.post("/api/reset")
def api_reset():
    agent.reset()
    return jsonify({"ok": True})


@app.post("/api/tts")
def api_tts():
    payload = request.get_json(force=True, silent=True) or {}
    text = payload.get("text", "")
    try:
        result = audio.speak(text)
        return jsonify(result)
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
    app.run(host="127.0.0.1", port=settings.ui_port, debug=True)
