"""Word-frequency fallback backend: rarity, not context."""

from __future__ import annotations

import numpy as np
from wordfreq import word_frequency

from ..textnorm import word_core


class UnigramBackend:
    name = "unigram"
    model_id = "wordfreq"

    def word_surprisal(self, stream, lang: str) -> np.ndarray:
        bits = np.zeros(len(stream.words), dtype=np.float64)
        for i, word in enumerate(stream.words):
            core = word_core(word)
            if not core:
                continue
            frequency = word_frequency(core.lower(), lang or "en", minimum=1e-8)
            bits[i] = -np.log2(frequency)
        return bits
