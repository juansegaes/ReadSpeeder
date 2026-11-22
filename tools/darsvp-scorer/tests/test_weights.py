import numpy as np

from darsvp_scorer.output import WordStream
from darsvp_scorer.weights import Config, combine


def make_stream(words, paragraph_start=None, paragraph_end=None, chapter_end=None):
    n = len(words)
    if paragraph_start is None:
        paragraph_start = [False] * n
    if paragraph_end is None:
        paragraph_end = [False] * n
    if chapter_end is None:
        chapter_end = [False] * n
    return WordStream(
        words=list(words),
        paragraph_start=list(paragraph_start),
        paragraph_end=list(paragraph_end),
        chapter_end=list(chapter_end),
        chapters=[("Chapter", 0)] if words else [],
        text=" ".join(words),
    )


def test_identical_words_get_100():
    stream = make_stream(["same", "same", "same"])
    weights, debug = combine(stream, np.zeros(3), "en", Config(), zipf=np.full(3, 4.5))
    assert list(weights) == [100, 100, 100]
    assert np.allclose(debug["content"], [1.0, 1.0, 1.0])


def test_hard_word_gets_more_than_the():
    stream = make_stream(["the", "extraordinary"])
    weights, _ = combine(
        stream,
        np.array([0.0, 10.0]),
        "en",
        Config(),
        zipf=np.array([7.5, 1.5]),
    )
    assert weights[1] > weights[0]


def test_output_is_always_in_range():
    rng = np.random.default_rng(7)
    words = [f"word{i}" for i in range(500)]
    stream = make_stream(words)
    weights, _ = combine(
        stream,
        rng.normal(5, 3, size=len(words)),
        "en",
        Config(),
        zipf=rng.uniform(1, 7, size=len(words)),
    )
    assert weights.min() >= 40
    assert weights.max() <= 600


def test_pause_differences():
    mid = make_stream(["end."])
    end = make_stream(["end."], paragraph_end=[True])
    mid_weight, _ = combine(mid, np.zeros(1), "en", Config(), zipf=np.array([4.5]))
    end_weight, _ = combine(end, np.zeros(1), "en", Config(), zipf=np.array([4.5]))
    assert mid_weight[0] == 250
    assert end_weight[0] == 300

    abbreviation, _ = combine(
        make_stream(["Dr."]), np.zeros(1), "en", Config(), zipf=np.array([4.5])
    )
    assert abbreviation[0] == 130

    quoted, _ = combine(
        make_stream(["Hello,”"]), np.zeros(1), "en", Config(), zipf=np.array([4.5])
    )
    assert quoted[0] == 175


def test_normalized_content_mean_is_one():
    rng = np.random.default_rng(11)
    words = [f"word{i}" for i in range(1000)]
    stream = make_stream(words)
    _, debug = combine(
        stream,
        rng.normal(5, 3, size=len(words)),
        "en",
        Config(),
        zipf=rng.uniform(1, 7, size=len(words)),
    )
    assert abs(float(np.mean(debug["content"])) - 1.0) < 0.05


def test_spillover_skips_first_word_of_paragraph():
    words = ["alpha", "beta", "gamma", "delta", "epsilon"]
    surprisal = np.array([10.0, 0.0, 0.0, 0.0, 0.0])
    zipf = np.full(len(words), 4.5)
    cfg = Config(normalize="total")

    without_break = make_stream(words, paragraph_start=[True, False, False, False, False])
    with_break = make_stream(words, paragraph_start=[True, True, False, False, False])

    _, without_debug = combine(without_break, surprisal, "en", cfg, zipf=zipf)
    _, with_debug = combine(with_break, surprisal, "en", cfg, zipf=zipf)
    assert with_debug["content"][1] < without_debug["content"][1]
