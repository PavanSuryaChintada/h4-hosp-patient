"""Stage 1 of name resolution: pull the drug name out of a line as the nurse wrote it.

    "T. Glycomet-GP 1 1-0-1 after food"   ->  name words ("glycomet-gp",)
    "Tab Shylcal500 BID"                  ->  ("shylcal",)
    "cap Razo - D"                        ->  ("razo-d",)
    "x Brufen 400 PRN stopped"            ->  ("brufen",)
    "T telmisartan + amlodipine od"       ->  parts (("telmisartan",), ("amlodipine",))

Lowercases, strips leading form words (Tab, T., Cap, Inj, Syp, Sach, Inh, ...) and markers
("x", "stop"), splits a squashed strength off a name ("telma40"), rejoins hyphenated brand
suffixes, and stops at the first strength, dose pattern, frequency or instruction word. Release
qualifiers (SR, MR, XR, DS, ...) are kept here: some brands include them, and the resolver tries
the name with and without trailing words. The original string is never changed; it stays on the
record for the output and the UI.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

# Dose-form words written before the name. Stripped while they lead the line.
FORM_WORDS = frozenset({
    "tab", "tabs", "tablet", "tablets", "t", "cap", "caps", "capsule", "capsules", "c",
    "inj", "injection", "syp", "syr", "syrup", "susp", "suspension", "sach", "sachet",
    "sachets", "inh", "inhaler", "mdi", "dpi", "rotacap", "rotacaps", "respule", "respules",
    "neb", "drops", "drop", "gel", "cream", "oint", "ointment", "patch", "powder", "lotion",
    "spray", "soln", "solution", "liq", "liquid", "granules", "pwd",
})
# Status markers written before the name.
LEADING_MARKERS = frozenset({"x", "stop", "stopped", "omit", "hold", "held", "old"})
# Words that end the name: frequency, timing, instructions, units and status.
NAME_STOP_WORDS = frozenset({
    "od", "bd", "bid", "tds", "tid", "qid", "qds", "hs", "sos", "prn", "stat", "once", "twice",
    "thrice", "daily", "weekly", "monthly", "alternate", "alt", "morning", "night", "nightly",
    "bedtime", "noon", "evening", "after", "before", "with", "at", "if", "for", "x", "every",
    "empty", "continue", "continued", "cont", "stopped", "stop", "omit", "held", "hold",
    "discontinued", "dc", "old", "rx", "bbf", "bf", "ac", "pc", "food", "meals", "meal",
    "day", "days", "wk", "wks", "week", "weeks", "mg", "mcg", "g", "gm", "ml", "iu", "units",
    "unit", "u", "puffs", "puff", "tsp", "tab", "tabs", "cap", "caps", "sachet", "in", "on",
    "per", "when", "as", "needed", "only", "then", "till", "until", "from", "to", "of", "a",
    "the", "half", "one", "two", "three", "times", "time", "lunch", "dinner", "breakfast",
    "pain", "fever", "-", "--",
})
# Characters that join two generics in one entry: "telmisartan + amlodipine", "a/b".
COMBO_JOINERS = re.compile(r"\s*[+/&]\s*")
SQUASHED_STRENGTH = re.compile(r"^([a-z][a-z\-]{2,}?)(\d[\d.]*[a-z]*)$")
DOSE_PATTERN = re.compile(r"^\d+(\.\d+)?(-\d+(\.\d+)?)+$|^\d")
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)


@dataclass(frozen=True)
class Normalised:
    """A written line reduced to the words that name the drug."""

    raw: str
    name_words: tuple[str, ...]            # the name, lowercased, in order
    parts: tuple[tuple[str, ...], ...]     # the name split at '+', '/' or '&'; one part if none
    head_words: tuple[str, ...] = ()       # every word from the name onward, unsplit: brand
                                           # names that contain numbers ("Mixtard 30") live here

    @property
    def name(self) -> str:
        """The name words joined by spaces, for display and provenance."""
        return " ".join(self.name_words)


def clean(text: str) -> str:
    """NFKC, drop zero-width characters, unify dashes, lowercase, collapse whitespace.

    Mirrors how the official scorer cleans tokens before comparing them.
    """
    text = unicodedata.normalize("NFKC", str(text)).translate(_INVISIBLE)
    text = re.sub(r"[‐-―]", "-", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def key(text: str) -> str:
    """Matching key: lowercase letters and digits only. "Glycomet-GP" and "glycomet gp" agree."""
    return re.sub(r"[^a-z0-9]", "", clean(text))


def _split_words(text: str) -> list[str]:
    """Split on spaces, separate commas/parentheses, and rejoin hyphen fragments."""
    text = re.sub(r"[(),:]", " ", text)
    text = re.sub(r"\s*-\s*(?=[a-z])", "-", text)      # "razo - d" -> "razo-d"
    words = []
    for word in text.split():
        word = word.strip(".")
        if not word:
            continue
        squashed = SQUASHED_STRENGTH.match(word)
        if squashed and not squashed.group(1).endswith("-"):
            words += [squashed.group(1), squashed.group(2)]   # "telma40" -> "telma", "40"
        else:
            words.append(word)
    return words


def _strip_leading(words: list[str]) -> list[str]:
    """Drop leading form words and status markers ("Tab", "T.", "x", "stop")."""
    while words and (words[0] in FORM_WORDS or words[0] in LEADING_MARKERS):
        words = words[1:]
    return words


def _name_words(words: list[str]) -> tuple[str, ...]:
    """Words up to the first strength, dose pattern, frequency or instruction word."""
    name = []
    for word in words:
        if word in NAME_STOP_WORDS or DOSE_PATTERN.match(word):
            break
        name.append(word)
    return tuple(name)


@lru_cache(maxsize=65536)
def normalise(raw: str) -> Normalised:
    """Reduce one written medication line to its name words. Pure, so cached.

    Args:
        raw: The line exactly as written.

    Returns:
        The name words, and the name split into parts where it joins generics with '+', '/'
        or '&'. Both may be empty, for example for a line that is only a dose.
    """
    text = clean(raw)
    head_words = tuple(_strip_leading(_split_words(text)))
    pieces = [p for p in COMBO_JOINERS.split(text) if p.strip()]
    parts = []
    for index, piece in enumerate(pieces):
        words = _split_words(piece)
        if index == 0:
            words = _strip_leading(words)
        part = _name_words(words)
        if part:
            parts.append(part)
        if len(part) < len(words):
            break                                  # the name ended inside this piece
    name_words = tuple(word for part in parts for word in part)
    return Normalised(raw=raw, name_words=name_words, parts=tuple(parts), head_words=head_words)
