"""Regenerate tests/fixtures/sample.darsvp.json with the unigram backend.

Run from tools/darsvp-scorer:

    .\\.venv\\Scripts\\python.exe scripts\\make_fixture.py
"""

from __future__ import annotations

import json
from pathlib import Path

from darsvp_scorer.extract import Book, Chapter
from darsvp_scorer.output import build_document, flatten_book, validate_document
from darsvp_scorer.surprisal.unigram import UnigramBackend
from darsvp_scorer.textnorm import split_paragraph
from darsvp_scorer.weights import Config, combine

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "sample.darsvp.json"
CREATED = "2026-11-22T12:00:00Z"


def _paragraph(text: str) -> list[str]:
    return split_paragraph(text)


def build_book() -> Book:
    return Book(
        title="Sample Book",
        author="Test Author",
        language="en",
        chapters=[
            Chapter(
                title="Chapter One",
                paragraphs=[
                    _paragraph(
                        "“Hello,” said Dr. Smith—the train was late... It arrived at 7."
                    ),
                    _paragraph("The station was quiet, cold, and almost empty."),
                ],
            ),
            Chapter(
                title="Chapter Two",
                paragraphs=[
                    _paragraph("She bought a ticket for the long journey home."),
                    _paragraph("Outside, the rain fell softly on the platform."),
                ],
            ),
        ],
        cover_jpeg=None,
    )


def main() -> None:
    book = build_book()
    stream = flatten_book(book)
    backend = UnigramBackend()
    surprisal = backend.word_surprisal(stream, "en")
    weights, debug = combine(stream, surprisal, "en", Config())
    document = build_document(
        book,
        stream,
        weights,
        backend,
        Config(),
        debug_fields=False,
        debug=debug,
        created=CREATED,
    )
    validate_document(document)
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    with FIXTURE.open("w", encoding="utf-8", newline="") as handle:
        json.dump(document, handle, ensure_ascii=False, separators=(",", ":"))
    print(f"Wrote {FIXTURE} ({len(stream.words)} words)")


if __name__ == "__main__":
    main()
