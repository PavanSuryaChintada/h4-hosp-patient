"""Evaluation harness: run the pipeline on the training patients and score it officially.

    python -m eval.run [--compare eval/reports/<earlier>.json] [--no-docs]

For the dev split (1,200 patients, everything is tuned on it) and the holdout split (300
patients, never tuned on), this runs the pipeline, writes the two submission files, and scores
them with the organisers' ``evaluate.py``. It adds what the scorer does not report: false-
resolution and abstention rates, and every near-miss with the stage where it was lost. It writes
``eval/reports/<timestamp>-<git_sha>.json`` and regenerates ``docs/evaluation.md``.

With ``--compare``, exits 1 if the holdout primary score or serious-issue recall dropped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval import official
from eval.baselines import score_references
from eval.metrics import caught, index_resolutions, resolution_metrics, rule_fidelity
from eval.pack import ROOT, data_dir, require_pack
from eval.records import TruthToken
from eval.split import split_ids
from eval.trace import diagnose, traces_from
from eval.truth import load_truth, write_truth_subset
from medsafe.data.adapter import Dataset, load_dataset
from medsafe.output.writer import (PREDICTIONS_FILE, RESOLUTION_FILE, write_predictions,
                                   write_resolution)
from medsafe.pipeline import STAGES, Settings, run_pipeline

WORK_DIR = ROOT / "eval" / "work"
REPORTS_DIR = ROOT / "eval" / "reports"
DOCS_PATH = ROOT / "docs" / "evaluation.md"
REPORTED_SPLITS = ("dev", "holdout")


def evaluate_split(dataset: Dataset, split: str, settings: Settings = Settings(), *,
                   work_dir: Path = WORK_DIR, with_baselines: bool = True) -> dict[str, Any]:
    """Run the pipeline on one split of the training patients and score it.

    Args:
        dataset: The training patients and reference tables (``load_dataset(..., "train")``).
        split: ``dev``, ``holdout`` or ``train``.
        settings: Pipeline thresholds.
        work_dir: Where submission and truth files for the scorer are written.
        with_baselines: Also score the reference submissions (oracle, flag nothing).

    Returns:
        The official report, our resolution metrics, and the near-miss table for the split.
    """
    ids = split_ids((p.patient_id for p in dataset.patients), split)
    subset = replace(dataset, patients=[p for p in dataset.patients if p.patient_id in ids])
    result = run_pipeline(subset, settings)
    traces = traces_from(result)

    folder = work_dir / split
    write_resolution(result, folder / "submission" / RESOLUTION_FILE)
    write_predictions([a for p in result.patients for a in p.alerts],
                      folder / "submission" / PREDICTIONS_FILE)
    labels, truth_resolution = write_truth_subset(data_dir(), ids, folder / "truth")
    report = official.score(folder / "submission" / PREDICTIONS_FILE,
                            folder / "submission" / RESOLUTION_FILE, labels, truth_resolution,
                            folder / "score.json")

    truth = load_truth(data_dir(), ids)
    ours = index_resolutions(r for t in traces.values() for r in (t.resolutions or ()))
    tokens_by_patient: dict[str, list[TruthToken]] = {}
    for token in truth.tokens:
        tokens_by_patient.setdefault(token.patient_id, []).append(token)

    shipped = [a for t in traces.values() for a in (t.shipped or ())]
    near_misses = []
    for issue, hit in zip([i for i in truth.issues if i.near_miss],
                          caught([i for i in truth.issues if i.near_miss], shipped)):
        lines = [t for t in tokens_by_patient.get(issue.patient_id, [])
                 if t.generics & issue.drugs]
        reason = "caught" if hit else diagnose(issue, traces.get(issue.patient_id), lines)
        near_misses.append({
            "patient_id": issue.patient_id, "issue_type": issue.issue_type,
            "severity": issue.severity, "drugs": " + ".join(sorted(issue.drugs)),
            "as_written": " | ".join(t.written_token for t in lines),
            "caught": hit,
            "drugs_resolved": hit or reason.startswith("every drug resolved")
                              or not reason.startswith(("'", "patient", "name")),
            "status": reason,
        })
    near_misses.sort(key=lambda n: (n["caught"], n["patient_id"], n["drugs"]))

    findings = [f for t in traces.values() for f in (t.findings or ())]
    return {
        "split": split,
        "patients": len(ids),
        "stages_built": list(result.stages_built),
        "official": report,
        "rules": rule_fidelity(truth.issues, findings),
        "resolution": resolution_metrics(truth.tokens, ours),
        "near_misses": near_misses,
        "baselines": (score_references(data_dir(), ids, labels, truth_resolution,
                                       folder / "references") if with_baselines else {}),
    }


def data_version(folder: Path) -> str:
    """Short content hash of every CSV in the pack's data folder: names and bytes."""
    digest = hashlib.sha256()
    for path in sorted(folder.glob("*.csv")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


# The clinician-only layer is excluded: tests/test_compliance.py proves Track A's files are
# byte-identical without it, so it cannot change a number.
CODE_PATHS = ("run.py", "src", "eval", "tools", "requirements.txt", "requirements-dev.txt",
              ":(exclude)src/medsafe/workflow.py", ":(exclude)src/medsafe/explain/prioritise.py")


def git_revision() -> str:
    """Short git sha, with ``-dirty`` if tracked code that produces numbers has uncommitted
    changes. Generated reports and untracked files do not count: the question is whether the
    code behind a number is the committed code."""
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, check=True,
                             capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no", "--",
                                *CODE_PATHS], cwd=ROOT, check=True,
                               capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{sha}-dirty" if dirty else sha


def build_report(splits: dict[str, dict[str, Any]], settings: Settings,
                 generated_at: datetime) -> dict[str, Any]:
    """The JSON report: provenance, every threshold, and every split's results."""
    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "git_revision": git_revision(),
        "data_version": data_version(data_dir()),
        "settings": asdict(settings),
        "splits": splits,
    }


def write_report(report: dict[str, Any], reports_dir: Path = REPORTS_DIR) -> Path:
    """Write ``report`` to ``<reports_dir>/<timestamp>-<git_revision>.json``. Returns the path."""
    stamp = datetime.fromisoformat(report["generated_at"]).strftime("%Y%m%dT%H%M%SZ")
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{stamp}-{report['git_revision']}.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return path


def compare(report: dict[str, Any], previous: dict[str, Any]) -> tuple[bool, str]:
    """Regression gate on the holdout split. Returns (ok, message)."""
    messages, ok = [], True
    for name in ("primary_score", "serious_recall"):
        def value(r: dict[str, Any]) -> float:
            """The metric ``name`` on the holdout split of report ``r``."""
            official_report = r["splits"]["holdout"]["official"]
            return official_report.get(name, official_report["components"].get(name, 0.0))
        before, now = value(previous), value(report)
        if now < before - 1e-9:
            ok = False
            messages.append(f"REGRESSION: holdout {name} {before:.4f} -> {now:.4f}")
        else:
            messages.append(f"ok: holdout {name} {before:.4f} -> {now:.4f}")
    return ok, "\n".join(messages)


def _num(value: float | None, digits: int = 4) -> str:
    """Format a metric; None means not measurable."""
    return "n/a" if value is None else f"{value:.{digits}f}"


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """A Markdown table."""
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def _relative(path: Path) -> str:
    """A path relative to the repo root, with forward slashes."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def render_markdown(report: dict[str, Any], report_path: str) -> str:
    """docs/evaluation.md, generated from one report."""
    splits = report["splits"]
    names = [s for s in REPORTED_SPLITS if s in splits]
    components = ("serious_recall", "near_miss_serious_recall", "precision_all",
                  "graded_recall_non_minor", "resolution_accuracy", "base_score",
                  "noise_alerts_per_patient", "alert_fatigue_multiplier")
    built = splits[names[0]]["stages_built"]
    parts = [
        "# Evaluation",
        f"Generated by `python -m eval.run` from `{report_path}` at `{report['git_revision']}`, "
        f"data version `{report['data_version']}`. Do not edit by hand. Every score here is "
        f"computed by the organisers' unmodified `evaluate.py`.",
        f"Stages built: {', '.join(built)}"
        + (f". Not yet built: {', '.join(s for s in STAGES if s not in built)}."
           if set(STAGES) - set(built) else ". The pack baseline (the floor) scores 0.4071 on "
           "all training patients (docs/baseline-floor.md)."),
        "## The two figures the pack asks for by name",
        _table(["", *[f"{n} ({splits[n]['patients']} patients)" for n in names]],
               [["**Near-miss recall**",
                 *[f"**{sum(x['caught'] for x in splits[n]['near_misses'])} / "
                   f"{len(splits[n]['near_misses'])}** "
                   f"({splits[n]['official']['components']['near_miss_serious_recall']:.4f})"
                   for n in names]],
                ["**Resolution accuracy on misspelled entries**",
                 *[f"**{splits[n]['official']['resolution_accuracy_misspelled']:.2%}**"
                   for n in names]]]),
        "Both read from the organisers' `evaluate.py` output: its `NEAR-MISS recall` line and its "
        "`...on misspelled entries` line.",
        "## Official score",
        _table(["", *[f"{n} ({splits[n]['patients']} patients)" for n in names]],
               [["**primary score**", *[f"**{splits[n]['official']['primary_score']:.4f}**"
                                        for n in names]]]
               + [[c, *[_num(splits[n]["official"]["components"][c]) for n in names]]
                  for c in components]),
        "## Name resolution",
        "Correct means the exact set of generics; an empty set is correct for a non-medicine "
        "line. A false resolution names the wrong drug and can raise a confidently wrong alert; "
        "an abstention names nothing and is flagged for manual check.",
        _table(["", *names],
               [[label, *[_num(splits[n]["resolution"][k]) for n in names]] for label, k in (
                   ("accuracy", "accuracy"), ("false-resolution rate", "false_resolution_rate"),
                   ("abstention rate", "abstention_rate"),
                   ("accuracy on misspelled lines", "misspelled_accuracy"))]),
        "### By token kind (" + names[-1] + ")",
        _table(["Kind", "Lines", "Accuracy", "False", "Abstained"],
               [[k, v["lines"], f"{v['accuracy']:.3f}", v["false"], v["abstained"]]
                for k, v in splits[names[-1]]["resolution"]["by_token_kind"].items()]),
    ]

    parts += ["## Rules, one family at a time",
              "Every finding, minor included, against every label. A missed or false case is a "
              "rule bug with a reproducible patient id, not model error: the labels are "
              "deterministic and the tables authoritative."]
    for name in names:
        rules = splits[name]["rules"]
        parts += [f"### {name}",
                  _table(["Issue type", "True", "Ours", "Matched", "Missed", "False",
                          "Wrong severity", "First missed", "First false"],
                         [[t, r["true"], r["ours"], r["matched"], r["missed"], r["false"],
                           r["wrong_severity"], "; ".join(r["first_missed"]) or "-",
                           "; ".join(r["first_false"]) or "-"] for t, r in rules.items()])]

    all_near = [n for name in names for n in splits[name]["near_misses"]]
    caught_count = sum(n["caught"] for n in all_near)
    parts += [
        "## Near-misses",
        f"{len(all_near)} seeded near-misses across {' and '.join(names)}: **{caught_count} of "
        f"{len(all_near)} caught.** Every one resolves, so a miss here would be a rule bug.",
    ]
    missed = [n for n in all_near if not n["caught"]]
    parts.append(_table(["Patient", "Issue", "Severity", "Drugs", "As written", "Why missed"],
                        [[n["patient_id"], n["issue_type"], n["severity"], n["drugs"],
                          n["as_written"], n["status"]] for n in missed])
                 if missed else "None missed.")

    holdout = splits.get("holdout", splits[names[-1]])
    if holdout["baselines"]:
        parts += [
            "## Floor, ceiling and calibration (holdout)",
            "Reference submissions on the same patients, scored by the same official scorer "
            "(eval/baselines.py). The pack baseline is the floor. Minor alerts drive alert "
            "fatigue, fatigue drives dismissal, and dismissal buries the serious alert, so they "
            "are shown to the clinician but never submitted; the scorer agrees, charging 0.25 "
            "noise units for each, which is why even a perfect detector that reports them scores "
            "below 1.0. Full-train figures: docs/baseline-floor.md.",
            _table(["Reference", "Primary score", "Serious recall", "Precision",
                    "Noise per patient"],
                   [[name, f"{b['primary_score']:.4f}",
                     _num(b["components"]["serious_recall"]),
                     _num(b["components"]["precision_all"]),
                     _num(b["components"]["noise_alerts_per_patient"])]
                    for name, b in holdout["baselines"].items()]),
        ]
    parts += [
        "## What these numbers measure",
        "The labels were produced by the organisers' deterministic rule engine running the "
        "published reference tables on each patient's true regimen; the hidden test labels "
        "come from the same engine. Our rule engine (Phase 3) implements those same published "
        "rules. So a training score measures whether name resolution, list parsing and our "
        "implementation of the published rules are right. It does not measure whether the rules "
        "are clinically right: the labeller and the detector share them by design. Expect the "
        "test score to differ where the test lists are written differently, not where the rules "
        "differ.",
        "## Reproduce",
        "```\npip install -r requirements.txt -r requirements-dev.txt\npython -m eval.sweep\n"
        "python -m eval.run\n```",
    ]
    return "\n\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point. Returns 0 ok, 1 regression, 2 pack or scorer missing."""
    parser = argparse.ArgumentParser(description="Score the pipeline on the training patients.")
    parser.add_argument("--no-docs", action="store_true", help="do not regenerate the docs")
    parser.add_argument("--no-baselines", action="store_true", help="skip reference submissions")
    parser.add_argument("--compare", type=Path, help="earlier report; exit 1 on a drop")
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--docs", type=Path, default=DOCS_PATH)
    args = parser.parse_args(argv)
    try:
        require_pack()
        dataset = load_dataset(data_dir(), "train")
        settings = Settings()
        splits = {name: evaluate_split(dataset, name, settings,
                                       with_baselines=not args.no_baselines and name == "holdout")
                  for name in REPORTED_SPLITS}
    except (FileNotFoundError, official.OfficialScorerError) as error:
        print(f"cannot evaluate: {error}", file=sys.stderr)
        return 2

    report = build_report(splits, settings, datetime.now(timezone.utc))
    path = write_report(report, args.reports_dir)
    if not args.no_docs:
        args.docs.write_text(render_markdown(report, _relative(path)), encoding="utf-8")

    for name in REPORTED_SPLITS:
        s = splits[name]
        c = s["official"]["components"]
        print(f"{name:<8} primary {s['official']['primary_score']:.4f}  serious {c['serious_recall']:.4f}"
              f"  near-miss {c['near_miss_serious_recall']:.4f}  precision {c['precision_all']:.4f}"
              f"  graded {c['graded_recall_non_minor']:.4f}  resolution {c['resolution_accuracy']:.4f}"
              f"  noise {c['noise_alerts_per_patient']:.4f}  multiplier {c['alert_fatigue_multiplier']:.4f}")
        for issue_type, r in s["rules"].items():
            print(f"         {issue_type:<18} true {r['true']:<5} ours {r['ours']:<5} matched "
                  f"{r['matched']:<5} missed {r['missed']:<3} false {r['false']:<3} "
                  f"wrong severity {r['wrong_severity']}")
        missed = [n for n in s["near_misses"] if not n["caught"]]
        print(f"         near-misses caught {len(s['near_misses']) - len(missed)}/{len(s['near_misses'])}"
              + "".join(f"\n           MISSED {n['patient_id']} {n['drugs']}: {n['status']}" for n in missed))
    print(f"report: {_relative(path)}")
    if args.compare:
        ok, message = compare(report, json.loads(args.compare.read_text(encoding="utf-8")))
        print(message)
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
