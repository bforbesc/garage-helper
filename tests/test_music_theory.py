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


def test_get_midi_notes_for_chord_c9():
    result = music_theory.get_midi_notes_for_chord("C9", octave=4)
    assert result["midi_notes"] == [60, 64, 67, 70, 74]


def test_get_midi_notes_for_chord_am6():
    result = music_theory.get_midi_notes_for_chord("Am6", octave=4)
    assert result["midi_notes"] == [69, 72, 76, 78]


def test_get_chord_progression_minor():
    result = music_theory.get_chord_progression("A", "i-iv-VII-III", octave=4, mode="minor")
    assert len(result["chords"]) == 4
    assert result["chords"][0]["quality"] == "min"  # i
    assert result["chords"][1]["quality"] == "min"  # iv
    assert result["chords"][2]["quality"] == "maj"  # VII
    assert result["chords"][3]["quality"] == "maj"  # III


def test_invert_chord_first_inversion():
    result = music_theory.invert_chord([60, 64, 67], inversion=1)
    assert result["midi_notes"] == [64, 67, 72]
    assert result["inversion"] == 1


def test_invert_chord_second_inversion():
    result = music_theory.invert_chord([60, 64, 67], inversion=2)
    assert result["midi_notes"] == [67, 72, 76]
    assert result["inversion"] == 2
