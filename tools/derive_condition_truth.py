"""Back-derive which conditions each training patient has, from the contraindication labels,
and measure the condition matcher against it.

    python tools/derive_condition_truth.py

The labels never name the condition, but the tables pin it down:

  present  For a label (patient, drug, severity), the table rows for that drug at that severity
           name the conditions that could have produced it. Where exactly one condition is
           possible, that condition was present. (Pregnancy, which comes from the pregnancy
           field and not from text, is counted separately.)
  absent   For a drug on the patient's current regimen, every table row MORE severe than the
           drug's label, or every row if the drug has no contraindication label at all, names a
           condition the patient does not have: had it been present, the label would differ.

Uses the pipeline's regimen (which reproduces every training label exactly) to know which drugs
are current. Reads training data only.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from eval.pack import data_dir, require_pack  # noqa: E402
from eval.truth import load_truth  # noqa: E402
from medsafe.data.adapter import load_dataset  # noqa: E402
from medsafe.pipeline import run_pipeline  # noqa: E402
from medsafe.rules.contraindication import PREGNANCY, PREGNANCY_LETTER_SEVERITY  # noqa: E402
from medsafe.rules.types import SEVERITY_RANK  # noqa: E402


def derive(dataset, issues, result) -> tuple[set, set, Counter]:
    """(present pairs, absent pairs, coverage counts); pairs are (patient_id, condition_id)."""
    rows_by_drug: dict[str, list] = {}
    for row in dataset.contraindications:
        rows_by_drug.setdefault(row.generic, []).append(row)
    labels = {(i.patient_id, next(iter(i.drugs))): i.severity
              for i in issues if i.issue_type == "contraindication"}
    present, absent, coverage = set(), set(), Counter()
    for patient_result in result.patients:
        patient = patient_result.patient
        for drug in patient_result.rules.regimen.generics:
            rows = rows_by_drug.get(drug, [])
            label = labels.get((patient.patient_id, drug))
            if label is not None:
                candidates = {r.condition_id for r in rows if r.severity == label
                              and (r.condition_id != PREGNANCY or patient.pregnant)}
                letter = dataset.drugs[drug].pregnancy_category
                if patient.pregnant and PREGNANCY_LETTER_SEVERITY.get(letter) == label:
                    candidates.add(PREGNANCY)
                if len(candidates) == 1:
                    coverage["unique"] += 1
                    condition = candidates.pop()
                    if condition == PREGNANCY:
                        coverage["unique: pregnancy field"] += 1
                    else:
                        present.add((patient.patient_id, condition))
                else:
                    coverage["ambiguous"] += 1
            for row in rows:
                if row.condition_id != PREGNANCY and (
                        label is None or SEVERITY_RANK[row.severity] > SEVERITY_RANK[label]):
                    absent.add((patient.patient_id, row.condition_id))
    return present, absent - present, coverage


def main() -> int:
    """Print coverage and the matcher's agreement with the derived truth. Exit 1 on any error."""
    require_pack()
    dataset = load_dataset(data_dir(), "train")
    result = run_pipeline(dataset)
    present, absent, coverage = derive(dataset, load_truth(data_dir()).issues, result)
    found = {(p.patient.patient_id, c) for p in result.patients for c in p.rules.conditions.present}

    labels = coverage["unique"] + coverage["ambiguous"]
    print(f"contraindication labels: {labels}")
    print(f"  condition pinned down uniquely: {coverage['unique']} "
          f"({coverage['unique'] / labels:.1%}), of which pregnancy field: "
          f"{coverage['unique: pregnancy field']}")
    print(f"  more than one possible condition: {coverage['ambiguous']}")
    print(f"derived truth: {len(present)} (patient, condition) pairs present, {len(absent)} absent")
    missed = sorted(present - found)
    false = sorted(absent & found)
    print(f"matcher: present found {len(present) - len(missed)}/{len(present)}, "
          f"absent correctly not found {len(absent) - len(false)}/{len(absent)}")
    for label, pairs in (("MISSED", missed), ("FALSE", false)):
        for patient_id, condition in pairs[:10]:
            p = next(r.patient for r in result.patients if r.patient.patient_id == patient_id)
            print(f"  {label} {patient_id} {condition}: dx={list(p.diagnoses)} allergy={p.allergies!r}")
    return 1 if missed or false else 0


if __name__ == "__main__":
    raise SystemExit(main())
