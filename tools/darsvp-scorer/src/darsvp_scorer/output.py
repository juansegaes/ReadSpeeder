"""Flatten books into word streams and build/validate the daRSVP JSON document."""

from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from . import __version__
from .extract import Book, SUPPORTED_LANGUAGES

FORMAT_NAME = "darsvp"
FORMAT_VERSION = 1
MIN_WEIGHT = 40
MAX_WEIGHT = 600
MAX_TEXT_LENGTH = 5_000_000


@dataclass
class WordStream:
    words: list[str]
    paragraph_start: list[bool]
    paragraph_end: list[bool]
    chapter_end: list[bool]
    chapters: list[tuple[str, int]]
    text: str


def flatten_book(book: Book) -> WordStream:
    """Flatten a book into the canonical word stream."""
    words: list[str] = []
    paragraph_start: list[bool] = []
    paragraph_end: list[bool] = []
    chapter_end: list[bool] = []
    chapters: list[tuple[str, int]] = []
    paragraphs: list[str] = []

    for chapter in book.chapters:
        chapter_words = [words for paragraph in chapter.paragraphs for words in paragraph]
        if not chapter_words:
            continue
        chapters.append((chapter.title, len(words)))
        for paragraph in chapter.paragraphs:
            if not paragraph:
                continue
            paragraphs.append(" ".join(paragraph))
            for index, word in enumerate(paragraph):
                words.append(word)
                paragraph_start.append(index == 0)
                paragraph_end.append(index == len(paragraph) - 1)
                chapter_end.append(False)
        chapter_end[-1] = True

    text = "\n\n".join(paragraphs)
    assert text.split() == words, "word stream does not match its text"
    return WordStream(
        words=words,
        paragraph_start=paragraph_start,
        paragraph_end=paragraph_end,
        chapter_end=chapter_end,
        chapters=chapters,
        text=text,
    )


def truncate_stream(stream: WordStream, max_words: int) -> WordStream:
    """Keep the first ``max_words`` words, rounded down to a paragraph end."""
    if max_words >= len(stream.words):
        return stream
    if max_words <= 0:
        return WordStream([], [], [], [], [], "")
    last = max_words - 1
    while last > 0 and not stream.paragraph_end[last]:
        last -= 1
    count = last + 1
    words = stream.words[:count]
    paragraph_start = stream.paragraph_start[:count]
    paragraph_end = stream.paragraph_end[:count]
    chapter_end = stream.chapter_end[:count]

    chapters: list[tuple[str, int]] = []
    for title, start in stream.chapters:
        if start < count:
            chapters.append((title, start))
    paragraphs: list[str] = []
    current: list[str] = []
    for i in range(count):
        if paragraph_start[i] and current:
            paragraphs.append(" ".join(current))
            current = []
        current.append(words[i])
    if current:
        paragraphs.append(" ".join(current))
    text = "\n\n".join(paragraphs)
    return WordStream(
        words=words,
        paragraph_start=paragraph_start,
        paragraph_end=paragraph_end,
        chapter_end=chapter_end,
        chapters=chapters,
        text=text,
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_document(
    book: Book,
    stream: WordStream,
    weights,
    backend,
    cfg,
    debug_fields: bool,
    debug: dict | None = None,
    created: str | None = None,
) -> dict:
    """Build the JSON-serialisable document described in the plan."""
    document = {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "title": book.title,
        "author": book.author,
        "language": book.language,
        "generator": {
            "tool": "darsvp-scorer",
            "toolVersion": __version__,
            "backend": getattr(backend, "name", "unknown"),
            "model": getattr(backend, "model_id", "unknown"),
            "normalize": cfg.normalize,
            "created": created or _utc_now(),
        },
        "text": stream.text,
        "chapters": [
            {"title": title, "startWord": start} for title, start in stream.chapters
        ],
        "weights": [int(value) for value in weights],
    }
    if book.cover_jpeg:
        document["cover"] = base64.b64encode(book.cover_jpeg).decode("ascii")
    if debug_fields and debug:
        document["debug"] = debug
    return document


def _fail(message: str) -> None:
    raise ValueError(message)


def validate_document(document: dict) -> None:
    """Raise ``ValueError`` for every violation of the file contract."""
    if not isinstance(document, dict):
        _fail("Document must be a JSON object")
    if document.get("format") != FORMAT_NAME:
        _fail("format must be 'darsvp'")
    if document.get("version") != FORMAT_VERSION:
        _fail("version must be 1")

    title = document.get("title")
    if not isinstance(title, str) or not title.strip():
        _fail("title must be a non-empty string")
    author = document.get("author")
    if author is not None and not isinstance(author, str):
        _fail("author must be a string or null")
    language = document.get("language")
    if language not in SUPPORTED_LANGUAGES:
        _fail(f"language must be one of {', '.join(SUPPORTED_LANGUAGES)}")

    text = document.get("text")
    if not isinstance(text, str) or not text:
        _fail("text must be a non-empty string")
    if len(text) > MAX_TEXT_LENGTH:
        _fail("text is longer than 5,000,000 characters")
    if text != text.strip():
        _fail("text must not have leading or trailing whitespace")
    for character in text:
        if character.isspace() and character not in (" ", "\n"):
            _fail("text contains whitespace other than space and newline")
    if "  " in text:
        _fail("text contains repeated spaces")
    if "\n\n\n" in text:
        _fail("text contains more than two consecutive newlines")
    if "\n" in text.replace("\n\n", ""):
        _fail("paragraphs must be separated by exactly two newlines")
    for paragraph in text.split("\n\n"):
        if not paragraph or paragraph.startswith(" ") or paragraph.endswith(" "):
            _fail("paragraphs must not be empty or padded with spaces")

    words = text.split()
    weights = document.get("weights")
    if not isinstance(weights, list):
        _fail("weights must be an array")
    if len(weights) != len(words):
        _fail(f"weights has {len(weights)} entries but text has {len(words)} words")
    for weight in weights:
        if isinstance(weight, bool) or not isinstance(weight, int):
            _fail("weights must be integers")
        if not MIN_WEIGHT <= weight <= MAX_WEIGHT:
            _fail(f"weight {weight} is outside [{MIN_WEIGHT}, {MAX_WEIGHT}]")

    chapters = document.get("chapters", [])
    if not isinstance(chapters, list):
        _fail("chapters must be an array")
    previous = -1
    for chapter in chapters:
        if not isinstance(chapter, dict):
            _fail("each chapter must be an object")
        if not isinstance(chapter.get("title"), str):
            _fail("chapter title must be a string")
        start = chapter.get("startWord")
        if isinstance(start, bool) or not isinstance(start, int):
            _fail("chapter startWord must be an integer")
        if not 0 <= start < len(words):
            _fail("chapter startWord is out of range")
        if start <= previous:
            _fail("chapter startWord values must be strictly increasing")
        previous = start

    cover = document.get("cover")
    if cover is not None:
        if not isinstance(cover, str):
            _fail("cover must be a base64 string")
        try:
            raw = base64.b64decode(cover, validate=True)
        except (binascii.Error, ValueError):
            _fail("cover is not valid base64")
        if not (raw.startswith(b"\xff\xd8\xff") or raw.startswith(b"\x89PNG\r\n\x1a\n")):
            _fail("cover must be a JPEG or PNG image")

    if "debug" in document and not isinstance(document["debug"], dict):
        _fail("debug must be an object")


def write_document(document: dict, path) -> None:
    """Validate and write a compact UTF-8 JSON document."""
    validate_document(document)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        json.dump(document, handle, ensure_ascii=False, separators=(",", ":"))
