from __future__ import annotations

import agent as agent_module


def test_create_music_in_garageband_tool(monkeypatch):
    a = agent_module.GarageBandAgent()

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
