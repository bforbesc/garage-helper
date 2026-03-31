from pathlib import Path
from types import SimpleNamespace

from tools import composer


def test_compose_music_idea_generates_midi(tmp_path, monkeypatch):
    monkeypatch.setattr(composer, "settings", SimpleNamespace(downloads_dir=str(tmp_path)))
    result = composer.compose_music_idea(genre="pop", key="C", bars=2, seed=42)
    assert result["ok"] is True
    assert result["bars"] == 2
    assert "melody" in result["tracks"]
    assert "bass" in result["tracks"]
    assert "drums" in result["tracks"]
    midi_path = Path(result["midi_file_path"])
    assert midi_path.exists()
    assert midi_path.suffix == ".mid"
