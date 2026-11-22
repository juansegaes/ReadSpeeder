"""Turn TXT and EPUB files into a :class:`Book` of chapters and paragraphs."""

from __future__ import annotations

import base64
import io
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

from .textnorm import split_paragraph
from .wordrepair import repair_merged_words

SUPPORTED_LANGUAGES = ("en", "es", "fr", "de", "it", "pt")

_IMAGE_TYPES = {
    ebooklib.ITEM_COVER,
    ebooklib.ITEM_IMAGE,
}
_BLOCK_TAGS = {
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "blockquote",
    "pre",
    "dt",
    "dd",
    "figcaption",
    "td",
    "th",
}
_STRIP_TAGS = {"script", "style", "nav"}
_FOOTNOTE_TYPES = {"footnote", "endnote", "rearnote"}
_FOOTNOTE_ROLES = {"doc-footnote", "doc-endnote"}
_NUMBER_RE = re.compile(r"^\[?\d+\]?$")
_WS_RE = re.compile(r"\s+")


@dataclass
class Chapter:
    title: str
    paragraphs: list[list[str]]


@dataclass
class Book:
    title: str
    author: str | None
    language: str | None
    chapters: list[Chapter]
    cover_jpeg: bytes | None


def _clean_title(value: str | None) -> str:
    return _WS_RE.sub(" ", (value or "").strip())


def _normalise_language(value: str | None) -> str | None:
    if not value:
        return None
    language = value.strip().replace("_", "-").split("-")[0].lower()
    return language or None


def _metadata(book: epub.EpubBook, namespace: str, name: str) -> str | None:
    try:
        values = book.get_metadata(namespace, name)
    except Exception:
        return None
    if not values:
        return None
    value = values[0][0]
    return _clean_title(str(value)) or None


def _load_txt(path: Path) -> Book:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    paragraphs = [split_paragraph(part) for part in re.split(r"\n\s*\n", text)]
    paragraphs = [words for words in paragraphs if words]
    return Book(
        title=path.stem,
        author=None,
        language=None,
        chapters=[Chapter(title=path.stem, paragraphs=paragraphs)],
        cover_jpeg=None,
    )


def _flatten_toc(entries, prefix: str = "") -> list[tuple[str, str]]:
    """Flatten ebooklib's TOC into (href_without_fragment, title) pairs."""
    flat: list[tuple[str, str]] = []
    for entry in entries:
        if isinstance(entry, epub.Link):
            flat.append((entry.href.split("#", 1)[0], _clean_title(entry.title)))
        elif isinstance(entry, tuple) and len(entry) == 2:
            section, children = entry
            title = _clean_title(getattr(section, "title", "") or "")
            href = getattr(section, "href", "") or ""
            if href:
                flat.append((href.split("#", 1)[0], title))
            flat.extend(_flatten_toc(children))
        elif hasattr(entry, "title"):
            flat.append(("", _clean_title(str(entry.title))))
    return flat


def _remove_footnotes(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()
    for tag in soup.find_all("a"):
        epub_type = " ".join(tag.get("epub:type", "") or "")
        role = " ".join(tag.get("role", "") or "")
        if "noteref" in epub_type or role == "doc-noteref":
            tag.decompose()
    for tag in soup.find_all("sup"):
        text = _clean_title(tag.get_text())
        if _NUMBER_RE.match(text):
            tag.decompose()
    for tag in soup.find_all(True):
        epub_type = " ".join(tag.get("epub:type", "") or "")
        role = " ".join(tag.get("role", "") or "")
        if _FOOTNOTE_TYPES.intersection(epub_type.split()) or role in _FOOTNOTE_ROLES:
            tag.decompose()
    for br in soup.find_all("br"):
        br.replace_with(" ")


def _block_paragraphs(
    soup: BeautifulSoup,
    language: str | None = None,
    repair: bool = True,
) -> list[list[str]]:
    paragraphs: list[list[str]] = []
    for element in soup.find_all(_BLOCK_TAGS):
        if element.find(_BLOCK_TAGS) is not None:
            continue
        words = split_paragraph(element.get_text(), join_inner_tabs=True)
        if language and repair:
            words = repair_merged_words(words, language)
        if words:
            paragraphs.append(words)
    return paragraphs


def _fallback_paragraphs(
    soup: BeautifulSoup,
    language: str | None = None,
    repair: bool = True,
) -> list[list[str]]:
    body = soup.body or soup
    paragraphs: list[list[str]] = []
    for line in body.get_text("\n").split("\n"):
        words = split_paragraph(line, join_inner_tabs=True)
        if language and repair:
            words = repair_merged_words(words, language)
        if words:
            paragraphs.append(words)
    return paragraphs


def _first_heading(soup: BeautifulSoup) -> str | None:
    for tag in soup.find_all(["h1", "h2", "h3"]):
        text = _clean_title(tag.get_text())
        if text:
            return text
    return None


def _cover_bytes(book: epub.EpubBook) -> bytes | None:
    candidates: list = []
    for item in book.get_items_of_type(ebooklib.ITEM_COVER):
        candidates.append(item)
    meta_cover = _metadata(book, "OPF", "cover")
    if meta_cover:
        for item in book.get_items():
            if item.get_id() == meta_cover or item.get_name() == meta_cover:
                candidates.append(item)
    for item in book.get_items():
        if "cover" in item.get_name().lower():
            candidates.append(item)
    for item in candidates:
        try:
            if item.get_type() not in _IMAGE_TYPES:
                continue
            from PIL import Image

            image = Image.open(io.BytesIO(item.get_content()))
            image = image.convert("RGB")
            image.thumbnail((1024, 1024))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=85)
            return buffer.getvalue()
        except Exception:
            continue
    return None


def _load_epub(path: Path, include_cover: bool, repair_merged: bool = True) -> Book:
    book = epub.read_epub(str(path))
    title = _metadata(book, "DC", "title") or path.stem
    author = _metadata(book, "DC", "creator")
    language = _normalise_language(_metadata(book, "DC", "language"))

    toc_map: dict[str, str] = {}
    try:
        for href, toc_title in _flatten_toc(book.toc):
            if href and toc_title and href not in toc_map:
                toc_map[href] = toc_title
    except Exception:
        toc_map = {}

    chapters: list[Chapter] = []
    for idref, linear in book.spine:
        if linear == "no":
            continue
        item = book.get_item_with_id(idref)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        soup = BeautifulSoup(item.get_content(), "html.parser")
        _remove_footnotes(soup)
        paragraphs = _block_paragraphs(soup, language, repair_merged)
        if not paragraphs:
            paragraphs = _fallback_paragraphs(soup, language, repair_merged)
        if not paragraphs:
            continue
        name = item.get_name()
        chapter_title = toc_map.get(name)
        if not chapter_title:
            chapter_title = _first_heading(soup)
        if not chapter_title:
            chapter_title = f"Section {len(chapters) + 1}"
        chapters.append(Chapter(title=chapter_title, paragraphs=paragraphs))

    return Book(
        title=title,
        author=author,
        language=language,
        chapters=chapters,
        cover_jpeg=_cover_bytes(book) if include_cover else None,
    )


def load_book(
    path: Path,
    include_cover: bool = True,
    repair_merged: bool = True,
) -> Book:
    """Load a TXT or EPUB file into a :class:`Book`."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return _load_txt(path)
    if suffix == ".epub":
        return _load_epub(path, include_cover, repair_merged)
    raise ValueError(f"Unsupported input type: {path.suffix or '(none)'}")
