"""What a submission folder holds, next to the training labels' own distribution (R17).

    python run.py --split test --out submission
    python -m eval.submission_summary submission

The test labels are hidden, so the test submission cannot be scored; its shape can be compared
with training's. Prints row counts, patients and lines covered, alerts by issue type and
severity, alerts per patient, and the share of each type and severity next to the training
labels with minor removed (what a perfect no-minor submission on train would hold).
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

from eval.pack import data_dir, require_pack
from eval.validate_submission import raw_tokens
from medsafe.output.writer import PREDICTIONS_FILE, RESOLUTION_FILE

SEVERITIES = ("contraindicated", "major", "moderate", "minor")
ISSUE_TYPES = ("interaction", "duplicate_therapy", "renal_dose", "contraindication")


def rows(path: Path) -> list[dict[str, str]]:
    """A CSV file's rows."""
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def shape(alerts: list[dict[str, str]], patients: int) -> dict[str, object]:
    """Counts and shares by issue type and severity, and alerts per patient with its spread."""
    per = Counter(a["patient_id"] for a in alerts)
    counts = [*per.values(), *[0] * (patients - len(per))]
    mean = len(alerts) / patients
    variance = sum((c - mean) ** 2 for c in counts) / (patients - 1)
    return {"alerts": len(alerts), "per_patient": mean, "se": (variance / patients) ** 0.5,
            "with_alert": len({a["patient_id"] for a in alerts}) / patients,
            "type": Counter(a["issue_type"] for a in alerts),
            "severity": Counter(a["severity"] for a in alerts),
            "cell": Counter((a["issue_type"], a["severity"]) for a in alerts)}


def summarise(folder: Path, split: str = "test") -> list[str]:
    """The summary as printable lines."""
    predictions = rows(folder / PREDICTIONS_FILE)
    resolution = rows(folder / RESOLUTION_FILE)
    tokens = raw_tokens(split)
    covered = {r["patient_id"].upper() for r in resolution}
    ours = shape(predictions, len(tokens))
    train_patients = len(raw_tokens("train"))
    train = shape([r for r in rows(data_dir() / "train_labels.csv") if r["severity"] != "minor"],
                  train_patients)

    out = [f"{PREDICTIONS_FILE}: {len(predictions)} rows; {RESOLUTION_FILE}: {len(resolution)} rows",
           f"patients: {len(tokens)} in the {split} file, {len(covered & set(tokens))} with resolution rows; "
           f"distinct written lines {sum(map(len, tokens.values()))}",
           f"minor alerts in the predictions file: {ours['severity']['minor']}",
           "",
           f"{'':<22}{split:>10}{'share':>8}{'train labels, no minor':>26}{'share':>8}"]
    for label, key, names in (("issue type", "type", ISSUE_TYPES), ("severity", "severity", SEVERITIES)):
        out.append(f"by {label}")
        for name in names:
            a, b = ours[key][name], train[key][name]
            out.append(f"  {name:<20}{a:>10}{a / max(ours['alerts'], 1):>8.1%}{b:>26}{b / max(train['alerts'], 1):>8.1%}")
    out += [f"  {'total':<20}{ours['alerts']:>10}{'':>8}{train['alerts']:>26}",
            f"alerts per patient    {ours['per_patient']:>10.2f}{'':>8}{train['per_patient']:>26.2f}",
            f"  difference {ours['per_patient'] - train['per_patient']:+.3f}, "
            f"{(ours['per_patient'] - train['per_patient']) / (ours['se'] ** 2 + train['se'] ** 2) ** 0.5:+.2f} "
            f"standard errors (sampling noise alone gives within +-2 about 95% of the time)",
            f"patients with alerts  {ours['with_alert']:>10.1%}{'':>8}{train['with_alert']:>26.1%}",
            "",
            "issue type x severity (" + split + " / train labels, no minor)"]
    for issue in ISSUE_TYPES:
        out.append(f"  {issue:<20}" + "".join(
            f"{s[:6]:>8} {ours['cell'][(issue, s)]:>5}/{train['cell'][(issue, s)]:<5}" for s in SEVERITIES[:3]))
    return out


def main(argv: list[str] | None = None) -> int:
    """Print the summary. Returns 0, or 2 if the pack is missing."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--split", choices=("train", "test"), default="test")
    args = parser.parse_args(argv)
    try:
        require_pack()
    except FileNotFoundError as error:
        print(f"cannot summarise: {error}", file=sys.stderr)
        return 2
    print("\n".join(summarise(args.folder, args.split)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
