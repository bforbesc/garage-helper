from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

from config import settings


def midi_to_freq(midi_note: int) -> float:
    return 440.0 * (2 ** ((midi_note - 69) / 12))


def preview_midi_notes(midi_notes: list[int], duration_sec: float = 1.2, sample_rate: int = 44100) -> dict:
    if not midi_notes:
        raise ValueError("midi_notes cannot be empty")

    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    signal = np.zeros_like(t)
    for note in midi_notes:
        freq = midi_to_freq(int(note))
        signal += 0.25 * np.sin(2 * math.pi * freq * t)
    signal = np.clip(signal, -1.0, 1.0)
    envelope = np.linspace(1.0, 0.2, signal.shape[0])
    signal *= envelope
    sd.play(signal, sample_rate)
    sd.wait()
    return {"ok": True, "midi_notes": midi_notes, "duration_sec": duration_sec}


def play_audio_file(path: str) -> dict:
    data, sample_rate = sf.read(path, dtype="float32", always_2d=False)
    sd.play(data, sample_rate)
    sd.wait()
    return {"ok": True, "path": str(Path(path).resolve())}


def speak(text: str) -> dict:
    if not text.strip():
        return {"ok": True, "skipped": True}
    proc = subprocess.run(
        ["say", "-v", settings.say_voice, text[:500]],
        capture_output=True,
        text=True,
    )
    return {"ok": proc.returncode == 0, "stderr": proc.stderr.strip()}
