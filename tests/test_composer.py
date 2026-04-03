from pathlib import Path
from types import SimpleNamespace

from tools import composer
from tools import music_theory


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
    audio_path = Path(result["audio_file_path"])
    assert audio_path.exists()
    assert audio_path.suffix == ".wav"


def test_compose_melody_default_in_key(tmp_path, monkeypatch):
    monkeypatch.setattr(composer, "settings", SimpleNamespace(downloads_dir=str(tmp_path)))
    result = composer.compose_music_idea(
        genre="hiphop",
        key="D#",
        scale_type="minor",
        bars=8,
        seed=42,
        include_tracks=["melody"],
        allow_out_of_key_notes=False,
    )
    melody_notes = [n["midi"] for n in result["tracks"]["melody"]]
    pcs = {n % 12 for n in music_theory.get_scale_notes("D#", "minor", octave=4)["midi_notes"]}
    assert all((note % 12) in pcs for note in melody_notes)


def test_compose_melody_can_include_out_of_key_when_requested(tmp_path, monkeypatch):
    monkeypatch.setattr(composer, "settings", SimpleNamespace(downloads_dir=str(tmp_path)))
    result = composer.compose_music_idea(
        genre="hiphop",
        key="D#",
        scale_type="minor",
        bars=8,
        seed=1,
        include_tracks=["melody"],
        allow_out_of_key_notes=True,
    )
    melody_notes = [n["midi"] for n in result["tracks"]["melody"]]
    pcs = {n % 12 for n in music_theory.get_scale_notes("D#", "minor", octave=4)["midi_notes"]}
    assert any((note % 12) not in pcs for note in melody_notes)
