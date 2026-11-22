"""Lexical features: word length and corpus frequency."""

from __future__ import annotations

from wordfreq import zipf_frequency


def zipf_for(core: str, lang: str | None, cfg) -> float:
    """Zipf frequency of a word core; numbers get a fixed value."""
    if not core:
        return 0.0
    if any(ch.isdigit() for ch in core):
        return cfg.digit_zipf
    return float(zipf_frequency(core.lower(), lang or "en"))
