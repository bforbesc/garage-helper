from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path
from typing import Any

import mido
import numpy as np
import soundfile as sf

from config import settings
from tools import music_theory

GENRE_DEFAULTS = {
    "lofi": {"bpm": 78, "scale_type": "minor"},
    "pop": {"bpm": 110, "scale_type": "major"},
    "house": {"bpm": 124, "scale_type": "minor"},
    "hiphop": {"bpm": 92, "scale_type": "minor"},
    "jungle": {"bpm": 170, "scale_type": "minor"},
}

GENRE_ALIASES = {
    "boom bap": "hiphop",
    "boom-bap": "hiphop",
    "rnb": "hiphop",
    "edm": "house",
    "dnb": "jungle",
    "drum and bass": "jungle",
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

TRACK_ALIASES = {
    "melody": "melody",
    "lead": "melody",
    "topline": "melody",
    "bass": "bass",
    "bassline": "bass",
    "drums": "drums",
    "drum": "drums",
    "beat": "drums",
    "percussion": "drums",
    "chords": "chords",
    "pads": "chords",
    "harmony": "chords",
}

DEFAULT_TRACK_ORDER = ["melody", "bass", "drums", "chords"]


def _normalize_genre(genre: str) -> str:
    g = (genre or "pop").strip().lower()
    g = GENRE_ALIASES.get(g, g)
    return g if g in GENRE_DEFAULTS else "pop"


def _normalize_tracks(include_tracks: list[str] | None) -> list[str]:
    if not include_tracks:
        return ["melody", "bass", "drums"]
    tracks: list[str] = []
    for item in include_tracks:
        canonical = TRACK_ALIASES.get((item or "").strip().lower())
        if canonical and canonical not in tracks:
            tracks.append(canonical)
    return tracks or ["melody", "bass", "drums"]


def _note_to_semitone(note: str) -> int:
    return music_theory.NOTE_TO_SEMITONE[note.upper().replace("♭", "B").replace("♯", "#")]


def _semitone_to_note(semitone: int) -> str:
    return music_theory.SEMITONE_TO_NOTE[semitone % 12]


def _clamp_midi(note: int, low: int = 36, high: int = 96) -> int:
    return max(low, min(high, note))


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


def _melody_patterns_for_genre(genre: str) -> list[list[float]]:
    by_genre = {
        "house": [[0.5, 0.5, 1.0, 0.5, 0.5, 1.0], [1.0, 0.5, 0.5, 1.0, 1.0]],
        "hiphop": [[1.0, 0.5, 0.5, 1.0, 1.0], [0.5, 1.0, 0.5, 1.0, 1.0]],
        "lofi": [[1.0, 1.0, 0.5, 0.5, 1.0], [0.5, 1.0, 1.0, 0.5, 1.0]],
        "jungle": [[0.5, 0.5, 0.5, 0.5, 1.0, 1.0], [1.0, 0.5, 0.5, 0.5, 0.5, 1.0]],
        "pop": [[1.0, 0.5, 0.5, 1.0, 1.0], [0.5, 0.5, 1.0, 1.0, 1.0]],
    }
    return by_genre.get(genre, by_genre["pop"])


def _melody_from_scale(
    scale_midi: list[int],
    bars: int,
    progression: list[dict[str, Any]],
    genre: str,
    style_hint: str | None = None,
) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    style_text = (style_hint or "").strip().lower()
    rest_bias = 0.12 if "busy" in style_text else 0.24 if "sparse" in style_text else 0.18
    if "legato" in style_text:
        patterns = [[2.0, 2.0], [1.5, 1.0, 1.5]]
    else:
        patterns = _melody_patterns_for_genre(genre)

    for bar_idx in range(bars):
        bar_start = bar_idx * 4.0
        chord = progression[bar_idx % len(progression)]["midi_notes"]
        chord_tones = [_clamp_midi(n + 12, low=48, high=84) for n in chord]
        scale_pool = sorted({_clamp_midi(n, low=48, high=84) for n in scale_midi + [n + 12 for n in scale_midi]})
        pattern = random.choice(patterns)
        beat = bar_start
        for dur in pattern:
            if beat >= bar_start + 4.0:
                break
            duration = min(dur, bar_start + 4.0 - beat)
            if random.random() < rest_bias:
                beat += duration
                continue
            if random.random() < 0.65:
                midi_note = random.choice(chord_tones)
            else:
                midi_note = random.choice(scale_pool)
            # Keep lead line clearly dominant in GarageBand by using higher note velocities.
            velocity = random.randint(108, 124)
            notes.append(
                {
                    "start_beat": round(beat, 3),
                    "duration_beats": round(duration, 3),
                    "midi": midi_note,
                    "velocity": velocity,
                }
            )
            beat += duration
    return notes


def _bass_from_chords(chords: list[dict[str, Any]]) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for i, chord in enumerate(chords):
        root = min(chord["midi_notes"]) - 12
        notes.append({"start_beat": i * 4, "duration_beats": 4, "midi": max(24, root), "velocity": 72})
    return notes


def _chords_track_from_progression(chords: list[dict[str, Any]]) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for i, chord in enumerate(chords):
        start = i * 4.0
        for midi_note in chord["midi_notes"]:
            notes.append(
                {
                    "start_beat": start,
                    "duration_beats": 3.75,
                    "midi": _clamp_midi(int(midi_note), low=45, high=88),
                    "velocity": 64,
                }
            )
    return notes


def _drums_pattern(bars: int, genre: str, style_hint: str | None = None) -> list[dict[str, Any]]:
    # General MIDI: kick=36, snare=38, closed hat=42, open hat=46
    style_text = (style_hint or "").strip().lower()
    swing = 0.08 if "swing" in style_text else 0.0
    clap_note = 39 if genre in {"house", "pop"} else 38
    hat_note = 42

    def add_hit(out: list[dict[str, Any]], beat: float, midi_note: int, velocity: int) -> None:
        out.append({"start_beat": round(beat, 3), "duration_beats": 0.25, "midi": midi_note, "velocity": velocity})

    notes: list[dict[str, Any]] = []
    for bar in range(bars):
        base = bar * 4
        if genre == "house":
            for beat in [0.0, 1.0, 2.0, 3.0]:
                add_hit(notes, base + beat, 36, 88)
            for beat in [1.0, 3.0]:
                add_hit(notes, base + beat, clap_note, 82)
            for off in [0.5 + swing, 1.5 + swing, 2.5 + swing, 3.5 + swing]:
                add_hit(notes, base + off, 46, 60)
        elif genre == "jungle":
            first_half = bar < max(1, bars // 2)
            if first_half:
                # Beat A
                for beat in [0.0, 1.5, 2.0, 3.25]:
                    add_hit(notes, base + beat, 36, 84)
                for beat in [1.0, 3.0]:
                    add_hit(notes, base + beat, 38, 78)
                for off in [0.5 + swing, 1.0 + swing, 1.5 + swing, 2.0 + swing, 2.5 + swing, 3.0 + swing, 3.5 + swing]:
                    add_hit(notes, base + off, hat_note, 56)
            else:
                # Beat B (variation)
                for beat in [0.0, 0.75, 2.0, 2.75, 3.5]:
                    add_hit(notes, base + beat, 36, 82)
                for beat in [1.0, 2.5, 3.0]:
                    add_hit(notes, base + beat, 38, 80)
                for off in [0.25 + swing, 0.75 + swing, 1.25 + swing, 1.75 + swing, 2.25 + swing, 2.75 + swing, 3.25 + swing, 3.75]:
                    add_hit(notes, base + off, hat_note, 58)
        elif genre == "hiphop":
            for beat in [0.0, 1.75, 2.5]:
                add_hit(notes, base + beat, 36, 86)
            for beat in [1.0, 3.0]:
                add_hit(notes, base + beat, 38, 80)
            for off in [0.5 + swing, 1.5 + swing, 2.5 + swing, 3.5 + swing]:
                add_hit(notes, base + off, hat_note, 56)
        else:
            # pop/lofi fallback
            for beat in [0.0, 2.0]:
                add_hit(notes, base + beat, 36, 86)
            for beat in [1.0, 3.0]:
                add_hit(notes, base + beat, 38, 80)
            for off in [0.5 + swing, 1.5 + swing, 2.5 + swing, 3.5 + swing]:
                add_hit(notes, base + off, hat_note, 58)
    return notes


def _write_midi(tracks: dict[str, list[dict[str, Any]]], bpm: int, out_path: Path) -> Path:
    mid = mido.MidiFile(ticks_per_beat=480)
    tempo_track = mido.MidiTrack()
    tempo_track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    mid.tracks.append(tempo_track)

    for track_name, notes in tracks.items():
        t = mido.MidiTrack()
        t.append(mido.MetaMessage("track_name", name=track_name, time=0))
        channel = 9 if track_name == "drums" else 0
        events: list[tuple[int, mido.Message]] = []
        for n in notes:
            start = int(float(n["start_beat"]) * mid.ticks_per_beat)
            dur = int(float(n["duration_beats"]) * mid.ticks_per_beat)
            midi_note = int(n["midi"])
            velocity = int(n.get("velocity", 90))
            events.append((start, mido.Message("note_on", note=midi_note, velocity=velocity, time=0, channel=channel)))
            events.append((start + max(1, dur), mido.Message("note_off", note=midi_note, velocity=0, time=0, channel=channel)))

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


def _midi_to_freq(midi_note: int) -> float:
    return 440.0 * (2 ** ((midi_note - 69) / 12))


def _note_envelope(length: int, attack_ratio: float = 0.02, release_ratio: float = 0.18) -> np.ndarray:
    env = np.ones(max(1, length), dtype=np.float32)
    if length <= 2:
        return env

    attack_len = max(1, int(length * max(0.0, min(0.45, attack_ratio))))
    release_len = max(1, int(length * max(0.0, min(0.8, release_ratio))))
    if attack_len < length:
        env[:attack_len] = np.linspace(0.0, 1.0, attack_len, endpoint=False)
    if release_len < length:
        env[-release_len:] *= np.linspace(1.0, 0.0, release_len, endpoint=True)
    return env


def _synthesize_tonal_note(midi_note: int, duration_sec: float, sample_rate: int, track_name: str) -> np.ndarray:
    duration = max(0.04, duration_sec)
    sample_count = max(1, int(duration * sample_rate))
    t = np.linspace(0.0, duration, sample_count, endpoint=False)
    freq = _midi_to_freq(midi_note)
    sine = np.sin(2 * np.pi * freq * t)

    if track_name == "bass":
        sub = np.sin(2 * np.pi * (freq * 0.5) * t)
        wave = 0.82 * sine + 0.18 * sub
        env = _note_envelope(sample_count, attack_ratio=0.01, release_ratio=0.2)
    elif track_name == "chords":
        bright = np.sin(2 * np.pi * (freq * 2.0) * t)
        saw_hint = np.sign(sine)
        wave = 0.55 * sine + 0.25 * bright + 0.2 * saw_hint
        env = _note_envelope(sample_count, attack_ratio=0.03, release_ratio=0.25)
    else:
        saw_hint = np.sign(sine)
        harmonic = np.sin(2 * np.pi * (freq * 2.0) * t)
        wave = 0.5 * sine + 0.35 * saw_hint + 0.15 * harmonic
        env = _note_envelope(sample_count, attack_ratio=0.02, release_ratio=0.15)

    return (wave * env).astype(np.float32)


def _synthesize_drum_hit(midi_note: int, duration_sec: float, sample_rate: int) -> np.ndarray:
    duration = max(0.03, min(duration_sec, 0.45))
    sample_count = max(1, int(duration * sample_rate))
    t = np.linspace(0.0, duration, sample_count, endpoint=False)

    if midi_note == 36:  # kick
        sweep = np.linspace(115.0, 42.0, sample_count)
        phase = 2 * np.pi * np.cumsum(sweep) / sample_rate
        wave = np.sin(phase) * np.exp(-7.5 * t)
    elif midi_note in {38, 39}:  # snare / clap
        noise = np.random.uniform(-1.0, 1.0, sample_count)
        tone = np.sin(2 * np.pi * 185.0 * t)
        wave = (0.75 * noise + 0.25 * tone) * np.exp(-18.0 * t)
    elif midi_note in {42, 46}:  # hihat
        noise = np.random.uniform(-1.0, 1.0, sample_count)
        high = np.concatenate(([0.0], np.diff(noise)))
        wave = high * np.exp(-42.0 * t)
    else:
        noise = np.random.uniform(-1.0, 1.0, sample_count)
        wave = noise * np.exp(-24.0 * t)

    return wave.astype(np.float32)


def _render_song_audio(
    tracks: dict[str, list[dict[str, Any]]],
    bpm: int,
    bars: int,
    out_path: Path,
    sample_rate: int = 44100,
) -> Path:
    seconds_per_beat = 60.0 / max(1, int(bpm))
    max_note_end = float(bars) * 4.0
    for notes in tracks.values():
        for note in notes:
            start = float(note["start_beat"])
            duration = float(note["duration_beats"])
            max_note_end = max(max_note_end, start + duration)

    total_seconds = max_note_end * seconds_per_beat + 1.25
    total_samples = max(1, int(total_seconds * sample_rate))
    mix = np.zeros(total_samples, dtype=np.float32)

    for track_name, notes in tracks.items():
        for note in notes:
            midi_note = int(note["midi"])
            velocity = max(1, min(127, int(note.get("velocity", 90))))
            start_beat = float(note["start_beat"])
            duration_beat = float(note["duration_beats"])

            start_idx = max(0, int(start_beat * seconds_per_beat * sample_rate))
            duration_sec = max(0.035, duration_beat * seconds_per_beat)
            if track_name == "drums":
                signal = _synthesize_drum_hit(midi_note, duration_sec, sample_rate)
                gain = 0.28 * (velocity / 127.0)
            elif track_name == "melody":
                signal = _synthesize_tonal_note(midi_note, duration_sec, sample_rate, track_name)
                gain = 0.78 * (velocity / 127.0)
            else:
                signal = _synthesize_tonal_note(midi_note, duration_sec, sample_rate, track_name)
                gain = 0.32 * (velocity / 127.0)

            end_idx = min(total_samples, start_idx + len(signal))
            if end_idx <= start_idx:
                continue
            mix[start_idx:end_idx] += signal[: end_idx - start_idx] * gain

    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > 0:
        mix = mix / peak * 0.92

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), mix, sample_rate, subtype="PCM_16")
    return out_path


def compose_music_idea(
    genre: str = "pop",
    key: str = "C",
    scale_type: str | None = None,
    bars: int = 4,
    bpm: int | None = None,
    seed: int | None = None,
    include_tracks: list[str] | None = None,
    style_hint: str | None = None,
) -> dict[str, Any]:
    if seed is not None:
        random.seed(int(seed))

    normalized_genre = _normalize_genre(genre)
    defaults = GENRE_DEFAULTS[normalized_genre]
    resolved_scale = (scale_type or defaults["scale_type"]).lower()
    resolved_bpm = int(bpm or defaults["bpm"])
    resolved_bars = max(1, min(int(bars), 16))
    selected_tracks = _normalize_tracks(include_tracks)

    scale = music_theory.get_scale_notes(root=key, scale_type=resolved_scale, octave=5)
    progression = _build_progression(key=key, scale_type=resolved_scale, bars=resolved_bars, genre=normalized_genre)
    melody_notes = _melody_from_scale(
        scale["midi_notes"],
        bars=resolved_bars,
        progression=progression,
        genre=normalized_genre,
        style_hint=style_hint,
    )
    bass_notes = _bass_from_chords(progression)
    drum_notes = _drums_pattern(resolved_bars, genre=normalized_genre, style_hint=style_hint)
    chord_notes = _chords_track_from_progression(progression)

    available_tracks = {
        "melody": melody_notes,
        "bass": bass_notes,
        "drums": drum_notes,
        "chords": chord_notes,
    }
    tracks = {track: available_tracks[track] for track in DEFAULT_TRACK_ORDER if track in selected_tracks}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"idea_{normalized_genre}_{timestamp}"
    midi_path = _write_midi(tracks=tracks, bpm=resolved_bpm, out_path=Path(settings.downloads_dir) / f"{base_name}.mid")
    audio_path = _render_song_audio(
        tracks=tracks,
        bpm=resolved_bpm,
        bars=resolved_bars,
        out_path=Path(settings.downloads_dir) / f"{base_name}.wav",
    )

    return {
        "ok": True,
        "genre": normalized_genre,
        "key": key.upper(),
        "scale_type": resolved_scale,
        "bpm": resolved_bpm,
        "bars": resolved_bars,
        "style_hint": (style_hint or "").strip(),
        "included_tracks": list(tracks.keys()),
        "progression": progression,
        "tracks": tracks,
        "midi_file_path": str(midi_path.resolve()),
        "audio_file_path": str(audio_path.resolve()),
    }
