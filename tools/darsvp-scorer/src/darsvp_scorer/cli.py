"""Command line interface: score, inspect, check."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np

from . import __version__
from .extract import SUPPORTED_LANGUAGES, load_book
from .output import (
    WordStream,
    build_document,
    flatten_book,
    truncate_stream,
    validate_document,
    write_document,
)
from .surprisal.unigram import UnigramBackend
from .textnorm import word_core
from .weights import Config, combine, load_config

BASE_WPM = 300


def _reconfigure_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="darsvp-score",
        description="Score books for dynamic adaptive RSVP (daRSVP) reading.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    score = subparsers.add_parser("score", help="score a book into a .darsvp.json file")
    score.add_argument("input", type=Path)
    score.add_argument("-o", "--output", type=Path)
    score.add_argument("--backend", choices=("llama", "unigram"))
    score.add_argument("--model", type=Path)
    score.add_argument("--lang", choices=SUPPORTED_LANGUAGES)
    score.add_argument("--config", type=Path)
    score.add_argument("--normalize", choices=("content", "total"))
    score.add_argument("--n-ctx", type=int, default=1024)
    score.add_argument("--overlap", type=int, default=256)
    score.add_argument("--n-gpu-layers", type=int, default=-1)
    score.add_argument("--no-cover", action="store_true")
    score.add_argument("--debug-fields", action="store_true")
    score.add_argument("--cache-dir", type=Path, default=Path(".darsvp-cache"))
    score.add_argument("--max-words", type=int)

    inspect = subparsers.add_parser("inspect", help="inspect a .darsvp.json file")
    inspect.add_argument("file", type=Path)
    inspect.add_argument("--start", type=int, default=0)
    inspect.add_argument("--count", type=int, default=60)
    inspect.add_argument("--top", type=int, default=25)

    check = subparsers.add_parser("check", help="check the llama.cpp model and GPU")
    check.add_argument("--model", type=Path, required=True)
    check.add_argument("--n-gpu-layers", type=int, default=-1)

    return parser


def _cache_path(cache_dir: Path, model_id: str, words: list[str]) -> Path:
    digest = hashlib.sha256(
        (model_id + "\n" + "\n".join(words)).encode("utf-8")
    ).hexdigest()
    return cache_dir / f"{digest}.npy"


def _make_backend(args, stream: WordStream):
    if args.model is not None or args.backend == "llama":
        if args.model is None:
            raise ValueError("--backend llama requires --model PATH.gguf")
        from .surprisal.llama import LlamaBackend

        return LlamaBackend(
            args.model,
            n_ctx=args.n_ctx,
            overlap=args.overlap,
            n_gpu_layers=args.n_gpu_layers,
        )
    return UnigramBackend()


def _score(args) -> int:
    cfg = load_config(args.config)
    if args.normalize:
        cfg = Config(**{**cfg.__dict__, "normalize": args.normalize})

    book = load_book(args.input, include_cover=not args.no_cover)
    stream = flatten_book(book)
    if args.max_words is not None:
        stream = truncate_stream(stream, args.max_words)
    if not stream.words:
        raise ValueError("The document contains no words")

    language = args.lang
    if language is None:
        candidate = book.language
        language = candidate if candidate in SUPPORTED_LANGUAGES else "en"
        if candidate and candidate not in SUPPORTED_LANGUAGES:
            print(
                f"Warning: language {candidate!r} is not supported; using 'en'.",
                file=sys.stderr,
            )

    backend = _make_backend(args, stream)
    if backend.name == "unigram":
        print(
            "Note: the unigram backend ignores context; it only uses word frequency.",
            file=sys.stderr,
        )

    started = time.perf_counter()
    cache_path = _cache_path(args.cache_dir, backend.model_id, stream.words)
    surprisal = None
    if cache_path.exists():
        try:
            surprisal = np.load(cache_path)
            if surprisal.shape[0] != len(stream.words):
                surprisal = None
        except Exception:
            surprisal = None
    if surprisal is None:
        surprisal = backend.word_surprisal(stream, language)
        try:
            args.cache_dir.mkdir(parents=True, exist_ok=True)
            np.save(cache_path, surprisal)
        except Exception as error:
            print(f"Warning: could not write cache: {error}", file=sys.stderr)

    weights, debug = combine(stream, surprisal, language, cfg)
    document = build_document(
        book, stream, weights, backend, cfg, args.debug_fields, debug=debug
    )
    output = args.output
    if output is None:
        output = args.input.with_suffix(".darsvp.json")
    write_document(document, output)
    elapsed = time.perf_counter() - started

    _print_summary(document, weights, cfg, backend, elapsed, output, debug)
    return 0


def _print_summary(document, weights, cfg, backend, elapsed, output, debug=None) -> None:
    words = document["text"].split()
    count = len(words)
    base = 60_000.0 / BASE_WPM
    darsvp_ms = float(np.sum(weights)) * base / 100.0
    plain_ms = count * base
    percentiles = np.percentile(weights, [5, 25, 50, 75, 95])
    content = [word_core(word) for word in words]
    content_mask = [bool(core) for core in content]
    if debug and isinstance(debug.get("content"), list):
        content_values = [
            value for value, keep in zip(debug["content"], content_mask) if keep
        ]
        mean_content = float(np.mean(content_values)) if content_values else 0.0
    else:
        mean_content = (
            float(np.mean(weights[[keep for keep in content_mask]])) / 100.0
            if any(content_mask)
            else 0.0
        )
    print(f"Wrote {output}")
    print(f"  title:     {document['title']}")
    print(f"  words:     {count:,}")
    print(f"  chapters:  {len(document['chapters'])}")
    print(f"  backend:   {backend.name} ({backend.model_id})")
    print(f"  normalize: {cfg.normalize}")
    print(f"  time:      {elapsed:.2f} s")
    print(
        "  weights:   p5={:.0f} p25={:.0f} p50={:.0f} p75={:.0f} p95={:.0f}".format(
            *percentiles
        )
    )
    print(f"  mean content multiplier: {mean_content:.3f}")
    print(
        f"  reading time at {BASE_WPM} WPM: daRSVP {darsvp_ms / 1000:.1f} s "
        f"vs plain RSVP {plain_ms / 1000:.1f} s"
    )


def _inspect(args) -> int:
    with open(args.file, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    validate_document(document)

    words = document["text"].split()
    weights = document["weights"]
    debug = document.get("debug") or {}
    content_values = debug.get("content")
    base = 60_000.0 / BASE_WPM

    print(f"File:      {args.file}")
    print(f"Title:     {document['title']}")
    print(f"Author:    {document.get('author') or '-'}")
    print(f"Language:  {document['language']}")
    print(f"Words:     {len(words):,}")
    print(f"Chapters:  {len(document.get('chapters', []))}")
    print(f"Generator: {document.get('generator', {})}")
    print()
    print(f"{'index':>6}  {'weight':>6}  {'ms@300':>7}  word")
    start = max(0, args.start)
    end = min(len(words), start + max(0, args.count))
    for index in range(start, end):
        weight = weights[index]
        print(f"{index:>6}  {weight:>6}  {weight * base / 100:>7.0f}  {words[index]}")

    if args.top > 0 and words:
        ranked = []
        for index, word in enumerate(words):
            if not word_core(word):
                continue
            value = weight = weights[index]
            if isinstance(content_values, list) and len(content_values) == len(words):
                value = content_values[index] * 100
            ranked.append((float(value), index, word, weight))
        ranked.sort(reverse=True)
        print()
        print(f"Longest-held content words (top {args.top}):")
        for value, index, word, weight in ranked[: args.top]:
            print(f"  {index:>6}  {value:>7.0f}  (total {weight:>4})  {word}")
        print()
        print(f"Shortest-held content words (top {args.top}):")
        for value, index, word, weight in reversed(ranked[-args.top :]):
            print(f"  {index:>6}  {value:>7.0f}  (total {weight:>4})  {word}")
    return 0


def _check(args) -> int:
    from .surprisal.llama import LlamaBackend

    backend = LlamaBackend(args.model, n_gpu_layers=args.n_gpu_layers)
    backend.check()
    return 0


def main(argv: list[str] | None = None) -> None:
    _reconfigure_streams()
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "score":
            code = _score(args)
        elif args.command == "inspect":
            code = _inspect(args)
        elif args.command == "check":
            code = _check(args)
        else:
            parser.error("unknown command")
            code = 2
    except (ValueError, FileNotFoundError, IsADirectoryError) as error:
        print(f"error: {error}", file=sys.stderr)
        if os.environ.get("DARSVP_DEBUG") == "1":
            traceback.print_exc()
        raise SystemExit(2)
    except KeyboardInterrupt:
        raise SystemExit(1)
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        if os.environ.get("DARSVP_DEBUG") == "1":
            traceback.print_exc()
        raise SystemExit(1)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
