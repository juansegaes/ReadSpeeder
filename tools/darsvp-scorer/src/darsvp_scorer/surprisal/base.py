"""Shared token-level surprisal machinery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

import numpy as np

from ..textnorm import split_word_parts


class SurprisalBackend(Protocol):
    name: str
    model_id: str

    def word_surprisal(self, stream, lang: str) -> np.ndarray: ...


@dataclass
class TokenizedStream:
    tokens: list[int]
    token_word: list[int]


def tokenize_stream(
    stream, tokenize: Callable[[str], list[int]]
) -> TokenizedStream:
    """Tokenize a word stream, keeping an exact token→word map."""
    tokens: list[int] = []
    token_word: list[int] = []

    for i, word in enumerate(stream.words):
        paragraph_start = bool(stream.paragraph_start[i])
        if paragraph_start and i > 0:
            separator = tokenize("\n\n")
            tokens.extend(separator)
            token_word.extend([-1] * len(separator))

        prefix, core, suffix = split_word_parts(word)
        if not core:
            text = word if paragraph_start else " " + word
            word_tokens = tokenize(text)
            tokens.extend(word_tokens)
            token_word.extend([-1] * len(word_tokens))
            continue

        lead = "" if paragraph_start else " "
        if prefix:
            prefix_tokens = tokenize(lead + prefix)
            tokens.extend(prefix_tokens)
            token_word.extend([-1] * len(prefix_tokens))
            core_tokens = tokenize(core)
        else:
            core_tokens = tokenize(lead + core)
        tokens.extend(core_tokens)
        token_word.extend([i] * len(core_tokens))

        if suffix:
            suffix_tokens = tokenize(suffix)
            tokens.extend(suffix_tokens)
            token_word.extend([-1] * len(suffix_tokens))

    return TokenizedStream(tokens=tokens, token_word=token_word)


def _log_softmax_targets(logits: np.ndarray, targets: np.ndarray) -> np.ndarray:
    """log softmax of the target token for each row, in float64, in blocks."""
    count = len(targets)
    result = np.empty(count, dtype=np.float64)
    for start in range(0, count, 128):
        block = np.asarray(logits[start : start + 128], dtype=np.float64)
        rows = np.arange(len(block))
        maximum = block.max(axis=1)
        logsum = maximum + np.log(np.exp(block - maximum[:, None]).sum(axis=1))
        result[start : start + 128] = (
            block[rows, targets[start : start + 128]] - logsum
        )
    return result


def windowed_logprobs(
    tokens: list[int],
    eval_window: Callable[[list[int]], np.ndarray],
    bos: int | None,
    n_ctx: int,
    overlap: int,
    progress: Callable[[int, int], None] | None = None,
) -> np.ndarray:
    """Natural-log probability of every token given the tokens before it."""
    n = len(tokens)
    logprobs = np.full(n, np.nan, dtype=np.float64)
    if n == 0:
        return logprobs
    b = 1 if bos is not None else 0
    if n_ctx - b <= 0:
        raise ValueError("n_ctx is too small")

    score_start = 0
    while score_start < n:
        ctx_start = max(0, score_start - overlap)
        end = min(n, ctx_start + n_ctx - b)
        if end <= score_start:
            raise ValueError("n_ctx is too small for the requested overlap")
        window = ([bos] if bos is not None else []) + tokens[ctx_start:end]
        logits = np.asarray(eval_window(window))

        scored_positions = []
        row_indices = []
        targets = []
        for j in range(score_start, end):
            row = b + (j - ctx_start) - 1
            if row < 0:
                continue
            scored_positions.append(j)
            row_indices.append(row)
            targets.append(tokens[j])
        if scored_positions:
            values = _log_softmax_targets(
                logits[np.asarray(row_indices)], np.asarray(targets)
            )
            for j, value in zip(scored_positions, values):
                logprobs[j] = value
        score_start = end
        if progress is not None:
            progress(end, len(tokens))
    return logprobs


def aggregate_bits(
    tok: TokenizedStream, logprobs_nat: np.ndarray, n_words: int
) -> np.ndarray:
    """Sum per-token surprisal into bits for each word."""
    bits = np.zeros(n_words, dtype=np.float64)
    seen = np.zeros(n_words, dtype=bool)
    has_nan = np.zeros(n_words, dtype=bool)

    for token_index, word_index in enumerate(tok.token_word):
        if word_index < 0:
            continue
        seen[word_index] = True
        value = logprobs_nat[token_index]
        if np.isnan(value):
            has_nan[word_index] = True
        else:
            bits[word_index] += -value / np.log(2.0)

    valid = seen & ~has_nan
    if valid.any():
        median = float(np.median(bits[valid]))
        bits[seen & has_nan] = median
    return bits
