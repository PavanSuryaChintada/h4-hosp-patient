"""Check that every training label's severity is the reference tables' severity, unchanged.

    python tools/verify_label_severity.py

Evidence for docs/DECISIONS.md D-015: the submission must carry table severity verbatim,
because graded recall rewards the exact severity and the labels never re-score by patient
context. For each issue type this recomputes the severity the tables give and compares:

    interaction        interactions.csv severity for the pair
    renal_dose         most restrictive renal_rules.csv tier the patient's eGFR is below
    duplicate_therapy  the duplicate group's severity; no group -> moderate; paracetamol -> major
    contraindication   one of the drug's drug_disease_contraindications.csv severities, or the
                       pregnancy letter (X -> contraindicated, D -> major) for a pregnant patient
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from eval.pack import data_dir, require_pack  # noqa: E402
from eval.truth import load_truth  # noqa: E402
from medsafe.data.adapter import load_dataset  # noqa: E402

RANK = {"contraindicated": 3, "major": 2, "moderate": 1, "minor": 0}
PREGNANCY_LETTER = {"X": "contraindicated", "D": "major"}


def main() -> int:
    """Print, per issue type, how many labels equal the table severity. Exit 1 on any mismatch."""
    require_pack()
    dataset = load_dataset(data_dir(), "train")
    truth = load_truth(data_dir())
    patients = {p.patient_id: p for p in dataset.patients}
    pairs = {frozenset((i.drug_a, i.drug_b)): i.severity for i in dataset.interactions}
    tiers = defaultdict(list)
    for rule in dataset.renal_rules:
        tiers[rule.generic].append(rule)
    contra = defaultdict(set)
    for row in dataset.contraindications:
        contra[row.generic].add(row.severity)

    outcome: dict[str, Counter] = defaultdict(Counter)
    mismatches = []
    for issue in truth.issues:
        drugs = sorted(issue.drugs)
        patient = patients[issue.patient_id]
        if issue.issue_type == "interaction":
            expected = {pairs.get(frozenset(drugs))}
            how = "pair severity"
        elif issue.issue_type == "renal_dose":
            applicable = [r for r in tiers[drugs[0]] if patient.egfr is not None
                          and r.egfr_below is not None and patient.egfr < r.egfr_below]
            expected = {min(applicable, key=lambda r: r.egfr_below).severity} if applicable else set()
            how = "most restrictive tier"
        elif issue.issue_type == "duplicate_therapy":
            if "paracetamol" in drugs:
                expected, how = {"major"}, "paracetamol override"
            else:
                groups = {dataset.drugs[d].duplicate_group for d in drugs}
                group = groups.pop() if len(groups) == 1 else None
                if group in dataset.duplicate_groups:
                    expected, how = {dataset.duplicate_groups[group].severity}, "group severity"
                else:
                    expected, how = {"moderate"}, "no group -> moderate"
        else:
            expected = set(contra[drugs[0]])
            letter = dataset.drugs[drugs[0]].pregnancy_category
            if patient.pregnant and letter in PREGNANCY_LETTER:
                expected.add(PREGNANCY_LETTER[letter])
            how = ("single candidate" if len(expected) == 1 else "one of several candidates")
        ok = issue.severity in expected
        outcome[issue.issue_type]["labels"] += 1
        outcome[issue.issue_type]["match"] += ok
        outcome[issue.issue_type][how] += 1
        if not ok:
            mismatches.append((issue.issue_type, issue.patient_id, drugs, issue.severity, expected))

    print(f"{'issue type':<20}{'labels':>8}{'match':>8}  how the table severity was found")
    for issue_type in ("interaction", "renal_dose", "duplicate_therapy", "contraindication"):
        c = outcome[issue_type]
        detail = ", ".join(f"{k} {v}" for k, v in sorted(c.items()) if k not in ("labels", "match"))
        print(f"{issue_type:<20}{c['labels']:>8}{c['match']:>8}  {detail}")
    for mismatch in mismatches[:20]:
        print("  MISMATCH", mismatch)
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
