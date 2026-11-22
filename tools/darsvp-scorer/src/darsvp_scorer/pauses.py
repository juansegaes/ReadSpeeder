"""Punctuation-based pause rules."""

from __future__ import annotations

from .textnorm import CLOSERS, SENTENCE_END

ABBREVIATIONS: dict[str, set[str]] = {
    "en": {
        "mr", "mrs", "ms", "dr", "st", "jr", "sr", "prof", "vs", "etc", "fig",
        "no", "vol", "ch", "p", "pp", "approx", "dept", "est",
    },
    "es": {"sr", "sra", "srta", "dr", "dra", "ud", "uds", "pág", "etc", "núm", "cap", "av"},
    "fr": {"m", "mme", "mlle", "dr", "st", "etc", "p", "ex", "cf", "vol", "chap"},
    "de": {"dr", "hr", "fr", "nr", "bzw", "usw", "ca", "vgl", "z.b", "d.h", "s"},
    "it": {"sig", "dott", "prof", "ecc", "pag", "cap"},
    "pt": {"sr", "sra", "dr", "dra", "prof", "etc", "pág", "cap"},
}
_DEFAULT_ABBREVIATIONS = ABBREVIATIONS["en"]


def is_abbreviation(t: str, lang: str | None) -> bool:
    """True when ``t`` looks like an abbreviation ending in a full stop."""
    if not t.endswith("."):
        return False
    stem = t[:-1]
    if not stem:
        return False
    if len(stem) == 1 and stem.isalpha():
        return True
    if ".." in stem:
        # An ellipsis ("wait...", "…") is a sentence end, not an abbreviation.
        return False
    if "." in stem:
        return True
    known = ABBREVIATIONS.get((lang or "en").lower(), _DEFAULT_ABBREVIATIONS)
    return stem.lower() in known


def pause_for(
    word: str,
    is_paragraph_end: bool,
    is_chapter_end: bool,
    lang: str | None,
    cfg,
) -> float:
    """Return the pause multiplier added on top of a word's content cost."""
    t = word.rstrip(CLOSERS)
    last = t[-1:] if t else ""

    if is_chapter_end:
        return cfg.pause_chapter_end
    if is_paragraph_end:
        return cfg.pause_paragraph_end
    if last and last in SENTENCE_END:
        if is_abbreviation(t, lang):
            return cfg.pause_abbreviation
        return cfg.pause_sentence_end
    if last and last in ";:；：":
        return cfg.pause_semicolon_colon
    if last and last in ",，":
        return cfg.pause_comma
    if (last and last in "—–") or word in {"—", "–", "-", "--"}:
        return cfg.pause_dash
    if word.endswith(")"):
        return cfg.pause_close_paren
    return 0.0
