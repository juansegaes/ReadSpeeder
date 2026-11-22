from darsvp_scorer.textnorm import clean_text, letter_count, split_paragraph, word_core


def test_nbsp_is_a_word_separator():
    assert split_paragraph("one\u00a0two") == ["one", "two"]


def test_soft_hyphen_is_removed_inside_a_word():
    assert split_paragraph("im\u00adpor\u00adtant") == ["important"]


def test_zero_width_space_is_removed():
    assert split_paragraph("one\u200btwo") == ["onetwo"]


def test_tabs_and_newlines_collapse():
    assert clean_text("a\tb\nc\r\nd") == "a b c d"


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
