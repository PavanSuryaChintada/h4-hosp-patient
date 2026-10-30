"""Brand, misspelling and abbreviation -> generic name(s). Abstains rather than guessing.

Stages, in order, each tried only if the one before found nothing:

    1. normalise    pull the name words out of the line            (resolve/normalise.py)
    2. exact        the name, or the name plus up to two following words, is a known generic,
                    brand, combination brand or curated synonym
    3. non-drug     the line is a device, test, diet or follow-up note: resolves to nothing
    4. parts        "a + b", "a/b", "a-b": every part resolves on its own -> the union
    5. prefix       a truncated name (5+ letters) that starts exactly one drug's names
    6. fuzzy        candidates from rapidfuzz WRatio, character trigrams and the first-letter
                    bucket, reranked by 0.60 edit similarity + 0.25 trigram overlap
                    + 0.15 length ratio
    7. abstain      best fuzzy score < MIN_CONFIDENCE ("no_confident_match"), or best minus
                    the best *different* drug < MIN_MARGIN ("ambiguous")

Deterministic: ties break alphabetically, results are cached per written string, and nothing
depends on the order patients arrive in. The tables are authoritative; every name the resolver
can output is a generic from ``drug_reference.csv``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process
from rapidfuzz.distance import OSA

from medsafe.data.schema import CombinationBrand, Drug
from medsafe.resolve import thresholds
from medsafe.resolve.normalise import Normalised, key, normalise
from medsafe.resolve.synonyms import COMBO_PART_SYNONYMS, NON_DRUG_WORDS, SYNONYMS

METHODS = ("exact", "synonym", "parts", "prefix", "fuzzy", "non_drug", "abstained")


@dataclass(frozen=True)
class Resolution:
    """What one written line resolved to, and how sure the resolver is."""

    raw: str                                   # the line exactly as written
    normalised: str                            # the name words the resolver matched on
    generics: tuple[str, ...]                  # sorted; empty for non-drug or abstained
    method: str                                # one of METHODS
    confidence: float                          # 0-1
    candidates: tuple[tuple[str, float], ...] = ()   # top 3 drugs considered, with scores
    abstain_reason: str | None = None          # no_name | no_confident_match | ambiguous

    @property
    def resolved_generic(self) -> str | None:
        """Generics joined by ';' as the submission wants them, or None if none."""
        return ";".join(self.generics) or None

    @property
    def verify_manually(self) -> bool:
        """True if the resolver abstained: the line must be checked by a person."""
        return self.method == "abstained"


@dataclass(frozen=True)
class NameEntry:
    """One way a drug can be written, keyed for matching."""

    key: str
    label: str                                 # as written in the table
    generics: tuple[str, ...]
    source: str                                # generic | brand | combination | synonym


@dataclass
class NameIndex:
    """Every known written form of every drug, built from the reference tables.

    A key that two tables map to different drugs is ambiguous and never matched exactly.
    """

    entries: dict[str, NameEntry] = field(default_factory=dict)
    ambiguous: set[str] = field(default_factory=set)
    dropped_synonyms: list[str] = field(default_factory=list)

    @classmethod
    def build(cls, drugs: Mapping[str, Drug], combinations: Sequence[CombinationBrand],
              synonyms: Mapping[str, tuple[str, ...]] = SYNONYMS) -> NameIndex:
        """Index generic names, single brands, combination brands and curated synonyms.

        Args:
            drugs: The drug reference, keyed by generic.
            combinations: Combination brands.
            synonyms: Written form -> generics. Entries naming an unknown generic are dropped.
        """
        index = cls()
        for drug in drugs.values():
            index._add(drug.generic, (drug.generic,), "generic")
            for brand in drug.brands:
                index._add(brand, (drug.generic,), "brand")
        for combination in combinations:
            index._add(combination.brand, combination.generics, "combination")
        for written, generics in sorted(synonyms.items()):
            if all(g in drugs for g in generics):
                index._add(written, tuple(sorted(generics)), "synonym")
            else:
                index.dropped_synonyms.append(written)
        return index

    def _add(self, label: str, generics: tuple[str, ...], source: str) -> None:
        """Add one written form; a clash with a different drug marks the key ambiguous."""
        entry_key = key(label)
        if not entry_key:
            return
        existing = self.entries.get(entry_key)
        if existing is None:
            self.entries[entry_key] = NameEntry(entry_key, label, generics, source)
        elif existing.generics != generics:
            self.ambiguous.add(entry_key)

    def exact(self, text_key: str) -> NameEntry | None:
        """The entry for an exact key, or None if unknown or ambiguous."""
        if text_key in self.ambiguous:
            return None
        return self.entries.get(text_key)

    @property
    def keys(self) -> list[str]:
        """Every matchable key, sorted, ambiguous ones excluded."""
        return sorted(k for k in self.entries if k not in self.ambiguous)


def trigrams(text: str) -> frozenset[str]:
    """Character trigrams of ``text`` padded with '#', so short names still have some."""
    padded = f"#{text}#"
    return frozenset(padded[i:i + 3] for i in range(len(padded) - 2))


def similarity(query: str, candidate: str) -> float:
    """Phase 2 rerank score in [0, 1]: 0.60 edit + 0.25 trigram + 0.15 length ratio.

    The edit term is optimal-string-alignment similarity: like Levenshtein, but a swap of two
    neighbouring letters ("Telam" for "Telma") is one edit, not two. Handwritten transpositions
    are common, and plain Levenshtein ranked them below unrelated drugs (docs/DECISIONS.md D-017).
    """
    edit = OSA.normalized_similarity(query, candidate)
    a, b = trigrams(query), trigrams(candidate)
    trigram = len(a & b) / len(a | b) if a | b else 0.0
    length = min(len(query), len(candidate)) / max(len(query), len(candidate), 1)
    return 0.60 * edit + 0.25 * trigram + 0.15 * length


class Resolver:
    """Resolves written lines against one ``NameIndex`` at fixed thresholds."""

    def __init__(self, index: NameIndex, min_confidence: float = thresholds.MIN_CONFIDENCE,
                 min_margin: float = thresholds.MIN_MARGIN,
                 min_prefix_length: int = thresholds.MIN_PREFIX_LENGTH,
                 rank_cache: dict | None = None) -> None:
        """Prepare the candidate generators.

        Args:
            index: Known written forms.
            min_confidence: Best fuzzy score must reach this, or the resolver abstains.
            min_margin: Best score must beat the best different drug by this, or it abstains.
            min_prefix_length: Shortest truncated name the prefix stage will complete.
            rank_cache: Fuzzy rankings to share between resolvers built on the same index.
                Rankings do not depend on the thresholds, so a threshold sweep computes each
                once. Leave None for a private cache.
        """
        self.index = index
        self.min_confidence = min_confidence
        self.min_margin = min_margin
        self.min_prefix_length = min_prefix_length
        self._keys = index.keys
        self._trigrams = {k: trigrams(k) for k in self._keys}
        self._by_letter: dict[str, list[str]] = {}
        for k in self._keys:
            self._by_letter.setdefault(k[0], []).append(k)
        self._cache: dict[str, Resolution] = {}
        self._ranked: dict = rank_cache if rank_cache is not None else {}

    def resolve(self, raw: str) -> Resolution:
        """Resolve one written line. Same string, same answer, every time."""
        if raw not in self._cache:
            self._cache[raw] = self._resolve(raw)
        return self._cache[raw]

    def _resolve(self, raw: str) -> Resolution:
        """Run the stages in order; see the module docstring."""
        n = normalise(raw)
        if not n.name_words:
            return Resolution(raw, "", (), "abstained", 0.0, abstain_reason="no_name")

        if len(n.parts) == 1:
            entry = self._exact(n)
            if entry is not None:
                return self._found(n, entry.generics,
                                   "synonym" if entry.source == "synonym" else "exact", 1.0)
        if NON_DRUG_WORDS.intersection(n.head_words) or NON_DRUG_WORDS.intersection(n.name_words):
            return Resolution(raw, n.name, (), "non_drug", 1.0)

        explicit = len(n.parts) > 1
        parts = n.parts if explicit else self._hyphen_parts(n)
        if parts:
            min_fuzzy = (self.min_confidence if explicit
                         else max(self.min_confidence, thresholds.HYPHEN_PART_MIN_CONFIDENCE))
            resolved = [self._resolve_part(part, min_fuzzy) for part in parts]
            if all(resolved):
                generics = tuple(sorted({g for r in resolved for g in r[0]}))
                return self._found(n, generics, "parts", min(r[1] for r in resolved))

        prefix = self._prefix(n.name_words[0])
        if prefix is not None:
            return self._found(n, prefix, "prefix", thresholds.PREFIX_CONFIDENCE)
        return self._fuzzy(n)

    def _found(self, n: Normalised, generics: tuple[str, ...], method: str,
               confidence: float) -> Resolution:
        """A successful resolution record."""
        return Resolution(n.raw, n.name, generics, method, confidence,
                          candidates=((";".join(generics), round(confidence, 4)),))

    def _exact(self, n: Normalised) -> NameEntry | None:
        """Longest exact match over the name words plus up to two words after them.

        Each length is also tried with digits stripped from its last word, so a strength
        written onto a brand suffix ("Deplatt A75") still finds "Deplatt-A", and does so
        before the shorter "Deplatt" (a different product).
        """
        longest = min(len(n.head_words), len(n.name_words) + thresholds.MAX_EXTRA_HEAD_WORDS)
        for count in range(longest, 0, -1):
            words = n.head_words[:count]
            stripped = words[-1].rstrip("0123456789.")
            variants = [" ".join(words)]
            if count > 1 and stripped and stripped != words[-1]:
                variants.append(" ".join(words[:-1] + (stripped,)))
            for variant in variants:
                entry = self.index.exact(key(variant))
                if entry is not None:
                    return entry
        return None

    def _hyphen_parts(self, n: Normalised) -> tuple[tuple[str, ...], ...]:
        """Split a single hyphenated name ("carbidopa-levodopa") into parts, if it has one."""
        if len(n.name_words) == 1 and "-" in n.name_words[0]:
            pieces = tuple((p,) for p in n.name_words[0].split("-") if p)
            return pieces if len(pieces) > 1 else ()
        return ()

    def _resolve_part(self, words: tuple[str, ...],
                      min_fuzzy: float) -> tuple[tuple[str, ...], float] | None:
        """Resolve one part of a combination entry: exact, combination shorthand, then fuzzy.

        ``min_fuzzy`` is the score a fuzzy match needs. Parts joined explicitly with '+' or '/'
        use MIN_CONFIDENCE. Pieces of a hyphenated name need HYPHEN_PART_MIN_CONFIDENCE: a hyphen
        is usually part of a brand ("Meftal-Spas"), and loosely matching its fragments would
        invent a combination that does not exist.
        """
        for count in range(len(words), 0, -1):
            part_key = key(" ".join(words[:count]))
            entry = self.index.exact(part_key)
            if entry is not None:
                return entry.generics, 1.0
            if part_key in COMBO_PART_SYNONYMS:
                return COMBO_PART_SYNONYMS[part_key], 1.0
        result = self._rank([key(" ".join(words))])
        if result and result[0][1] >= min_fuzzy and self._decisive(result):
            return result[0][0], result[0][1]
        return None

    def _prefix(self, word: str) -> tuple[str, ...] | None:
        """Generics of the only drug whose names start with ``word`` (5+ letters), else None."""
        stem = key(word)
        if len(stem) < self.min_prefix_length:
            return None
        found = {self.index.entries[k].generics for k in self._by_letter.get(stem[0], ())
                 if k.startswith(stem) and k != stem}
        return found.pop() if len(found) == 1 else None

    def _rank(self, queries: Iterable[str]) -> list[tuple[tuple[str, ...], float, str]]:
        """Best score per distinct drug over every query, best first, ties alphabetical."""
        queries = tuple(queries)
        if queries not in self._ranked:
            self._ranked[queries] = self._rank_uncached(queries)
        return self._ranked[queries]

    def _rank_uncached(self, queries: tuple[str, ...]) -> list[tuple[tuple[str, ...], float, str]]:
        """Score every candidate from the three generators; see ``_rank``."""
        best: dict[tuple[str, ...], tuple[float, str]] = {}
        for query in queries:
            if len(query) < 3:
                continue
            pool = {match for match, _, _ in process.extract(
                query, self._keys, scorer=fuzz.WRatio, limit=thresholds.FUZZY_TOP_K)}
            query_grams = trigrams(query)
            bucket = self._by_letter.get(query[0], [])
            by_overlap = sorted(bucket, key=lambda k: (-len(query_grams & self._trigrams[k]), k))
            pool.update(by_overlap[:thresholds.FUZZY_TOP_K])
            for candidate in pool:
                score = similarity(query, candidate)
                generics = self.index.entries[candidate].generics
                if generics not in best or score > best[generics][0]:
                    best[generics] = (score, candidate)
        ranked = [(g, s, c) for g, (s, c) in best.items()]
        return sorted(ranked, key=lambda item: (-item[1], ";".join(item[0])))

    @staticmethod
    def _margin(ranked: list[tuple[tuple[str, ...], float, str]]) -> float:
        """Gap between the best drug and the best different drug; 1.0 if there is no rival."""
        return ranked[0][1] - ranked[1][1] if len(ranked) > 1 else 1.0

    def _decisive(self, ranked: list[tuple[tuple[str, ...], float, str]]) -> bool:
        """True if the best drug beats every other by at least MIN_MARGIN, and is not tied.

        A tie between two different drugs is never decisive, whatever MIN_MARGIN is: picking
        one alphabetically would be a coin toss presented as an answer.
        """
        margin = self._margin(ranked)
        return margin > 1e-9 and margin >= self.min_margin

    def _fuzzy(self, n: Normalised) -> Resolution:
        """Rerank fuzzy candidates and decide.

        Queries are the name's first one, two and three words, plus the name with up to two
        following words, for brands that contain a number ("Huminsulin 30/70").
        """
        queries = [key(" ".join(n.name_words[:count]))
                   for count in range(1, min(3, len(n.name_words)) + 1)]
        longest = min(len(n.head_words), len(n.name_words) + thresholds.MAX_EXTRA_HEAD_WORDS)
        queries += [key(" ".join(n.head_words[:count]))
                    for count in range(len(n.name_words) + 1, longest + 1)]
        ranked = self._rank(dict.fromkeys(queries))
        top3 = tuple((";".join(g), round(s, 4)) for g, s, _ in ranked[:3])
        if not ranked or ranked[0][1] < self.min_confidence:
            return Resolution(n.raw, n.name, (), "abstained", ranked[0][1] if ranked else 0.0,
                              top3, "no_confident_match")
        if not self._decisive(ranked):
            return Resolution(n.raw, n.name, (), "abstained", ranked[0][1], top3, "ambiguous")
        return Resolution(n.raw, n.name, ranked[0][0], "fuzzy", ranked[0][1], top3)
