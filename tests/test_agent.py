from __future__ import annotations

import agent as agent_module


def test_create_music_in_garageband_tool(monkeypatch):
    a = agent_module.GarageBandAgent()
    a.project_initialized = False

    monkeypatch.setattr(
        agent_module.composer,
        "compose_music_idea",
        lambda **_: {"ok": True, "midi_file_path": "/tmp/test.mid", "tracks": {"melody": []}},
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

    out = a._tool_create_music_in_garageband({"open_in_garageband": False})
    assert out["ok"] is True
    assert out["launch_result"]["skipped"] is True
    assert out["open_result"]["skipped"] is True


def test_create_music_in_garageband_blocks_replacement_without_flag(monkeypatch):
    a = agent_module.GarageBandAgent()
    a.project_initialized = True
    monkeypatch.setattr(
        agent_module.composer,
        "compose_music_idea",
        lambda **_: {"ok": True, "midi_file_path": "/tmp/test.mid"},
    )
    out = a._tool_create_music_in_garageband({"open_in_garageband": True})
    assert out["ok"] is False
    assert "replace current project" in out["error"].lower()


def test_create_music_in_garageband_allows_replacement_with_flag(monkeypatch):
    a = agent_module.GarageBandAgent()
    a.project_initialized = True
    monkeypatch.setattr(
        agent_module.composer,
        "compose_music_idea",
        lambda **_: {"ok": True, "midi_file_path": "/tmp/test.mid"},
    )
    monkeypatch.setattr(agent_module.applescript, "launch_garageband", lambda: {"ok": True})
    monkeypatch.setattr(agent_module.applescript, "open_file_in_garageband", lambda path: {"ok": True, "path": path})
    out = a._tool_create_music_in_garageband({"open_in_garageband": True, "replace_current_project": True})
    assert out["ok"] is True
    assert out["opened_in_garageband"] is True


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
