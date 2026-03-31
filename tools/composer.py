from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path
from typing import Any

import mido

from config import settings
from tools import music_theory

GENRE_DEFAULTS = {
    "lofi": {"bpm": 78, "scale_type": "minor"},
    "pop": {"bpm": 110, "scale_type": "major"},
    "house": {"bpm": 124, "scale_type": "minor"},
    "hiphop": {"bpm": 92, "scale_type": "minor"},
    "jungle": {"bpm": 170, "scale_type": "minor"},
}

GENRE_PROGRESSIONS = {
    "lofi": ["i-VII-VI-VII", "i-iv-VII-III", "ii-V-I-vi"],
    "pop": ["I-V-vi-IV", "vi-IV-I-V", "I-vi-IV-V"],
    "house": ["i-VI-III-VII", "i-iv-VI-V", "i-VII-VI-VII"],
    "hiphop": ["i-VII-VI-VII", "i-v-iv-v", "vi-VII-i-i"],
    "jungle": ["i-VII-VI-VII", "i-iv-VII-III", "i-VI-III-VII"],
}

ROMAN_MAJOR = {
    "I": 0,
    "II": 2,
    "III": 4,
    "IV": 5,
    "V": 7,
    "VI": 9,
    "VII": 11,
}
ROMAN_MINOR = {
    "I": 0,
    "II": 2,
    "III": 3,
    "IV": 5,
    "V": 7,
    "VI": 8,
    "VII": 10,
}

CHORD_QUALITY_FROM_ROMAN = {
    "I": "maj",
    "II": "min",
    "III": "min",
    "IV": "maj",
    "V": "maj",
    "VI": "min",
    "VII": "dim",
}
CHORD_QUALITY_FROM_ROMAN_MINOR = {
    "I": "min",
    "II": "dim",
    "III": "maj",
    "IV": "min",
    "V": "min",
    "VI": "maj",
    "VII": "maj",
}


def _normalize_genre(genre: str) -> str:
    g = (genre or "pop").strip().lower()
    return g if g in GENRE_DEFAULTS else "pop"


def _note_to_semitone(note: str) -> int:
    return music_theory.NOTE_TO_SEMITONE[note.upper().replace("♭", "B").replace("♯", "#")]


def _semitone_to_note(semitone: int) -> str:
    return music_theory.SEMITONE_TO_NOTE[semitone % 12]


def _degree_to_chord(key: str, scale_type: str, degree: str, octave: int = 4) -> dict[str, Any]:
    key_semitone = _note_to_semitone(key)
    degree_clean = degree.strip().upper()
    if scale_type == "minor":
        offset = ROMAN_MINOR.get(degree_clean, 0)
        quality = CHORD_QUALITY_FROM_ROMAN_MINOR.get(degree_clean, "min")
    else:
        offset = ROMAN_MAJOR.get(degree_clean, 0)
        quality = CHORD_QUALITY_FROM_ROMAN.get(degree_clean, "maj")

    root_note = _semitone_to_note(key_semitone + offset)
    chord_symbol = root_note if quality == "maj" else (f"{root_note}m" if quality == "min" else f"{root_note}{quality}")
    chord = music_theory.get_midi_notes_for_chord(chord_symbol, octave=octave)
    return {
        "degree": degree_clean,
        "chord_symbol": chord_symbol,
        "midi_notes": chord["midi_notes"],
        "note_names": chord["note_names"],
    }


def _build_progression(key: str, scale_type: str, bars: int, genre: str) -> list[dict[str, Any]]:
    random_progressions = GENRE_PROGRESSIONS[_normalize_genre(genre)]
    prog = random.choice(random_progressions)
    degrees = [d for d in prog.replace("i", "I").split("-") if d.strip()]
    chords = []
    for i in range(bars):
        degree = degrees[i % len(degrees)]
        chords.append(_degree_to_chord(key=key, scale_type=scale_type, degree=degree, octave=4))
    return chords


def _melody_from_scale(scale_midi: list[int], bars: int) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    beat = 0.0
    total_beats = bars * 4
    while beat < total_beats:
        step = random.choice([0.5, 0.5, 1.0, 1.0])
        if beat + step > total_beats:
            step = total_beats - beat
        midi_note = random.choice(scale_midi)
        velocity = random.randint(70, 105)
        notes.append({"start_beat": round(beat, 3), "duration_beats": round(step, 3), "midi": midi_note, "velocity": velocity})
        beat += step
    return notes


def _bass_from_chords(chords: list[dict[str, Any]]) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for i, chord in enumerate(chords):
        root = min(chord["midi_notes"]) - 12
        notes.append({"start_beat": i * 4, "duration_beats": 4, "midi": max(24, root), "velocity": 92})
    return notes


def _drums_pattern(bars: int) -> list[dict[str, Any]]:
    # General MIDI: kick=36, snare=38, closed hat=42
    notes: list[dict[str, Any]] = []
    for bar in range(bars):
        base = bar * 4
        notes.extend(
            [
                {"start_beat": base + 0.0, "duration_beats": 0.25, "midi": 36, "velocity": 110},
                {"start_beat": base + 1.0, "duration_beats": 0.25, "midi": 42, "velocity": 78},
                {"start_beat": base + 2.0, "duration_beats": 0.25, "midi": 38, "velocity": 108},
                {"start_beat": base + 3.0, "duration_beats": 0.25, "midi": 42, "velocity": 82},
            ]
        )
        # Off-beat hats
        for off in [0.5, 1.5, 2.5, 3.5]:
            notes.append({"start_beat": base + off, "duration_beats": 0.25, "midi": 42, "velocity": 70})
    return notes


def _write_midi(tracks: dict[str, list[dict[str, Any]]], bpm: int, out_path: Path) -> Path:
    mid = mido.MidiFile(ticks_per_beat=480)
    tempo_track = mido.MidiTrack()
    tempo_track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    mid.tracks.append(tempo_track)

    for track_name, notes in tracks.items():
        t = mido.MidiTrack()
        t.append(mido.MetaMessage("track_name", name=track_name, time=0))
        events: list[tuple[int, mido.Message]] = []
        for n in notes:
            start = int(float(n["start_beat"]) * mid.ticks_per_beat)
            dur = int(float(n["duration_beats"]) * mid.ticks_per_beat)
            midi_note = int(n["midi"])
            velocity = int(n.get("velocity", 90))
            events.append((start, mido.Message("note_on", note=midi_note, velocity=velocity, time=0)))
            events.append((start + max(1, dur), mido.Message("note_off", note=midi_note, velocity=0, time=0)))

        events.sort(key=lambda item: item[0])
        last_tick = 0
        for abs_tick, msg in events:
            msg.time = max(0, abs_tick - last_tick)
            last_tick = abs_tick
            t.append(msg)
        mid.tracks.append(t)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    mid.save(str(out_path))
    return out_path


def compose_music_idea(
    genre: str = "pop",
    key: str = "C",
    scale_type: str | None = None,
    bars: int = 4,
    bpm: int | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    if seed is not None:
        random.seed(int(seed))

    normalized_genre = _normalize_genre(genre)
    defaults = GENRE_DEFAULTS[normalized_genre]
    resolved_scale = (scale_type or defaults["scale_type"]).lower()
    resolved_bpm = int(bpm or defaults["bpm"])
    resolved_bars = max(1, min(int(bars), 16))

    scale = music_theory.get_scale_notes(root=key, scale_type=resolved_scale, octave=5)
    progression = _build_progression(key=key, scale_type=resolved_scale, bars=resolved_bars, genre=normalized_genre)
    melody_notes = _melody_from_scale(scale["midi_notes"], resolved_bars)
    bass_notes = _bass_from_chords(progression)
    drum_notes = _drums_pattern(resolved_bars)

    tracks = {
        "melody": melody_notes,
        "bass": bass_notes,
        "drums": drum_notes,
    }

    filename = f"idea_{normalized_genre}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mid"
    midi_path = _write_midi(tracks=tracks, bpm=resolved_bpm, out_path=Path(settings.downloads_dir) / filename)

    return {
        "ok": True,
        "genre": normalized_genre,
        "key": key.upper(),
        "scale_type": resolved_scale,
        "bpm": resolved_bpm,
        "bars": resolved_bars,
        "progression": progression,
        "tracks": tracks,
        "midi_file_path": str(midi_path.resolve()),
    }

