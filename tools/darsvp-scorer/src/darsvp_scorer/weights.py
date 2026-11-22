"""The daRSVP weight formula: combine features into per-word multipliers."""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

import numpy as np

from .lexical import zipf_for
from .pauses import pause_for
from .textnorm import letter_count, word_core


@dataclass
class Config:
    # content (per-word reading cost)
    w_surprisal: float = 0.22
    w_length: float = 0.12
    w_freq: float = 0.08
    w_spill: float = 0.08
    z_surprisal_min: float = -2.0
    z_surprisal_max: float = 3.0
    length_center: float = 5.0
    length_scale: float = 3.0
    z_length_min: float = -1.33
    z_length_max: float = 3.0
    zipf_center: float = 4.5
    zipf_scale: float = 1.5
    z_freq_min: float = -1.5
    z_freq_max: float = 2.5
    digit_zipf: float = 3.5
    content_min: float = 0.5
    content_max: float = 2.5
    empty_core_content: float = 0.5
    # pauses (added on top, in units of the base word time)
    pause_chapter_end: float = 2.5
    pause_paragraph_end: float = 2.0
    pause_sentence_end: float = 1.5
    pause_semicolon_colon: float = 1.0
    pause_comma: float = 0.75
    pause_dash: float = 0.75
    pause_close_paren: float = 0.3
    pause_abbreviation: float = 0.3
    # final
    final_min: float = 0.4
    final_max: float = 6.0
    normalize: str = "content"  # "content" or "total"


def load_config(path: Path | None) -> Config:
    """Load a TOML config, rejecting unknown keys."""
    if path is None:
        return Config()
    import tomllib

    with open(path, "rb") as handle:
        data = tomllib.load(handle)
    known = {field.name for field in fields(Config)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise ValueError(f"Unknown config key(s): {', '.join(unknown)}")
    if "normalize" in data and data["normalize"] not in ("content", "total"):
        raise ValueError("normalize must be 'content' or 'total'")
    return Config(**data)


def combine(
    stream,
    surprisal_bits: np.ndarray,
    lang: str | None,
    cfg: Config,
    zipf: np.ndarray | None = None,
) -> tuple[np.ndarray, dict]:
    """Return integer weights (hundredths) and a debug dictionary."""
    words = stream.words
    n = len(words)
    cores = [word_core(word) for word in words]
    lengths = np.array([letter_count(core) for core in cores], dtype=np.int64)
    is_content = lengths > 0

    if zipf is None:
        zipf_values = np.array([zipf_for(core, lang, cfg) for core in cores])
    else:
        zipf_values = np.asarray(zipf, dtype=np.float64)
    surprisal = np.asarray(surprisal_bits, dtype=np.float64)

    content_surprisal = surprisal[is_content]
    if content_surprisal.size:
        median = float(np.median(content_surprisal))
        mad = 1.4826 * float(np.median(np.abs(content_surprisal - median)))
        mad = max(mad, 0.5)
        z_surprisal = np.clip(
            (surprisal - median) / mad, cfg.z_surprisal_min, cfg.z_surprisal_max
        )
    else:
        z_surprisal = np.zeros(n)

    z_length = np.clip(
        (lengths - cfg.length_center) / cfg.length_scale,
        cfg.z_length_min,
        cfg.z_length_max,
    )
    z_freq = np.clip(
        (cfg.zipf_center - zipf_values) / cfg.zipf_scale,
        cfg.z_freq_min,
        cfg.z_freq_max,
    )

    paragraph_start = np.asarray(stream.paragraph_start, dtype=bool)
    spill = np.zeros(n)
    for i in range(1, n):
        if not paragraph_start[i]:
            spill[i] = max(0.0, float(z_surprisal[i - 1]))

    cost = (
        1.0
        + cfg.w_surprisal * z_surprisal
        + cfg.w_length * z_length
        + cfg.w_freq * z_freq
        + cfg.w_spill * spill
    )
    content = np.clip(cost, cfg.content_min, cfg.content_max)
    content[~is_content] = cfg.empty_core_content

    if cfg.normalize == "content":
        mean = float(content[is_content].mean()) if is_content.any() else 0.0
        if mean > 0:
            content[is_content] = np.clip(
                content[is_content] / mean, cfg.content_min, cfg.content_max
            )

    pauses = np.array(
        [
            pause_for(
                words[i],
                bool(stream.paragraph_end[i]),
                bool(stream.chapter_end[i]),
                lang,
                cfg,
            )
            for i in range(n)
        ]
    )
    final = np.clip(content + pauses, cfg.final_min, cfg.final_max)
    if cfg.normalize == "total":
        mean = float(final.mean()) if n else 0.0
        if mean > 0:
            final = np.clip(final / mean, cfg.final_min, cfg.final_max)

    weights = np.rint(final * 100).astype(np.int64)
    debug = {
        "surprisalBits": [round(float(value), 4) for value in surprisal],
        "zipf": [round(float(value), 3) for value in zipf_values],
        "content": [round(float(value), 4) for value in content],
    }
    return weights, debug
