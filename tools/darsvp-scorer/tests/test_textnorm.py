from darsvp_scorer.textnorm import clean_text, letter_count, split_paragraph, word_core


def test_nbsp_is_a_word_separator():
    assert split_paragraph("one\u00a0two") == ["one", "two"]


def test_soft_hyphen_is_removed_inside_a_word():
    assert split_paragraph("im\u00adpor\u00adtant") == ["important"]


def test_zero_width_space_is_removed():
    assert split_paragraph("one\u200btwo") == ["onetwo"]


def test_tabs_and_newlines_collapse():
    assert clean_text("a\tb\nc\r\nd") == "a b c d"


def test_inner_tabs_are_joined_only_when_requested():
    assert split_paragraph("press\ted h\tard") == ["press", "ed", "h", "ard"]
    assert split_paragraph("press\ted h\tard", join_inner_tabs=True) == ["pressed", "hard"]
    assert split_paragraph("Alice's\t elbow", join_inner_tabs=True) == ["Alice's", "elbow"]
    assert split_paragraph("the\t roo\tts", join_inner_tabs=True) == ["the", "roots"]


def test_word_core_examples():
    assert word_core("“Hello,”") == "Hello"
    assert word_core("state-of-the-art.") == "state-of-the-art"
    assert word_core("—") == ""


def test_letter_count():
    assert letter_count("state-of-the-art") == 13
    assert letter_count("") == 0


def test_split_paragraph_has_only_plain_spaces():
    words = split_paragraph("one\u00a0two\tthree\nfour")
    joined = " ".join(words)
    assert all(ch == " " or not ch.isspace() for ch in joined)
