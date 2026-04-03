from __future__ import annotations

import agent as agent_module


def test_create_music_in_garageband_tool(monkeypatch):
    a = agent_module.GarageBandAgent()

    monkeypatch.setattr(
        agent_module.composer,
        "compose_music_idea",
        lambda **_: {"ok": True, "midi_file_path": "/tmp/test.mid", "tracks": {"melody": []}},
    )
    monkeypatch.setattr(
        a,
        "_tool_get_garageband_project_state",
        lambda: {"ok": True, "garageband_running": False, "has_open_project": False, "window_titles": []},
    )
    monkeypatch.setattr(agent_module.applescript, "launch_garageband", lambda: {"ok": True})
    monkeypatch.setattr(
        agent_module.applescript,
        "open_file_in_garageband",
        lambda path: {"ok": True, "path": path},
    )

    out = a._tool_create_music_in_garageband({"genre": "pop", "key": "C"})
    assert out["ok"] is True
    assert out["composition"]["midi_file_path"] == "/tmp/test.mid"
    assert out["open_result"]["path"] == "/tmp/test.mid"


def test_create_music_in_garageband_tool_open_disabled(monkeypatch):
    a = agent_module.GarageBandAgent()

    monkeypatch.setattr(
        agent_module.composer,
        "compose_music_idea",
        lambda **_: {"ok": True, "midi_file_path": "/tmp/test.mid"},
    )
    monkeypatch.setattr(
        a,
        "_tool_get_garageband_project_state",
        lambda: {"ok": True, "garageband_running": False, "has_open_project": False, "window_titles": []},
    )

    out = a._tool_create_music_in_garageband({"open_in_garageband": False})
    assert out["ok"] is True
    assert out["launch_result"]["skipped"] is True
    assert out["open_result"]["skipped"] is True


def test_create_music_in_garageband_auto_mode_keeps_current_project(monkeypatch):
    a = agent_module.GarageBandAgent()
    monkeypatch.setattr(
        agent_module.composer,
        "compose_music_idea",
        lambda **_: {"ok": True, "midi_file_path": "/tmp/test.mid"},
    )
    monkeypatch.setattr(
        a,
        "_tool_get_garageband_project_state",
        lambda: {"ok": True, "garageband_running": True, "has_open_project": True, "window_titles": ["Song - Tracks"]},
    )
    monkeypatch.setattr(agent_module.applescript, "launch_garageband", lambda: {"ok": True})
    seen = {"open_called": False}

    def fake_open(_path):
        seen["open_called"] = True
        return {"ok": True}

    monkeypatch.setattr(agent_module.applescript, "open_file_in_garageband", fake_open)

    out = a._tool_create_music_in_garageband({"open_in_garageband": True, "project_mode": "auto"})
    assert out["ok"] is True
    assert out["resolved_project_mode"] == "current"
    assert out["open_result"]["skipped"] is True
    assert seen["open_called"] is False


def test_create_music_in_garageband_new_mode_opens_new_project(monkeypatch):
    a = agent_module.GarageBandAgent()
    monkeypatch.setattr(
        agent_module.composer,
        "compose_music_idea",
        lambda **_: {"ok": True, "midi_file_path": "/tmp/test.mid"},
    )
    monkeypatch.setattr(
        a,
        "_tool_get_garageband_project_state",
        lambda: {"ok": True, "garageband_running": True, "has_open_project": True, "window_titles": ["Song - Tracks"]},
    )
    monkeypatch.setattr(agent_module.applescript, "launch_garageband", lambda: {"ok": True})
    monkeypatch.setattr(agent_module.applescript, "open_file_in_garageband", lambda path: {"ok": True, "path": path})
    out = a._tool_create_music_in_garageband({"open_in_garageband": True, "project_mode": "new"})
    assert out["ok"] is True
    assert out["resolved_project_mode"] == "new"
    assert out["opened_in_garageband"] is True


def test_create_music_in_garageband_legacy_replace_flag_maps_to_new(monkeypatch):
    a = agent_module.GarageBandAgent()
    monkeypatch.setattr(
        agent_module.composer,
        "compose_music_idea",
        lambda **_: {"ok": True, "midi_file_path": "/tmp/test.mid"},
    )
    monkeypatch.setattr(
        a,
        "_tool_get_garageband_project_state",
        lambda: {"ok": True, "garageband_running": True, "has_open_project": True, "window_titles": ["Song - Tracks"]},
    )
    monkeypatch.setattr(agent_module.applescript, "launch_garageband", lambda: {"ok": True})
    monkeypatch.setattr(agent_module.applescript, "open_file_in_garageband", lambda path: {"ok": True, "path": path})

    out = a._tool_create_music_in_garageband({"open_in_garageband": True, "replace_current_project": True})
    assert out["ok"] is True
    assert out["project_mode"] == "new"
    assert out["resolved_project_mode"] == "new"


def test_create_music_in_garageband_ask_mode_requests_choice(monkeypatch):
    a = agent_module.GarageBandAgent()
    monkeypatch.setattr(
        agent_module.composer,
        "compose_music_idea",
        lambda **_: {"ok": True, "midi_file_path": "/tmp/test.mid"},
    )
    monkeypatch.setattr(
        a,
        "_tool_get_garageband_project_state",
        lambda: {"ok": True, "garageband_running": True, "has_open_project": True, "window_titles": ["Song - Tracks"]},
    )
    out = a._tool_create_music_in_garageband({"open_in_garageband": True, "project_mode": "ask"})
    assert out["ok"] is False
    assert out["needs_project_choice"] is True


def test_create_music_in_garageband_current_mode_requires_open_project(monkeypatch):
    a = agent_module.GarageBandAgent()
    monkeypatch.setattr(
        agent_module.composer,
        "compose_music_idea",
        lambda **_: {"ok": True, "midi_file_path": "/tmp/test.mid"},
    )
    monkeypatch.setattr(
        a,
        "_tool_get_garageband_project_state",
        lambda: {"ok": True, "garageband_running": False, "has_open_project": False, "window_titles": []},
    )
    out = a._tool_create_music_in_garageband({"open_in_garageband": True, "project_mode": "current"})
    assert out["ok"] is False
    assert "requires an open garageband project" in out["error"].lower()


def test_shortcut_blocks_without_focus(monkeypatch):
    a = agent_module.GarageBandAgent()
    monkeypatch.setattr(a, "_ensure_focus_for_ui_actions", lambda: {"ok": False, "error": "no focus"})
    out = a._tool_garageband_shortcut({"name": "play_pause"})
    assert out["ok"] is False
    assert "focus" in out


def test_computer_action_key_blocks_without_focus(monkeypatch):
    a = agent_module.GarageBandAgent()
    monkeypatch.setattr(a, "_ensure_focus_for_ui_actions", lambda: {"ok": False, "error": "no focus"})
    monkeypatch.setattr(agent_module.computer_control, "screenshot", lambda: {"path": "screenshots/test.png"})
    out = a._tool_computer_action({"action": "key", "key": "space"})
    assert out["ok"] is False
    assert out["post_action_screenshot"] == "screenshots/test.png"


def test_new_project_tool_updates_project_state(monkeypatch):
    a = agent_module.GarageBandAgent()
    a.project_initialized = False
    monkeypatch.setattr(agent_module.applescript, "new_garageband_project_dialog", lambda: {"ok": True})
    out = a._tool_new_garageband_project({})
    assert out["ok"] is True
    assert a.project_initialized is True


def test_create_music_in_garageband_auto_play_rendered_audio(monkeypatch):
    a = agent_module.GarageBandAgent()

    monkeypatch.setattr(
        agent_module.composer,
        "compose_music_idea",
        lambda **_: {"ok": True, "midi_file_path": "/tmp/test.mid", "audio_file_path": "/tmp/test.wav"},
    )
    monkeypatch.setattr(
        a,
        "_tool_get_garageband_project_state",
        lambda: {"ok": True, "garageband_running": False, "has_open_project": False, "window_titles": []},
    )
    monkeypatch.setattr(agent_module.applescript, "launch_garageband", lambda: {"ok": True})
    monkeypatch.setattr(agent_module.applescript, "open_file_in_garageband", lambda path: {"ok": True, "path": path})

    seen = {}

    def fake_play(path):
        seen["path"] = path
        return {"ok": True, "path": path}

    monkeypatch.setattr(agent_module.audio, "play_audio_file", fake_play)

    out = a._tool_create_music_in_garageband({"auto_play_rendered_audio": True})
    assert out["ok"] is True
    assert out["played_rendered_audio"] is True
    assert out["play_result"]["ok"] is True
    assert seen["path"] == "/tmp/test.wav"


def test_create_music_in_garageband_auto_play_missing_audio_fails(monkeypatch):
    a = agent_module.GarageBandAgent()

    monkeypatch.setattr(
        agent_module.composer,
        "compose_music_idea",
        lambda **_: {"ok": True, "midi_file_path": "/tmp/test.mid"},
    )
    monkeypatch.setattr(
        a,
        "_tool_get_garageband_project_state",
        lambda: {"ok": True, "garageband_running": False, "has_open_project": False, "window_titles": []},
    )
    monkeypatch.setattr(agent_module.applescript, "launch_garageband", lambda: {"ok": True})
    monkeypatch.setattr(agent_module.applescript, "open_file_in_garageband", lambda path: {"ok": True, "path": path})

    out = a._tool_create_music_in_garageband({"auto_play_rendered_audio": True})
    assert out["ok"] is False
    assert out["play_result"]["ok"] is False


def test_create_music_in_garageband_passes_allow_out_of_key_flag(monkeypatch):
    a = agent_module.GarageBandAgent()
    captured = {}

    def fake_compose(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "midi_file_path": "/tmp/test.mid", "audio_file_path": "/tmp/test.wav"}

    monkeypatch.setattr(agent_module.composer, "compose_music_idea", fake_compose)
    monkeypatch.setattr(
        a,
        "_tool_get_garageband_project_state",
        lambda: {"ok": True, "garageband_running": False, "has_open_project": False, "window_titles": []},
    )
    monkeypatch.setattr(agent_module.applescript, "launch_garageband", lambda: {"ok": True})
    monkeypatch.setattr(agent_module.applescript, "open_file_in_garageband", lambda path: {"ok": True, "path": path})

    out = a._tool_create_music_in_garageband({"allow_out_of_key_notes": True, "open_in_garageband": False})
    assert out["ok"] is True
    assert captured["allow_out_of_key_notes"] is True
