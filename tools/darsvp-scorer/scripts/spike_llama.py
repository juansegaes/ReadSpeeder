"""Load a GGUF model and inspect the llama-cpp-python API.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\spike_llama.py C:\\Users\\Juan\\models\\model.gguf
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: spike_llama.py MODEL.gguf")
        return 2
    model_path = Path(sys.argv[1])
    if not model_path.exists():
        print(f"Model not found: {model_path}")
        return 2

    from llama_cpp import Llama

    llm = Llama(
        model_path=str(model_path),
        n_ctx=1024,
        n_gpu_layers=-1,
        n_batch=512,
        logits_all=True,
        verbose=True,
    )
    print("scores attribute:", type(llm.scores), np.asarray(llm.scores).shape)
    print("n_vocab:", getattr(llm, "n_vocab", lambda: "?")())
    print("token_bos:", llm.token_bos())

    prompt = "The cat sat on the"
    tokens = llm.tokenize(prompt.encode("utf-8"), add_bos=False, special=False)
    llm.reset()
    llm.eval(tokens)
    scores = np.asarray(llm.scores)
    print("scores after eval:", scores.shape)
    row = scores[len(tokens) - 1]
    order = np.argsort(row)[::-1][:5]
    print("top 5:")
    for token in order:
        piece = llm.detokenize([int(token)]).decode("utf-8", "replace")
        print(f"  {piece!r} {row[int(token)]:.4f}")

    def logprob(token: int) -> float:
        maximum = float(row.max())
        logsumexp = maximum + np.log(np.exp(row - maximum).sum())
        return float(row[token] - logsumexp)

    mat = llm.tokenize(" mat".encode("utf-8"), add_bos=False, special=False)[0]
    quantum = llm.tokenize(" quantum".encode("utf-8"), add_bos=False, special=False)[0]
    print(f"log P(' mat') = {logprob(mat):+.4f}")
    print(f"log P(' quantum') = {logprob(quantum):+.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
