from tools import music_theory


def test_get_midi_notes_for_chord_cm7():
    result = music_theory.get_midi_notes_for_chord("Cm7", octave=4)
    assert result["midi_notes"] == [60, 63, 67, 70]


def test_get_scale_notes_c_major():
    result = music_theory.get_scale_notes("C", "major", octave=4)
    assert result["note_names"] == ["C", "D", "E", "F", "G", "A", "B"]
    assert result["midi_notes"] == [60, 62, 64, 65, 67, 69, 71]


def test_transpose_chord_up_two():
    result = music_theory.transpose_chord("Cm7", semitones=2, octave=4)
    assert result["normalized_chord"] == "Dmin7"
    assert result["midi_notes"] == [62, 65, 69, 72]

