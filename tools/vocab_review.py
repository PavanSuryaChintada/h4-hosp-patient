"""Every term in condition_terms.py, how often it fires, and whether training truth backs it (U2).

    python tools/vocab_review.py                          # print the review
    python tools/vocab_review.py --write docs/vocabulary-review.md

For each term, grouped by condition_id:

  train patients   training patients with a clause where the term fires (stated present), and
                   where it appears negated ("no h/o asthma")
  test patients    the same count on test, numbers only: a drift check, never a source of terms
  R7               the back-derived condition truth (tools/derive_condition_truth.py):
                     proven-present   the term fires on a patient the labels prove HAS it
                     proven-absent    the term fires on a patient the labels prove does NOT have
                                      it: a false alert in waiting. Should never appear.
                     unvalidated      neither: no patient carrying it was on a drug whose label
                                      would show the condition
  FLAG             fires on more than 5% of training or test patients: too common to be a
                   contraindication, more likely matching something else
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tools")]

from derive_condition_truth import derive  # noqa: E402
from eval.pack import data_dir, require_pack  # noqa: E402
from eval.truth import load_truth  # noqa: E402
from medsafe.data.adapter import load_dataset  # noqa: E402
from medsafe.pipeline import run_pipeline  # noqa: E402
from medsafe.rules import conditions  # noqa: E402
from medsafe.rules.condition_terms import (ALLERGY_ABBREVIATIONS, ALLERGY_PHRASES,  # noqa: E402
                                           DIAGNOSIS_ABBREVIATIONS, DIAGNOSIS_PHRASES)

FLAG_SHARE = 0.05
EF_TERM = "EF below 50% (number)"


def terms() -> list[tuple[str, str, str]]:
    """(condition_id, term, source) for every phrase, abbreviation and the EF number."""
    rows = []
    for source, phrases, abbreviations in (("diagnosis", DIAGNOSIS_PHRASES, DIAGNOSIS_ABBREVIATIONS),
                                           ("allergy", ALLERGY_PHRASES, ALLERGY_ABBREVIATIONS)):
        for condition, forms in phrases.items():
            rows += [(condition, phrase, source) for phrase in forms]
        rows += [(condition, abbreviation, source) for abbreviation, condition in abbreviations.items()]
    return [*rows, ("heart_failure", EF_TERM, "diagnosis")]


def fires(term: str, condition: str, clause: str) -> bool:
    """True if ``term`` matches the clause and the matcher's answer for the clause keeps
    ``condition`` (so "LVEF 60%" does not count for "lvef")."""
    clause_words = conditions.words(clause)
    if term == EF_TERM:
        ef = conditions.ejection_fraction(clause)
        return ef is not None and ef < conditions.EF_HEART_FAILURE_BELOW
    matched = term in clause_words if " " not in term and (
        term in DIAGNOSIS_ABBREVIATIONS or term in ALLERGY_ABBREVIATIONS) else conditions._phrase_in(clause_words, term)
    if not matched:
        return False
    if condition != "heart_failure":
        return True
    named = conditions._named(clause_words, DIAGNOSIS_PHRASES, DIAGNOSIS_ABBREVIATIONS)
    return condition in conditions._heart_function(clause, clause_words, named)


def carriers(dataset) -> dict[tuple[str, str], tuple[set[str], set[str]]]:
    """(condition, term) -> (patients where it fires stated present, patients where negated)."""
    found: dict[tuple[str, str], tuple[set[str], set[str]]] = defaultdict(lambda: (set(), set()))
    all_terms = terms()
    for patient in dataset.patients:
        texts = {"diagnosis": list(patient.diagnoses), "allergy": [patient.allergies] if patient.allergies else []}
        for source, items in texts.items():
            for text in items:
                for clause in conditions.clauses(text):
                    negated = bool(conditions.NEGATION.search(clause))
                    for condition, term, term_source in all_terms:
                        if term_source == source and fires(term, condition, clause):
                            found[(condition, term)][negated].add(patient.patient_id)
    return found


def review() -> tuple[list[str], int]:
    """The review as markdown lines, and the number of terms proven absent or flagged."""
    require_pack()
    train = load_dataset(data_dir(), "train")
    test = load_dataset(data_dir(), "test")
    present, absent, _ = derive(train, load_truth(data_dir()).issues, run_pipeline(train))
    on_train, on_test = carriers(train), carriers(test)
    n_train, n_test = len(train.patients), len(test.patients)

    lines = [f"| condition | term | train fires (negated) | test fires | R7 | flag |",
             "|---|---|---:|---:|---|---|"]
    problems = 0
    for condition, term, _ in terms():
        fired, negated = on_train[(condition, term)]
        test_fired = on_test[(condition, term)][0]
        proven_present = {p for p in fired if (p, condition) in present}
        proven_absent = {p for p in fired if (p, condition) in absent}
        status = (f"proven-absent ({len(proven_absent)})" if proven_absent
                  else f"proven-present ({len(proven_present)})" if proven_present else "unvalidated")
        share = max(len(fired) / n_train, len(test_fired) / n_test)
        flag = f"FLAG {share:.1%}" if share > FLAG_SHARE else ""
        problems += bool(proven_absent or flag)
        lines.append(f"| {condition} | {term} | {len(fired)} ({len(negated)}) | {len(test_fired)} | {status} | {flag} |")
    total = len(terms())
    unvalidated = sum("unvalidated" in line for line in lines)
    head = [f"# Vocabulary review", "",
            f"Generated by `python tools/vocab_review.py --write docs/vocabulary-review.md`. "
            f"{n_train} training and {n_test} test patients; test is counted, never read for terms.", "",
            f"{total} terms: {sum('proven-present' in l for l in lines)} proven present, "
            f"{sum('proven-absent' in l for l in lines)} proven absent, {unvalidated} unvalidated; "
            f"{sum('FLAG' in l for l in lines)} fire on more than {FLAG_SHARE:.0%} of patients.", ""]
    return head + lines, problems


def main(argv: list[str] | None = None) -> int:
    """Print or write the review. Exit 1 if any term is proven absent or flagged."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", type=Path, help="also write the markdown here")
    args = parser.parse_args(argv)
    lines, problems = review()
    text = "\n".join(lines) + "\n"
    print(text)
    if args.write:
        args.write.write_text(text, encoding="utf-8")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
