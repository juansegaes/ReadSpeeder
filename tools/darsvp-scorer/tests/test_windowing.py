import numpy as np

from darsvp_scorer.output import WordStream
from darsvp_scorer.surprisal.base import (
    aggregate_bits,
    tokenize_stream,
    windowed_logprobs,
)


def make_stream(words, paragraph_start=None):
    n = len(words)
    if paragraph_start is None:
        paragraph_start = [False] * n
    return WordStream(
        words=list(words),
        paragraph_start=list(paragraph_start),
        paragraph_end=[False] * n,
        chapter_end=[False] * n,
        chapters=[("Chapter", 0)] if words else [],
        text=" ".join(words),
    )


class BigramModel:
    def __init__(self, vocab=50, seed=3):
        rng = np.random.default_rng(seed)
        self.matrix = rng.normal(size=(vocab, vocab))
        self.vocab = vocab

    def __call__(self, window):
        logits = np.empty((len(window), self.vocab))
        for row, token in enumerate(window):
            logits[row] = self.matrix[token % self.vocab]
        return logits


def test_windowing_matches_single_pass():
    model = BigramModel()
    tokens = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
    windowed = windowed_logprobs(tokens, model, bos=0, n_ctx=16, overlap=4)
    single = windowed_logprobs(tokens, model, bos=0, n_ctx=10_000, overlap=4)
    assert np.allclose(windowed, single)


def test_every_token_is_scored_once():
    model = BigramModel()
    for length in (1, 15, 16, 17, 100):
        tokens = [(i % 40) + 1 for i in range(length)]
        values = windowed_logprobs(tokens, model, bos=0, n_ctx=16, overlap=4)
        assert not np.isnan(values).any()
        assert values.shape == (length,)


def test_token_word_map_for_words():
    stream = make_stream(["“Hello,”", "she", "said."], paragraph_start=[True, False, False])
    tok = tokenize_stream(stream, lambda text: [ord(character) for character in text])
    assert tok.token_word[0] == -1
    assert tok.token_word[1:6] == [0, 0, 0, 0, 0]
    assert tok.token_word[6:8] == [-1, -1]
    assert tok.token_word[8:12] == [1, 1, 1, 1]
    assert tok.token_word[12:17] == [2, 2, 2, 2, 2]
    assert tok.token_word[17] == -1


def test_token_word_map_across_paragraphs():
    stream = make_stream(["one", "two"], paragraph_start=[True, True])
    tok = tokenize_stream(stream, lambda text: [ord(character) for character in text])
    assert tok.token_word == [0, 0, 0, -1, -1, 1, 1, 1]


def test_aggregate_bits_sums_tokens():
    stream = make_stream(["one", "two"], paragraph_start=[True, True])
    tok = tokenize_stream(stream, lambda text: [ord(character) for character in text])
    logprobs = np.full(len(tok.tokens), -np.log(2.0))
    bits = aggregate_bits(tok, logprobs, 2)
    assert np.allclose(bits, [3.0, 3.0])
