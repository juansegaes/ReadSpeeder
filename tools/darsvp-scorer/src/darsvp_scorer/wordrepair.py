"""Split words that print-to-EPUB conversion accidentally joined together.

Some EPUBs are produced from scanned or PDF text and lose the space between two
words (``Thencame``, ``sayto``, ``mypoor``).  A language model cannot score those
as two words, and the reader shows them as one long word.  This module repairs
the clear cases with a conservative dictionary heuristic:

* the whole token is unknown to :mod:`wordfreq`;
* both halves are common words;
* the split is the most balanced one.

It never touches tokens that are already known words, and it leaves unusual
single-letter splits alone unless the letter is ``I`` or ``a``.
"""

from __future__ import annotations

from wordfreq import zipf_frequency

from .textnorm import split_word_parts

# Both halves must be at least this common.  The value is deliberately
# conservative: it catches "Thencame" and "sayto" but leaves "jurymen" alone.
MIN_HALF_ZIPF = 3.6
SINGLE_LETTERS = frozenset({"I", "a", "A"})


def _best_split(core: str, language: str) -> tuple[float, str, str] | None:
    best: tuple[float, str, str] | None = None
    for index in range(1, len(core)):
        left, right = core[:index], core[index:]
        if not left.isalpha() or not right.isalpha():
            continue
        if len(left) == 1 and left not in SINGLE_LETTERS:
            continue
        if len(right) == 1 and right not in SINGLE_LETTERS:
            continue
        left_zipf = zipf_frequency(left.lower(), language)
        right_zipf = zipf_frequency(right.lower(), language)
        if left_zipf < MIN_HALF_ZIPF or right_zipf < MIN_HALF_ZIPF:
            continue
        score = min(left_zipf, right_zipf)
        if best is None or score > best[0]:
            best = (score, left, right)
    return best


def _is_known_men_word(core: str, language: str) -> bool:
    """Return True for words like "jurymen" that must not be split."""
    lowered = core.lower()
    if not lowered.endswith("men") or len(lowered) <= 4:
        return False
    stem = lowered[:-3]
    return stem.endswith("y") and zipf_frequency(stem, language) >= MIN_HALF_ZIPF


def repair_word(word: str, language: str = "en") -> list[str]:
    """Return ``word`` split into two words when it is a clear merge."""
    prefix, core, suffix = split_word_parts(word)
    if (
        len(core) < 4
        or not core.isalpha()
        or zipf_frequency(core.lower(), language) > 0
        or _is_known_men_word(core, language)
    ):
        return [word]
    split = _best_split(core, language)
    if split is None:
        return [word]
    _, left, right = split
    return [prefix + left, right + suffix]


def repair_merged_words(words: list[str], language: str = "en") -> list[str]:
    """Repair every word in ``words`` that looks like two merged words."""
    repaired: list[str] = []
    for word in words:
        repaired.extend(repair_word(word, language))
    return repaired
