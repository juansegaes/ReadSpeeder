from darsvp_scorer.pauses import is_abbreviation, pause_for
from darsvp_scorer.weights import Config

CFG = Config()


def test_chapter_and_paragraph_end():
    assert pause_for("word.", True, True, "en", CFG) == CFG.pause_chapter_end
    assert pause_for("word.", True, False, "en", CFG) == CFG.pause_paragraph_end


def test_sentence_end():
    assert pause_for("end.", False, False, "en", CFG) == CFG.pause_sentence_end
    assert pause_for("really?!", False, False, "en", CFG) == CFG.pause_sentence_end
    assert pause_for("wait...", False, False, "en", CFG) == CFG.pause_sentence_end
    assert pause_for("yes…", False, False, "en", CFG) == CFG.pause_sentence_end


def test_abbreviation():
    assert pause_for("Dr.", False, False, "en", CFG) == CFG.pause_abbreviation
    assert pause_for("J.", False, False, "en", CFG) == CFG.pause_abbreviation
    assert pause_for("e.g.", False, False, "en", CFG) == CFG.pause_abbreviation
    assert pause_for("Sra.", False, False, "es", CFG) == CFG.pause_abbreviation
    assert pause_for("M.", False, False, "fr", CFG) == CFG.pause_abbreviation


def test_other_punctuation():
    assert pause_for("word;", False, False, "en", CFG) == CFG.pause_semicolon_colon
    assert pause_for("word:", False, False, "en", CFG) == CFG.pause_semicolon_colon
    assert pause_for("word,", False, False, "en", CFG) == CFG.pause_comma
    assert pause_for("word—", False, False, "en", CFG) == CFG.pause_dash
    assert pause_for("—", False, False, "en", CFG) == CFG.pause_dash
    assert pause_for("(word)", False, False, "en", CFG) == CFG.pause_close_paren
    assert pause_for("word", False, False, "en", CFG) == 0.0


def test_closers_are_ignored_for_the_last_character():
    assert pause_for("Hello,”", False, False, "en", CFG) == CFG.pause_comma


def test_is_abbreviation():
    assert is_abbreviation("Dr.", "en")
    assert is_abbreviation("U.S.", "en")
    assert not is_abbreviation("word.", "en")
    assert is_abbreviation("z.B.", "de")
