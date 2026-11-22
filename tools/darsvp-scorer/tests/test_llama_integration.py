"""Opt-in llama.cpp integration test.

Set DARSVP_TEST_MODEL to a GGUF file to run it.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from darsvp_scorer.output import WordStream
from darsvp_scorer.surprisal.llama import LlamaBackend

MODEL = os.environ.get("DARSVP_TEST_MODEL")


def _stream(words: list[str]) -> WordStream:
    return WordStream(
        words=words,
        paragraph_start=[False] * len(words),
        paragraph_end=[False] * len(words),
        chapter_end=[False] * len(words),
        chapters=[("Test", 0)],
        text=" ".join(words),
    )


@pytest.mark.skipif(not MODEL, reason="DARSVP_TEST_MODEL is not set")
def test_mat_is_more_predictable_than_quantum():
    backend = LlamaBackend(Path(MODEL), n_ctx=256, overlap=64)
    good = _stream(["The", "cat", "sat", "on", "the", "mat."])
    strange = _stream(["The", "cat", "sat", "on", "the", "quantum."])
    good_bits = backend.word_surprisal(good, "en")
    strange_bits = backend.word_surprisal(strange, "en")
    assert np.isfinite(good_bits).all()
    assert good_bits[5] < strange_bits[5]
