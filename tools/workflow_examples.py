"""Finds one real training case for each failure mode docs/WORKFLOW.md names.

    python tools/workflow_examples.py

Every case quoted in docs/WORKFLOW.md comes from this script, so the document never invents an
example. Cases are chosen by the criteria below; the labels only choose which patient is shown
(a seeded near-miss), the pipeline decides what is shown.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from eval.pack import data_dir, require_pack  # noqa: E402
from medsafe.data.adapter import load_dataset  # noqa: E402
from medsafe.explain.prioritise import collapse  # noqa: E402
from medsafe.pipeline import run_pipeline  # noqa: E402


def main() -> int:
    """Print one case per failure mode, with patient ids and the lines as written."""
    require_pack()
    dataset = load_dataset(data_dir(), "train")
    result = {p.patient.patient_id: p for p in run_pipeline(dataset).patients}
    with (data_dir() / "train_labels.csv").open(newline="", encoding="utf-8") as handle:
        near = [r for r in csv.DictReader(handle) if r["near_miss"] == "1"]

    counts = Counter(p.patient.prescriber_count for p in result.values())
    three = [p for p in result.values() if p.patient.prescriber_count == 3]
    serious_three = [p for p in three if any(a["severity"] in ("contraindicated", "major") for a in p.alerts)]
    print(f"1. Walled garden: prescriber_count {dict(sorted(counts.items()))}; "
          f"{len(serious_three)} of {len(three)} three-prescriber patients have a serious alert.")
    p = serious_three[0]
    print(f"   e.g. {p.patient.patient_id}: {len(p.patient.medications)} lines, "
          f"{len(p.alerts)} alerts, e.g. {p.alerts[0]['issue_type']} {p.alerts[0]['drugs_involved']} "
          f"({p.alerts[0]['severity']})")

    def lines_for(patient_id: str, drugs: set[str]) -> list[str]:
        """The patient's lines naming any of ``drugs``: as written, resolved, and their status."""
        return [f"{e.raw!r} -> {';'.join(e.generics)} [{(e.status)}]"
                for e in result[patient_id].rules.regimen.entries if set(e.generics) & drugs]

    for title, wanted in (("2. Brand chaos", "misspelled"), ("3. Hidden combination", "combination")):
        for issue in near:
            drugs = set(issue["drugs_involved"].split(";"))
            entries = [e for e in result[issue["patient_id"]].rules.regimen.entries if set(e.generics) & drugs]
            combos = [e for e in entries if len(e.generics) > 1 and not set(e.generics) <= drugs]
            resolutions = result[issue["patient_id"]].resolutions
            fuzzy = [e for e in entries if resolutions[e.index].method in ("fuzzy", "prefix")]
            if (wanted == "misspelled" and fuzzy and not combos) or (wanted == "combination" and combos):
                print(f"{title}: {issue['patient_id']} {issue['issue_type']} {issue['drugs_involved']} "
                      f"({issue['severity']}): {' | '.join(lines_for(issue['patient_id'], drugs))}")
                break

    by_egfr = sorted(((p.patient.egfr, p) for p in result.values() if p.patient.egfr is not None
                      and "metformin" in p.rules.regimen.generics), key=lambda x: x[0])
    picks = {}
    for egfr, p in by_egfr:
        renal = [f for f in p.findings if f.issue_type == "renal_dose" and f.drugs == ("metformin",)]
        tier = renal[0].severity if renal else "none"
        picks.setdefault(tier, (egfr, p.patient.patient_id))
    print("4. Severity by eGFR, metformin: " + "; ".join(
        f"eGFR {e:g} ({pid}) -> {tier}" for tier, (e, pid) in sorted(picks.items(), key=lambda x: x[1][0])))
    most = max(result.values(), key=lambda p: (sum(f.issue_type == "interaction" for f in p.findings),
                                               p.patient.patient_id))
    pairs = [f for f in most.findings if f.issue_type == "interaction"]
    folded = collapse(most.findings)
    print(f"   Pairwise popups: {most.patient.patient_id} has {len(pairs)} interaction pairs "
          f"({Counter(f.severity for f in pairs)}); collapse: "
          f"{folded.summary if folded else 'no grouping clears more than one serious pair'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
