"""Threshold sweep for name resolution, on the dev split only.

    python -m eval.sweep [--docs docs/sweep.md]

Tries every MIN_CONFIDENCE x MIN_MARGIN x MIN_PREFIX_LENGTH in the grid below on the 1,200
dev patients. Each setting's submission is scored by the organisers' ``evaluate.py``; our own
metrics add the false-resolution and abstention rates the scorer does not report. Picks the
setting with the best official primary score whose false-resolution rate is at most
MAX_FALSE_RESOLUTION_RATE (2%). Ties go to fewer false resolutions, then to the stricter
setting. Prints the choice and the same setting's numbers on the holdout split, and writes the
table to docs/sweep.md.

The chosen values are then recorded in src/medsafe/resolve/thresholds.py. Until the rule engine
lands, a false resolution costs only its own line; once alerts exist it can also cost a false
alert, so re-run this sweep after Phase 3 (docs/DECISIONS.md D-016).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from eval import official
from eval.metrics import index_resolutions, resolution_metrics
from eval.pack import ROOT, data_dir, require_pack
from eval.records import Resolution
from eval.run import WORK_DIR, _num, _relative, _table, data_version, git_revision
from eval.split import split_ids
from eval.truth import load_truth, write_truth_subset
from medsafe.data.adapter import Dataset, load_dataset
from medsafe.output.writer import write_predictions, write_resolution
from medsafe.pipeline import Settings, build_resolver, run_pipeline
from medsafe.resolve import thresholds

MIN_CONFIDENCES = (0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.64, 0.68, 0.72)
MIN_MARGINS = (0.00, 0.02, 0.04, 0.05, 0.06, 0.08, 0.10)
MIN_PREFIX_LENGTHS = (4, 5)
DOCS_PATH = ROOT / "docs" / "sweep.md"


def measure(dataset: Dataset, split: str, settings: Settings,
            rank_cache: dict | None = None) -> dict[str, Any]:
    """Official score plus our resolution metrics, for one split at one setting."""
    ids = split_ids((p.patient_id for p in dataset.patients), split)
    subset = replace(dataset, patients=[p for p in dataset.patients if p.patient_id in ids])
    resolver = build_resolver(subset, settings, rank_cache)
    result = run_pipeline(subset, settings, resolver)

    folder = WORK_DIR / "sweep" / split
    labels, truth_resolution = (folder / "truth" / "train_labels.csv",
                                folder / "truth" / "train_resolution.csv")
    if not labels.is_file():
        write_truth_subset(data_dir(), ids, folder / "truth")
    write_resolution(result, folder / "H4_resolution.csv")
    write_predictions([a for p in result.patients for a in p.alerts], folder / "H4_predictions.csv")
    report = official.score(folder / "H4_predictions.csv", folder / "H4_resolution.csv",
                            labels, truth_resolution, folder / "score.json")

    ours = index_resolutions(
        Resolution(r.patient.patient_id, entry.raw, frozenset(res.generics), res.method)
        for r in result.patients for entry, res in zip(r.patient.medications, r.resolutions))
    metrics = resolution_metrics(load_truth(data_dir(), ids).tokens, ours)
    return {**metrics, "primary_score": report["primary_score"],
            "official_resolution_accuracy": report["components"]["resolution_accuracy"]}


def sweep(dataset: Dataset) -> list[dict[str, Any]]:
    """Measure every setting in the grid on the dev split. One row per setting."""
    rank_cache: dict = {}
    rows = []
    for prefix in MIN_PREFIX_LENGTHS:
        for confidence in MIN_CONFIDENCES:
            for margin in MIN_MARGINS:
                settings = Settings(confidence, margin, prefix)
                m = measure(dataset, "dev", settings, rank_cache)
                rows.append({"min_confidence": confidence, "min_margin": margin,
                             "min_prefix_length": prefix, "primary_score": m["primary_score"],
                             "accuracy": m["official_resolution_accuracy"],
                             "false_resolution_rate": m["false_resolution_rate"],
                             "abstention_rate": m["abstention_rate"],
                             "misspelled_accuracy": m["misspelled_accuracy"]})
    return rows


def best(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Best official primary score within the false-resolution limit; ties to fewer false
    resolutions, then the stricter thresholds. Deterministic."""
    allowed = [r for r in rows if r["false_resolution_rate"] <= thresholds.MAX_FALSE_RESOLUTION_RATE]
    return max(allowed, key=lambda r: (round(r["primary_score"], 9),
                                       -round(r["false_resolution_rate"], 9),
                                       r["min_confidence"], r["min_margin"], r["min_prefix_length"]))


def render_markdown(rows: list[dict[str, Any]], chosen: dict[str, Any],
                    holdout: dict[str, Any]) -> str:
    """docs/sweep.md: the choice, its holdout check, and the full grid."""
    def grid(prefix: int, metric: str, digits: int) -> str:
        """One metric as a MIN_CONFIDENCE x MIN_MARGIN table, for one prefix length."""
        return _table([f"MIN_CONFIDENCE \\ MIN_MARGIN (prefix {prefix})",
                       *[f"{m:.2f}" for m in MIN_MARGINS]],
                      [[f"{c:.2f}", *[f"{r[metric]:.{digits}f}" for r in rows
                                      if r["min_confidence"] == c and r["min_prefix_length"] == prefix]]
                       for c in MIN_CONFIDENCES])

    parts = [
        "# Name-resolution threshold sweep",
        f"Generated by `python -m eval.sweep` at `{git_revision()}` (data version "
        f"`{data_version(data_dir())}`). Do not edit by hand. Tuned on the dev split only "
        f"(1,200 patients); the holdout split (300) is reported for the chosen setting and was "
        f"never used to choose it.",
        f"**Chosen: MIN_CONFIDENCE {chosen['min_confidence']:.2f}, MIN_MARGIN "
        f"{chosen['min_margin']:.2f}, MIN_PREFIX_LENGTH {chosen['min_prefix_length']}.** "
        f"The best official primary score whose false-resolution rate is at most "
        f"{thresholds.MAX_FALSE_RESOLUTION_RATE:.0%}.",
        _table(["", "dev (tuned on)", "holdout (unseen)"],
               [[label, _num(chosen[k]), _num(holdout[k])] for label, k in (
                   ("official primary score", "primary_score"),
                   ("resolution accuracy (official)", "accuracy"),
                   ("false-resolution rate", "false_resolution_rate"),
                   ("abstention rate", "abstention_rate"),
                   ("accuracy on misspelled lines", "misspelled_accuracy"))]),
        "With no alerts yet the primary score is 0.15 x resolution accuracy, so today this "
        "sweep maximises resolution accuracy. Until the rule engine lands a false resolution "
        "costs only its own line; once alerts exist it can also raise a false alert, so this "
        "sweep is re-run after Phase 3.",
    ]
    for prefix in MIN_PREFIX_LENGTHS:
        parts += [f"## Official primary score, prefix length {prefix}",
                  grid(prefix, "primary_score", 4),
                  f"## False-resolution rate, prefix length {prefix}",
                  grid(prefix, "false_resolution_rate", 4)]
    return "\n\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point. Returns 0, or 2 if the pack is missing."""
    parser = argparse.ArgumentParser(description="Sweep the name-resolution thresholds.")
    parser.add_argument("--docs", type=Path, default=DOCS_PATH)
    args = parser.parse_args(argv)
    try:
        require_pack()
    except FileNotFoundError as error:
        print(f"cannot sweep: {error}", file=sys.stderr)
        return 2
    dataset = load_dataset(data_dir(), "train")
    rows = sweep(dataset)
    chosen = best(rows)
    measured = measure(dataset, "holdout", Settings(chosen["min_confidence"], chosen["min_margin"],
                                                    chosen["min_prefix_length"]))
    holdout = {**measured, "accuracy": measured["official_resolution_accuracy"]}
    args.docs.write_text(render_markdown(rows, chosen, holdout), encoding="utf-8")
    print(f"chosen: MIN_CONFIDENCE {chosen['min_confidence']:.2f}, MIN_MARGIN "
          f"{chosen['min_margin']:.2f}, MIN_PREFIX_LENGTH {chosen['min_prefix_length']}")
    for label, row in (("dev", chosen), ("holdout", holdout)):
        print(f"  {label:<8} primary {row['primary_score']:.4f}  accuracy {row['accuracy']:.4f}  "
              f"false {row['false_resolution_rate']:.4f}  abstained {row['abstention_rate']:.4f}  "
              f"misspelled {_num(row['misspelled_accuracy'])}")
    print(f"table: {_relative(args.docs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
