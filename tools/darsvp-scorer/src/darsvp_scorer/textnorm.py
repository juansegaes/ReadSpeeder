"""Unicode cleanup and word splitting for daRSVP scoring.

The scorer and the Android app must agree on how many words a book contains.  The app
counts runs of non-whitespace using Kotlin's Unicode-aware ``Char.isWhitespace()``, while
Python uses ``str.split()``.  ``clean_text`` removes or replaces every character the two
could disagree on, so a paragraph is always a sequence of words separated by single ASCII
spaces.
"""

from __future__ import annotations

import unicodedata

CLOSERS = "\"'”’»)]}"
SENTENCE_END = ".!?…。！？"


def _join_inner_tabs(s: str) -> str:
    """Drop tabs that sit between two non-whitespace characters.

    Some EPUBs converted from print insert a tab inside a word (``press\\ted``,
    ``wha\\tev\\ter``).  A tab there is an OCR artifact, not a word separator, so
    removing it keeps the word whole.  Tabs next to whitespace or at the ends of
    a line are left alone and later become spaces.
    """
    out: list[str] = []
    for index, ch in enumerate(s):
        if (
            ch == "\t"
            and 0 < index < len(s) - 1
            and not s[index - 1].isspace()
            and not s[index + 1].isspace()
        ):
            continue
        out.append(ch)
    return "".join(out)


def clean_text(s: str, join_inner_tabs: bool = False) -> str:
    """Normalise a paragraph to words separated by single ASCII spaces.

    ``join_inner_tabs`` removes tabs used as in-word OCR artifacts; leave it
    off for plain text where a tab is a real separator.
    """
    s = unicodedata.normalize("NFC", s)
    if join_inner_tabs:
        s = _join_inner_tabs(s)
    out: list[str] = []
    for ch in s:
        category = unicodedata.category(ch)
        if category == "Cf":
            # Soft hyphen, zero-width space, ZWJ, BOM, ...
            continue
        if ch.isspace() or category in ("Zs", "Zl", "Zp", "Cc"):
            out.append(" ")
        else:
            out.append(ch)
    return " ".join("".join(out).split())


def split_paragraph(paragraph: str, join_inner_tabs: bool = False) -> list[str]:
    """Clean a paragraph and split it into words."""
    cleaned = clean_text(paragraph, join_inner_tabs=join_inner_tabs)
    return cleaned.split() if cleaned else []


def word_core(word: str) -> str:
    """Strip leading and trailing characters that are not alphanumeric."""
    start = 0
    end = len(word)
    while start < end and not word[start].isalnum():
        start += 1
    while end > start and not word[end - 1].isalnum():
        end -= 1
    return word[start:end]


def letter_count(core: str) -> int:
    """Number of alphanumeric characters in a word core."""
    return sum(1 for ch in core if ch.isalnum())


def split_word_parts(word: str) -> tuple[str, str, str]:
    """Split a word into (prefix, core, suffix) around its alphanumeric core."""
    core = word_core(word)
    if not core:
        return word, "", ""
    start = word.index(core)
    end = start + len(core)
    return word[:start], core, word[end:]
