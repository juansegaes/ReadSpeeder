"""llama.cpp backend with Vulkan support (Phase 2)."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from .base import TokenizedStream, aggregate_bits, tokenize_stream, windowed_logprobs


class LlamaBackend:
    name = "llama"

    def __init__(
        self,
        model_path: Path,
        n_ctx: int = 1024,
        overlap: int = 256,
        n_gpu_layers: int = -1,
        n_batch: int = 512,
        verbose: bool = False,
    ):
        from llama_cpp import Llama

        self.model_path = Path(model_path)
        self.model_id = self.model_path.name
        self.n_ctx = n_ctx
        self.overlap = overlap
        self.n_gpu_layers = n_gpu_layers
        self.llm = Llama(
            model_path=str(self.model_path),
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_batch=n_batch,
            logits_all=True,
            verbose=verbose,
        )
        bos = self.llm.token_bos()
        self.bos = None if bos is None or bos < 0 else int(bos)

    # -- llama.cpp adapters -------------------------------------------------
    def _tokenize(self, text: str) -> list[int]:
        data = text.encode("utf-8")
        try:
            return list(self.llm.tokenize(data, add_bos=False, special=False))
        except TypeError:
            return list(self.llm.tokenize(data, add_bos=False))

    def _eval_window(self, tokens: list[int]) -> np.ndarray:
        self.llm.reset()
        self.llm.eval(tokens)
        scores = np.asarray(self.llm.scores)
        return scores[: len(tokens)]

    # -- public API ---------------------------------------------------------
    def word_surprisal(self, stream, lang: str) -> np.ndarray:
        tokenized = tokenize_stream(stream, self._tokenize)
        total = len(tokenized.tokens)
        started = time.perf_counter()

        def progress(done: int, all_tokens: int) -> None:
            elapsed = max(time.perf_counter() - started, 1e-9)
            rate = done / elapsed
            eta = (all_tokens - done) / rate if rate > 0 else 0.0
            print(
                f"\rScoring tokens: {done}/{all_tokens} "
                f"({rate:,.0f} tok/s, ETA {eta:,.0f}s)",
                end="",
                flush=True,
            )

        logprobs = windowed_logprobs(
            tokenized.tokens,
            self._eval_window,
            self.bos,
            self.n_ctx,
            self.overlap,
            progress=progress,
        )
        print()
        return aggregate_bits(tokenized, logprobs, len(stream.words))

    # -- diagnostics --------------------------------------------------------
    def _logprob(self, row: np.ndarray, token: int) -> float:
        row = np.asarray(row, dtype=np.float64)
        maximum = row.max()
        logsumexp = maximum + np.log(np.exp(row - maximum).sum())
        return float(row[token] - logsumexp)

    def check(self) -> None:
        prompt = "The cat sat on the"
        tokens = self._tokenize(prompt)
        scores = self._eval_window(tokens)
        last = scores[-1]

        print(f"Model:      {self.model_path}")
        print(f"Model ID:   {self.model_id}")
        print(f"n_ctx:      {self.n_ctx}")
        print(f"n_gpu_layers: {self.n_gpu_layers}")
        print(f"BOS id:     {self.bos}")
        vocab = getattr(self.llm, "n_vocab", None)
        if callable(vocab):
            vocab = vocab()
        print(f"Vocab size: {vocab}")

        order = np.argsort(last)[::-1][:5]
        print("Top 5 next tokens:")
        for token in order:
            try:
                piece = self.llm.detokenize([int(token)]).decode("utf-8", "replace")
            except Exception:
                piece = str(int(token))
            print(f"  {piece!r:20} {self._logprob(last, int(token)):+.3f}")

        mat = self._tokenize(" mat")[0]
        quantum = self._tokenize(" quantum")[0]
        print(
            f"log P(' mat') = {self._logprob(last, mat):+.3f}   "
            f"log P(' quantum') = {self._logprob(last, quantum):+.3f}"
        )

        sample = "The quick brown fox jumps over the lazy dog. " * 200
        sample_tokens = self._tokenize(sample)[: self.n_ctx]
        started = time.perf_counter()
        self._eval_window(sample_tokens)
        elapsed = time.perf_counter() - started
        rate = len(sample_tokens) / elapsed if elapsed > 0 else 0.0
        print(f"Tokens/second: {rate:,.0f} ({len(sample_tokens)} tokens in {elapsed:.2f}s)")
