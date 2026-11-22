from darsvp_scorer.wordrepair import repair_merged_words, repair_word


def test_merged_words_are_split():
    assert repair_word("Thencame") == ["Then", "came"]
    assert repair_word("sayto") == ["say", "to"]
    assert repair_word("mypoor") == ["my", "poor"]
    assert repair_word("Ieat") == ["I", "eat"]
    assert repair_word("thinkingI") == ["thinking", "I"]
    assert repair_word("abright") == ["a", "bright"]


def test_punctuation_stays_with_the_second_word():
    assert repair_word("armsfolded,") == ["arms", "folded,"]
    assert repair_word("“Thencame") == ["“Then", "came"]


def test_known_words_and_rare_compounds_are_left_alone():
    assert repair_word("another") == ["another"]
    assert repair_word("jurymen") == ["jurymen"]
    assert repair_word("whatever") == ["whatever"]


def test_repair_merged_words_keeps_order():
    words = ["It", "was", "Thencame", "a", "bright", "day."]
    assert repair_merged_words(words) == [
        "It",
        "was",
        "Then",
        "came",
        "a",
        "bright",
        "day.",
    ]
