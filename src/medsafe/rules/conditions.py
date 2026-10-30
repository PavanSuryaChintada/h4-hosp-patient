"""Free-text diagnoses and allergies -> the condition_ids the contraindication table uses.

    "HTN; DM2; h/o UGI bleed"            -> peptic_ulcer
    "no h/o asthma; acute bronchitis"    -> nothing (asthma is negated in its own clause)
    "wheezy since childhood - asthma"    -> asthma
    "No drug allergy (penicillin tolerated)" -> nothing

Text is split into clauses on ';', ',', brackets and ' - '. A clause with a negation cue
negates every condition named in it, and only in it. Words match the vocabulary in
condition_terms.py exactly or within a small edit distance (1 edit for 5-7 letters, 2 for longer;
shorter words and abbreviations must match exactly). An ejection fraction is read as a number:
"EF 35%" is heart failure, "LVEF 60%" is not. Deterministic; nothing is inferred from the
medication list, and a blank diagnosis yields nothing.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from rapidfuzz.distance import OSA

from medsafe.rules.condition_terms import (ALLERGY_ABBREVIATIONS, ALLERGY_PHRASES,
                                           DIAGNOSIS_ABBREVIATIONS, DIAGNOSIS_PHRASES,
                                           EF_HEART_FAILURE_BELOW, NEGATION_CUES, WORD_FORMS)

CLAUSE_SPLIT = re.compile(r"[;,()\[\]]|\s+-+\s+|\s+/\s+")
NEGATION = re.compile("|".join(NEGATION_CUES), re.IGNORECASE)
EJECTION_FRACTION = re.compile(r"\b(?:lv)?ef\b[^0-9;]{0,12}?(\d{1,2}(?:\.\d+)?)")
# Heart failure named by anything other than the EF itself: a preserved EF does not unname it.
HEART_FAILURE_TERMS = {"heart_failure": tuple(p for p in DIAGNOSIS_PHRASES["heart_failure"] if p != "lvef")}
HEART_FAILURE_ABBREVIATIONS = {a: c for a, c in DIAGNOSIS_ABBREVIATIONS.items() if c == "heart_failure"}


@dataclass(frozen=True)
class ConditionMatch:
    """Conditions stated present, conditions stated absent, and the clause behind each."""

    present: frozenset[str]
    negated: frozenset[str]
    evidence: dict[str, str] = field(default_factory=dict)


def clauses(text: str) -> list[str]:
    """Split free text into clauses, the scope of a negation."""
    return [c.strip() for c in CLAUSE_SPLIT.split(text) if c.strip()]


def words(clause: str) -> list[str]:
    """Lowercase words of a clause; hyphens and apostrophes inside a word are dropped
    ("G-6-PD" -> "g6pd", "Parkinson's" -> "parkinsons")."""
    return [re.sub(r"['\-.]", "", w) for w in re.findall(r"[a-z0-9][a-z0-9'\-.]*", clause.lower())]


def _allowed_edits(term: str) -> int:
    """Typos tolerated in a vocabulary word: none up to 4 letters, 1 up to 7, then 2."""
    return 0 if len(term) <= 4 else 1 if len(term) <= 7 else 2


def _word_matches(written: str, term: str) -> bool:
    """True if a written word is the vocabulary word, allowing for its typo budget."""
    if written == term:
        return True
    budget = _allowed_edits(term)
    return budget > 0 and abs(len(written) - len(term)) <= budget and \
        OSA.distance(written, term) <= budget


def _word_is(written: str, term: str) -> bool:
    """True if a written word is the vocabulary word or one of its other forms ("bleeding")."""
    return _word_matches(written, term) or any(_word_matches(written, f) for f in WORD_FORMS.get(term, ()))


def _phrase_in(clause_words: list[str], phrase: str) -> bool:
    """True if the phrase's words appear consecutively in the clause."""
    terms = phrase.split()
    return any(all(_word_is(clause_words[i + k], t) for k, t in enumerate(terms))
               for i in range(len(clause_words) - len(terms) + 1))


def ejection_fraction(clause: str) -> float | None:
    """The ejection fraction a clause states, in percent ("LVEF 30%", "EF of 0.35"), or None."""
    found = EJECTION_FRACTION.search(clause.lower())
    if found is None:
        return None
    value = float(found.group(1))
    return value * 100 if value < 1 else value


def _heart_function(clause: str, clause_words: list[str], named: set[str]) -> set[str]:
    """Adjust a clause's conditions for a stated ejection fraction: below EF_HEART_FAILURE_BELOW it
    names heart failure; at or above it, heart failure stays only if another term names it."""
    ef = ejection_fraction(clause)
    if ef is None:
        return named
    if ef < EF_HEART_FAILURE_BELOW:
        return named | {"heart_failure"}
    if _named(clause_words, HEART_FAILURE_TERMS, HEART_FAILURE_ABBREVIATIONS):
        return named
    return named - {"heart_failure"}


def _named(clause_words: list[str], phrases: Mapping[str, Iterable[str]],
           abbreviations: Mapping[str, str]) -> set[str]:
    """Every condition a clause names."""
    found = {condition for condition, forms in phrases.items()
             if any(_phrase_in(clause_words, phrase) for phrase in forms)}
    found |= {abbreviations[w] for w in clause_words if w in abbreviations}
    return found


def _match(texts: Iterable[str], phrases: Mapping[str, Iterable[str]],
           abbreviations: Mapping[str, str], read_ef: bool = False) -> ConditionMatch:
    """Conditions named in some free texts, split into present and negated."""
    present, negated, evidence = set(), set(), {}
    for text in texts:
        for clause in clauses(text):
            clause_words = words(clause)
            named = _named(clause_words, phrases, abbreviations)
            if read_ef:
                named = _heart_function(clause, clause_words, named)
            if not named:
                continue
            if NEGATION.search(clause):
                negated |= named
            else:
                for condition in named - present:
                    evidence[condition] = clause
                present |= named
    return ConditionMatch(frozenset(present), frozenset(negated - present), evidence)


def detect_conditions(diagnoses: Iterable[str], allergies: str | None) -> ConditionMatch:
    """Conditions from the diagnosis list and the allergy text.

    Diagnosis text yields only diagnosis conditions, allergy text only allergy conditions.
    A condition stated present in one clause and absent in another counts as present.
    """
    from_diagnoses = _match(diagnoses, DIAGNOSIS_PHRASES, DIAGNOSIS_ABBREVIATIONS, read_ef=True)
    from_allergies = _match([allergies] if allergies else [], ALLERGY_PHRASES, ALLERGY_ABBREVIATIONS)
    return ConditionMatch(from_diagnoses.present | from_allergies.present,
                          from_diagnoses.negated | from_allergies.negated,
                          {**from_diagnoses.evidence, **from_allergies.evidence})
