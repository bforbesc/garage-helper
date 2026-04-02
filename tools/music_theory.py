from __future__ import annotations

from dataclasses import dataclass

NOTE_TO_SEMITONE = {
    "C": 0,
    "C#": 1,
    "DB": 1,
    "D": 2,
    "D#": 3,
    "EB": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "GB": 6,
    "G": 7,
    "G#": 8,
    "AB": 8,
    "A": 9,
    "A#": 10,
    "BB": 10,
    "B": 11,
}

SEMITONE_TO_NOTE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

SCALE_PATTERNS = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "pentatonic_major": [0, 2, 4, 7, 9],
    "pentatonic_minor": [0, 3, 5, 7, 10],
}

CHORD_QUALITIES = {
    "maj": [0, 4, 7],
    "min": [0, 3, 7],
    "dim": [0, 3, 6],
    "aug": [0, 4, 8],
    "7": [0, 4, 7, 10],
    "maj7": [0, 4, 7, 11],
    "min7": [0, 3, 7, 10],
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
    "9": [0, 4, 7, 10, 14],
    "min9": [0, 3, 7, 10, 14],
    "11": [0, 4, 7, 10, 14, 17],
    "13": [0, 4, 7, 10, 14, 21],
    "add9": [0, 4, 7, 14],
    "6": [0, 4, 7, 9],
    "min6": [0, 3, 7, 9],
}

GENRE_ARRANGEMENTS = {
    "house": ["intro(8)", "build(16)", "drop(16)", "breakdown(8)", "drop(16)", "outro(8)"],
    "lofi": ["intro(4)", "verse(16)", "hook(16)", "verse(16)", "outro(8)"],
    "pop": ["intro(4)", "verse(16)", "pre(8)", "chorus(16)", "verse(16)", "chorus(16)", "bridge(8)", "chorus(16)"],
    "hiphop": ["intro(4)", "verse(16)", "hook(8)", "verse(16)", "hook(8)", "outro(4)"],
}

GENRE_TEMPO = {
    "house": {"bpm": 124, "time_signature": "4/4"},
    "lofi": {"bpm": 78, "time_signature": "4/4"},
    "pop": {"bpm": 110, "time_signature": "4/4"},
    "hiphop": {"bpm": 92, "time_signature": "4/4"},
    "trap": {"bpm": 140, "time_signature": "4/4"},
}


@dataclass
class ParsedChord:
    root: str
    quality: str


def _normalize_note(note: str) -> str:
    return note.strip().upper().replace("♭", "B").replace("♯", "#")


def _note_to_midi(note_name: str, octave: int) -> int:
    semitone = NOTE_TO_SEMITONE[_normalize_note(note_name)]
    return max(0, min(127, (octave + 1) * 12 + semitone))


def _parse_chord(chord: str) -> ParsedChord:
    chord = chord.strip()
    if len(chord) < 1:
        raise ValueError("Chord cannot be empty")
    if len(chord) >= 2 and chord[1] in ["#", "b", "♯", "♭"]:
        root = chord[:2]
        quality_raw = chord[2:]
    else:
        root = chord[:1]
        quality_raw = chord[1:]
    quality_raw = quality_raw.strip().lower()
    mapping = {
        "": "maj",
        "m": "min",
        "m7": "min7",
        "maj": "maj",
        "maj7": "maj7",
        "min7": "min7",
        "min": "min",
        "major": "maj",
        "minor": "min",
        "9": "9",
        "min9": "min9",
        "m9": "min9",
        "11": "11",
        "13": "13",
        "add9": "add9",
        "6": "6",
        "m6": "min6",
        "min6": "min6",
    }
    quality = mapping.get(quality_raw, quality_raw or "maj")
    if quality not in CHORD_QUALITIES:
        raise ValueError(f"Unsupported chord quality: {quality}")
    return ParsedChord(root=_normalize_note(root), quality=quality)


def get_midi_notes_for_chord(chord: str, octave: int = 4) -> dict:
    parsed = _parse_chord(chord)
    root_semitone = NOTE_TO_SEMITONE[parsed.root]
    intervals = CHORD_QUALITIES[parsed.quality]
    midi_notes = [max(0, min(127, (octave + 1) * 12 + root_semitone + i)) for i in intervals]
    note_names = [SEMITONE_TO_NOTE[n % 12] for n in midi_notes]
    return {"chord": chord, "normalized_chord": f"{parsed.root}{parsed.quality}", "midi_notes": midi_notes, "note_names": note_names}


def get_scale_notes(root: str, scale_type: str = "major", octave: int = 4) -> dict:
    scale = scale_type.strip().lower()
    if scale not in SCALE_PATTERNS:
        raise ValueError(f"Unsupported scale type: {scale_type}")
    root = _normalize_note(root)
    root_semitone = NOTE_TO_SEMITONE[root]
    semitones = [(root_semitone + i) % 12 for i in SCALE_PATTERNS[scale]]
    note_names = [SEMITONE_TO_NOTE[s] for s in semitones]
    midi_notes = [_note_to_midi(n, octave) for n in note_names]
    return {
        "root": root,
        "scale_type": scale,
        "note_names": note_names,
        "midi_notes": midi_notes,
    }


ROMAN_MAP_MAJOR = {
    "I": ("maj", 0),
    "ii": ("min", 2),
    "iii": ("min", 4),
    "IV": ("maj", 5),
    "V": ("maj", 7),
    "vi": ("min", 9),
    "vii": ("dim", 11),
}

ROMAN_MAP_MINOR = {
    "i": ("min", 0),
    "ii": ("dim", 2),
    "III": ("maj", 3),
    "iv": ("min", 5),
    "v": ("min", 7),
    "VI": ("maj", 8),
    "VII": ("maj", 10),
}


def get_chord_progression(key: str = "C", progression: str = "I-V-vi-IV", octave: int = 4, mode: str = "major") -> dict:
    roman_map = ROMAN_MAP_MINOR if mode.strip().lower() == "minor" else ROMAN_MAP_MAJOR
    root = _normalize_note(key)
    root_semitone = NOTE_TO_SEMITONE[root]
    steps = [step.strip() for step in progression.split("-") if step.strip()]
    chords = []
    for step in steps:
        quality, offset = roman_map.get(step, ("maj", 0))
        chord_root = SEMITONE_TO_NOTE[(root_semitone + offset) % 12]
        chord_name = f"{chord_root}{'m' if quality == 'min' else ''}"
        chord_data = get_midi_notes_for_chord(f"{chord_root}{quality if quality not in ['maj', 'min'] else ('min' if quality == 'min' else '')}", octave)
        chords.append(
            {
                "roman": step,
                "name": chord_name,
                "quality": quality,
                "midi_notes": chord_data["midi_notes"],
                "note_names": chord_data["note_names"],
            }
        )
    return {"key": root, "progression": progression, "chords": chords}


def suggest_arrangement(genre: str = "pop") -> dict:
    normalized = genre.strip().lower()
    sections = GENRE_ARRANGEMENTS.get(normalized, GENRE_ARRANGEMENTS["pop"])
    return {"genre": normalized, "sections": sections}


def get_tempo_suggestion(genre: str = "pop") -> dict:
    normalized = genre.strip().lower()
    return {"genre": normalized, **GENRE_TEMPO.get(normalized, GENRE_TEMPO["pop"])}


def invert_chord(midi_notes: list[int], inversion: int = 1) -> dict:
    """Rotate the lowest N notes up an octave to create chord inversions."""
    if not midi_notes:
        raise ValueError("midi_notes cannot be empty")
    notes = sorted(midi_notes)
    inversion = max(0, min(inversion, len(notes) - 1))
    for _ in range(inversion):
        notes.append(notes.pop(0) + 12)
    return {"midi_notes": notes, "inversion": inversion}


def transpose_chord(chord: str, semitones: int, octave: int = 4) -> dict:
    parsed = _parse_chord(chord)
    root_semitone = NOTE_TO_SEMITONE[parsed.root]
    transposed_root = SEMITONE_TO_NOTE[(root_semitone + semitones) % 12]
    result = get_midi_notes_for_chord(f"{transposed_root}{parsed.quality if parsed.quality != 'maj' else ''}", octave)
    result["transposed_by"] = semitones
    return result
