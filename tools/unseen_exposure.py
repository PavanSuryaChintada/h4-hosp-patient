"""How exposed is the test score to text the vocabulary has never seen? (U1)

    python tools/unseen_exposure.py --counts-only     # numbers only, no test text shown
    python tools/unseen_exposure.py                   # also the top unmatched fragments

Measures, never tunes. docs/DECISIONS.md D-027: the vocabulary was broadened from training
morphology and frozen BEFORE this script's list was ever printed; adding a term because it
appears here would let test text shape the rules, which D-024 and the pack's rule against
labelling test patients forbid.

  diagnoses   test fragments (split on ';') that never occur in train; of those, the ones the
              matcher finds no condition in (present or negated); of those, the ones belonging
              to a patient on a drug with a contraindication row for a diagnosis condition.
              Only these can cost score: the true exposure. Each at-risk fragment is then set
              against its nearest train fragment (at most 2 edits away, OSA):
                typo of a no-condition train fragment   "dyslipidmeia" ~ "dyslipidemia"
                typo of a condition train fragment      a real miss: the typo budget fell short
                novel                                   no train fragment that close
  allergies   the same for allergy text, against drugs with an allergy row.
  stopped     active lines containing a status-like word the stopped markers do not catch, how
              many are the training form "(old Rx)" (active in training truth), and active lines
              with a word 1-2 edits from a stop marker (a misspelt "stopped").
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from rapidfuzz import process  # noqa: E402
from rapidfuzz.distance import OSA  # noqa: E402

from eval.pack import data_dir, require_pack  # noqa: E402
from medsafe.data.adapter import load_dataset  # noqa: E402
from medsafe.pipeline import run_pipeline  # noqa: E402
from medsafe.rules.conditions import detect_conditions  # noqa: E402

NO_ALLERGY = re.compile(r"^\s*(nkda|nka|nil|none|no known( drug)? allerg\w*|no drug allerg\w*)\s*$",
                        re.IGNORECASE)
# Words that can mark a line as no longer current, fixed before any test line was read.
STATUS_WORDS = re.compile(r"\b(old|previous|previously|earlier|past|was|had|took|trial|ceased|"
                          r"paused|suspended|off|finished|completed|tapered|tapering|skip\w*|"
                          r"until|till|earlier rx|not now)\b", re.IGNORECASE)
OLD_RX = re.compile(r"\(old rx\)", re.IGNORECASE)
STOP_MARKERS = ("stopped", "discontinued", "withdrawn", "omitted", "taking", "longer")
TYPO_EDITS = 2


def fragment_key(text: str) -> str:
    """A diagnosis fragment compared case- and space-insensitively."""
    return " ".join(text.lower().split())


def nearest_train(key: str, train_keys: list[str]) -> str | None:
    """The train fragment at most TYPO_EDITS edits from ``key``, or None."""
    found = process.extractOne(key, train_keys, scorer=OSA.distance, score_cutoff=TYPO_EDITS)
    return found[0] if found else None


def misspelt_stop(raw: str) -> bool:
    """True if a line has a word 1-2 edits from a stop marker but not the marker itself."""
    return any(w != m and len(w) >= 5 and OSA.distance(w, m) <= (1 if len(m) <= 7 else 2)
               for w in re.findall(r"[a-z/]+", raw.lower()) for m in STOP_MARKERS)


def main(argv: list[str] | None = None) -> int:
    """Print the exposure counts, and unless --counts-only the top unmatched entries."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--counts-only", action="store_true", help="numbers only, no test text")
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args(argv)
    require_pack()

    train = load_dataset(data_dir(), "train")
    test = load_dataset(data_dir(), "test")
    rows_by_drug: dict[str, set[str]] = {}
    for row in test.contraindications:
        rows_by_drug.setdefault(row.generic, set()).add(row.condition_id)
    kind = {c.condition_id: c.kind for c in test.conditions.values()}
    diagnosis_drugs = {d for d, cs in rows_by_drug.items() if any(kind.get(c) == "diagnosis" for c in cs)}
    allergy_drugs = {d for d, cs in rows_by_drug.items() if any(kind.get(c) == "allergy" for c in cs)}

    seen = {fragment_key(f) for p in train.patients for f in p.diagnoses}
    seen_allergy = {fragment_key(p.allergies) for p in train.patients if p.allergies}
    results = run_pipeline(test).patients

    unseen, unmatched, at_risk = set(), set(), Counter()
    a_unseen, a_unmatched, a_risk = set(), set(), Counter()
    status, old_rx, misspelt = Counter(), 0, 0
    for result in results:
        patient, regimen = result.patient, result.rules.regimen
        on_diagnosis_drug = bool(set(regimen.generics) & diagnosis_drugs)
        for fragment in patient.diagnoses:
            key = fragment_key(fragment)
            if key in seen:
                continue
            unseen.add(key)
            found = detect_conditions([fragment], None)
            if not (found.present or found.negated):
                unmatched.add(key)
                if on_diagnosis_drug:
                    at_risk[key] += 1
        if patient.allergies and fragment_key(patient.allergies) not in seen_allergy:
            key = fragment_key(patient.allergies)
            a_unseen.add(key)
            found = detect_conditions([], patient.allergies)
            if not (found.present or found.negated) and not NO_ALLERGY.match(patient.allergies):
                a_unmatched.add(key)
                if set(regimen.generics) & allergy_drugs:
                    a_risk[key] += 1
        for entry in regimen.entries:
            if entry.status == "active" and STATUS_WORDS.search(entry.raw):
                status[STATUS_WORDS.search(entry.raw).group(0).lower()] += 1
                old_rx += bool(OLD_RX.search(entry.raw))
            misspelt += entry.status == "active" and misspelt_stop(entry.raw)

    train_keys = sorted(seen)
    named = {k: bool(detect_conditions([k], None).present | detect_conditions([k], None).negated)
             for k in train_keys}
    kinds: dict[str, str] = {}
    for key in at_risk:
        near = nearest_train(key, train_keys)
        kinds[key] = "novel" if near is None else "miss" if named[near] else "typo"
    by_kind = Counter(kinds.values())
    weight = Counter()
    for key, kind in kinds.items():
        weight[kind] += at_risk[key]
    short = sorted(k for k in at_risk if len(k) <= 5)

    def conditions_of(key: str) -> tuple[frozenset[str], frozenset[str]]:
        """The conditions a fragment names, present and negated."""
        found = detect_conditions([key], None)
        return found.present, found.negated

    agreement, unsure = Counter(), []
    for key in sorted(unseen - unmatched):
        near = nearest_train(key, train_keys)
        kind = "novel" if near is None else "agrees" if conditions_of(near) == conditions_of(key) else "differs"
        agreement[kind] += 1
        if kind != "agrees":
            unsure.append(f"  {kind:<7} {key!r} -> present {sorted(conditions_of(key)[0])}, negated "
                          f"{sorted(conditions_of(key)[1])}; nearest train {near!r}")

    print(f"diagnoses: {len(unseen)} test fragments never seen in train; {len(unmatched)} with no "
          f"condition found; {len(at_risk)} of those on a patient taking a drug with a diagnosis "
          f"contraindication row ({sum(at_risk.values())} patient-fragments) <- exposure")
    print(f"  of the {len(at_risk)}: typo of a no-condition train fragment {by_kind['typo']} "
          f"({weight['typo']}); typo of a condition train fragment {by_kind['miss']} "
          f"({weight['miss']}) <- real misses; novel {by_kind['novel']} ({weight['novel']}); "
          f"{len(short)} are 5 characters or fewer, where 2 edits is loose: {short}")
    print(f"  the {len(unseen - unmatched)} unseen fragments that DID name a condition, against their "
          f"nearest train fragment: same conditions {agreement['agrees']}, different "
          f"{agreement['differs']} <- possible false alerts, novel {agreement['novel']}")
    print(f"allergies: {len(a_unseen)} unseen allergy texts; {len(a_unmatched)} unmatched and not a "
          f"no-allergy statement; {len(a_risk)} on a patient taking a drug with an allergy row")
    print(f"stopped: {sum(status.values())} active lines carry a status-like word the stopped "
          f"markers do not catch: {dict(status.most_common())}; {old_rx} are the training form "
          f"'(old Rx)'; {misspelt} active lines have a misspelt stop marker")
    if not args.counts_only:
        print(f"\nTop {args.top} unmatched unseen diagnosis fragments by at-risk patients:")
        for key, count in sorted(at_risk.items(), key=lambda kv: (kinds[kv[0]] == "typo", -kv[1], kv[0]))[:args.top]:
            print(f"  {count:>3}  {kinds[key]:<5}  {key}")
        print("\nUnseen fragments that name a condition their nearest train fragment does not:")
        print("\n".join(unsure))
        print("\nUnmatched unseen allergy texts at risk:")
        for key, count in a_risk.most_common(args.top):
            print(f"  {count:>3}  {key}")
        print("\nActive lines with a status-like word (first 30):")
        shown = 0
        for result in results:
            for entry in result.rules.regimen.entries:
                if entry.status == "active" and STATUS_WORDS.search(entry.raw) and shown < 30:
                    print(f"  {result.patient.patient_id}  {entry.raw}")
                    shown += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
