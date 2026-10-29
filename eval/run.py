"""Evaluation harness: run the pipeline, score it against ground truth, write a report.

    python -m eval.run [--input tests/fixtures] [--compare eval/reports/<earlier>.json]

Prints the two headline numbers side by side (serious-issue recall, and alerts per patient
before collapse -> after collapse and cap), then near-miss recall with every missed near-miss
and the stage where it was lost. Writes ``eval/reports/<timestamp>-<git_sha>.json`` and
regenerates ``docs/evaluation.md``. With ``--compare``, exits 1 if serious-issue recall dropped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval import mirror
from eval.baselines import evaluate_baselines
from eval.metrics import caught, compute_metrics
from eval.records import TruthMedication
from eval.trace import diagnose, traces_from
from eval.truth import Truth, load_truth
from medsafe.data.adapter import Dataset, load_dataset
from medsafe.data.validate import SchemaError
from medsafe.pipeline import STAGES, Settings, run_pipeline

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "tests" / "fixtures"
DEFAULT_REPORTS = ROOT / "eval" / "reports"
DEFAULT_DOCS = ROOT / "docs" / "evaluation.md"


@dataclass(frozen=True)
class Evaluation:
    """One scored run: what was built, what it scored, and what it missed."""

    settings: Settings
    stages_built: tuple[str, ...]
    metrics: dict[str, Any]
    score: float
    missed_near_misses: list[dict[str, str]]
    baselines: dict[str, dict[str, Any]]
    load: list[dict[str, Any]]


def evaluate(dataset: Dataset, truth: Truth, settings: Settings = Settings(), *,
             with_baselines: bool = True) -> Evaluation:
    """Run the pipeline over ``dataset`` and score it against ``truth``.

    Args:
        dataset: Loaded input.
        truth: Labels for the same patients.
        settings: Thresholds to run the pipeline with.
        with_baselines: Also score the calibration baselines (skipped by the sweep).

    Returns:
        The metrics, mirror score, missed near-misses with the reason for each, and the load
        counts. Deterministic for the same inputs.
    """
    result = run_pipeline(dataset, settings)
    traces = traces_from(result)
    metrics = compute_metrics(truth.issues, traces, truth.medications)
    shipped = [a for t in traces.values() for a in (t.shipped or ())]
    medications: dict[str, list[TruthMedication]] = {}
    for medication in truth.medications:
        medications.setdefault(medication.patient_id, []).append(medication)

    near_misses = [i for i in truth.issues if i.near_miss]
    missed = [{
        "patient_id": issue.patient_id,
        "issue_type": issue.issue_type,
        "severity": issue.severity,
        "drugs": " + ".join(sorted(issue.drugs)),
        "as_written": " + ".join(f"'{raw}'" for raw in issue.raw_drugs),
        "near_miss_because": issue.near_miss_reason,
        "missed_because": diagnose(issue, traces.get(issue.patient_id),
                                   medications.get(issue.patient_id, [])),
    } for issue, hit in zip(near_misses, caught(near_misses, shipped)) if not hit]
    missed.sort(key=lambda m: (m["patient_id"], m["issue_type"], m["drugs"]))

    return Evaluation(
        settings=settings,
        stages_built=result.stages_built,
        metrics=metrics,
        score=mirror.score(metrics),
        missed_near_misses=missed,
        baselines=evaluate_baselines(truth, list(traces)) if with_baselines else {},
        load=[{key: report.to_dict()[key] for key in
               ("kind", "rows_read", "loaded", "loaded_clean", "loaded_degraded", "skipped",
                "degraded_fields", "reasons")} for report in dataset.reports],
    )


def data_version(input_dir: Path) -> str:
    """Short content hash of every CSV and JSON file in ``input_dir``: names and bytes."""
    digest = hashlib.sha256()
    for path in sorted(input_dir.glob("*")):
        if path.suffix.lower() in (".csv", ".json"):
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def git_revision() -> str:
    """Short git sha of the checkout, with ``-dirty`` if there are uncommitted changes."""
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, check=True,
                             capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, check=True,
                               capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{sha}-dirty" if dirty else sha


def build_report(evaluation: Evaluation, input_dir: Path, generated_at: datetime) -> dict[str, Any]:
    """The JSON report: provenance, every threshold, every metric, every missed near-miss."""
    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "git_revision": git_revision(),
        "input_dir": _display(input_dir),
        "data_version": data_version(input_dir),
        "stages_built": list(evaluation.stages_built),
        "settings": {**asdict(evaluation.settings),
                     "mirror": "eval.mirror.score",
                     "low_value_alert_penalty": mirror.LOW_VALUE_ALERT_PENALTY},
        "headline": {"serious_recall": evaluation.metrics["serious_recall"],
                     "alerts_per_patient_before": evaluation.metrics["alerts_per_patient_before"],
                     "alerts_per_patient_after": evaluation.metrics["alerts_per_patient_after"]},
        "score": evaluation.score,
        "metrics": evaluation.metrics,
        "missed_near_misses": evaluation.missed_near_misses,
        "baselines": evaluation.baselines,
        "load": evaluation.load,
    }


def write_report(report: dict[str, Any], reports_dir: Path) -> Path:
    """Write ``report`` to ``<reports_dir>/<timestamp>-<git_revision>.json``. Returns the path."""
    stamp = datetime.fromisoformat(report["generated_at"]).strftime("%Y%m%dT%H%M%SZ")
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{stamp}-{report['git_revision']}.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return path


def compare(report: dict[str, Any], previous: dict[str, Any]) -> tuple[bool, str]:
    """Regression gate. Returns (ok, message); not ok if serious-issue recall dropped."""
    now = report["metrics"]["serious_recall"]
    before = previous["metrics"]["serious_recall"]
    dropped = before is not None and (now is None or now < before - 1e-9)
    verdict = "REGRESSION: serious-issue recall dropped" if dropped else "ok: no recall drop"
    return not dropped, (f"{verdict} ({_num(before)} in {previous.get('git_revision', '?')} -> "
                         f"{_num(now)} now)")


def _num(value: float | None, digits: int = 2) -> str:
    """Format a metric for display; None means not measurable."""
    return "n/a" if value is None else f"{value:.{digits}f}"


def _display(path: Path) -> str:
    """A path relative to the repo root when it is inside it, with forward slashes."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def headline(metrics: dict[str, Any]) -> str:
    """The two headline numbers, side by side. Never one without the other."""
    return (f"{'Serious-issue recall':<28}Alerts per patient\n"
            f"{_num(metrics['serious_recall']):<28}"
            f"{metrics['alerts_per_patient_before']:.1f} -> {metrics['alerts_per_patient_after']:.1f}")


def _stage_caveat(report: dict[str, Any]) -> str:
    """A sentence on what the numbers can mean given the stages built, or an empty string."""
    missing = [s for s in STAGES if s not in report["stages_built"]]
    if not missing:
        return ""
    return (f"Built so far: {', '.join(report['stages_built'])}. Not yet built: "
            f"{', '.join(missing)}. Nothing is flagged until those land, so recall is zero by "
            f"construction; the calibration baselines and tests/test_metrics.py show the "
            f"harness itself measures correctly.")


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """A Markdown table."""
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def render_markdown(report: dict[str, Any], report_path: str) -> str:
    """docs/evaluation.md, generated from one report."""
    m = report["metrics"]
    s = report["settings"]
    parts = [
        "# Evaluation",
        f"Generated by `python -m eval.run` from `{report_path}`. Do not edit by hand.",
        _table(["", ""], [
            ["Git revision", f"`{report['git_revision']}`"],
            ["Data", f"`{report['input_dir']}`, version `{report['data_version']}`"],
            ["Stages built", ", ".join(report["stages_built"])],
            ["Settings", f"alert_cap {s['alert_cap']}, min_confidence {s['min_confidence']}, "
                         f"min_margin {s['min_margin']}"],
            ["Mirror", f"`{s['mirror']}`, low-value alert penalty {s['low_value_alert_penalty']}"],
        ]),
        "## Headline",
        "```\n" + headline(m) + "\n```",
        f"Mirror score **{report['score']:.3f}**. Near-miss recall **{_num(m['near_miss_recall'])}** "
        f"({m['near_misses_caught']} of {m['near_misses']} caught). "
        f"{m['serious_caught']} of {m['serious_issues']} serious issues caught.",
    ]
    caveat = _stage_caveat(report)
    if caveat:
        parts.append(caveat)

    parts += ["## Missed near-misses",
              f"{len(report['missed_near_misses'])} of {m['near_misses']} missed, each with the "
              f"stage where it was lost."]
    if report["missed_near_misses"]:
        parts.append(_table(
            ["Patient", "Issue", "Severity", "Drugs", "As written", "Why it is a near-miss",
             "Why it was missed"],
            [[x["patient_id"], x["issue_type"], x["severity"], x["drugs"], x["as_written"],
              x["near_miss_because"], x["missed_because"]] for x in report["missed_near_misses"]]))

    by_severity = m["alerts_per_patient_by_severity"]
    resolution = m["resolution"]
    parts += [
        "## Breakdowns",
        "### Serious-issue recall by issue type",
        _table(["Issue type", "Recall"],
               [[k, _num(v)] for k, v in m["serious_recall_by_issue_type"].items()]),
        "### Recall by true severity",
        _table(["True severity", "Recall"],
               [[k, _num(v)] for k, v in m["recall_by_true_severity"].items()]),
        "### Alerts per patient by severity",
        _table(["Severity", "Before collapse", "After collapse and cap"],
               [[k, f"{by_severity['before'][k]:.2f}", f"{by_severity['after'][k]:.2f}"]
                for k in by_severity["before"]]),
        "### False positives by severity",
        "Shipped alerts that match no true issue at all. Low-value alerts per patient (the mirror's "
        f"penalty term): **{m['low_value_alerts_per_patient']:.2f}**.",
        _table(["Alert severity", "False positives"],
               [[k, v] for k, v in m["false_positives_by_severity"].items()]),
        "### Name resolution",
        ("Not available: name resolution is not built yet (Phase 2)." if resolution is None else
         _table(["Measure", "Value"], [[k, v if k == "lines" else _num(v, 3)]
                                       for k, v in resolution.items()])),
        "### Patients with no alert",
        f"{m['zero_alert_patients']['count']} of {m['patients']} patients had no alert; "
        f"{m['zero_alert_patients']['with_serious_issue']} of those have a serious true issue.",
        "## Load",
        _table(["File", "Read", "Clean", "Degraded", "Skipped"],
               [[x["kind"], x["rows_read"], x["loaded_clean"], x["loaded_degraded"],
                 x["skipped"]] for x in report["load"]]),
    ]
    if report["baselines"]:
        parts += [
            "## Calibration baselines",
            "These read the true generics and skip name resolution. They check the harness and "
            "the mirror, not the detector: flagging nothing must score 0, flagging everything "
            "must score near 0, and the oracle sets the ceiling.",
            _table(["Baseline", "Serious recall", "Near-miss recall", "Alerts per patient",
                    "Low-value per patient", "Mirror score"],
                   [[name, _num(b["serious_recall"]), _num(b["near_miss_recall"]),
                     f"{b['alerts_per_patient']:.1f}", f"{b['low_value_alerts_per_patient']:.1f}",
                     f"{b['score']:.3f}"] for name, b in report["baselines"].items()]),
        ]
    parts += ["## Reproduce",
              "```\npython tools/make_fixtures.py\npython -m eval.run\npython -m eval.sweep\n```"]
    return "\n\n".join(parts) + "\n"


def render_console(report: dict[str, Any], report_path: str) -> str:
    """The plain-text summary printed by ``python -m eval.run``."""
    m = report["metrics"]
    lines = [headline(m), "",
             f"Near-miss recall {_num(m['near_miss_recall'])} "
             f"({m['near_misses_caught']} of {m['near_misses']} caught)",
             f"Mirror score {report['score']:.3f}"]
    caveat = _stage_caveat(report)
    if caveat:
        lines += ["", caveat]
    lines += ["", f"Missed near-misses ({len(report['missed_near_misses'])}):"]
    lines += [f"  {x['patient_id']}  {x['issue_type']:<16} {x['drugs']:<34} {x['missed_because']}"
              for x in report["missed_near_misses"]]
    if report["baselines"]:
        lines += ["", f"{'Baseline':<17}{'recall':>8}{'alerts/pt':>11}{'low-value/pt':>14}"
                      f"{'score':>8}"]
        lines += [f"{name:<17}{_num(b['serious_recall']):>8}{b['alerts_per_patient']:>11.1f}"
                  f"{b['low_value_alerts_per_patient']:>14.1f}{b['score']:>8.3f}"
                  for name, b in report["baselines"].items()]
    lines += ["", f"report: {report_path}"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point. Returns 0 ok, 1 recall regression, 2 unusable input."""
    parser = argparse.ArgumentParser(description="Score the pipeline against ground truth.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help="input directory with labels beside it (default: fixtures)")
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument("--docs", type=Path, default=DEFAULT_DOCS,
                        help="where to write the Markdown summary")
    parser.add_argument("--no-docs", action="store_true", help="do not write the Markdown summary")
    parser.add_argument("--compare", type=Path, help="earlier report; exit 1 if recall dropped")
    args = parser.parse_args(argv)

    try:
        dataset = load_dataset(args.input)
    except SchemaError as error:
        print(f"input error: {error}", file=sys.stderr)
        return 2
    truth = load_truth(args.input)
    if truth is None:
        print(f"no labels in {args.input}: recall cannot be measured", file=sys.stderr)
        return 2

    report = build_report(evaluate(dataset, truth), args.input, datetime.now(timezone.utc))
    path = write_report(report, args.reports_dir)
    if not args.no_docs:
        args.docs.parent.mkdir(parents=True, exist_ok=True)
        args.docs.write_text(render_markdown(report, _display(path)), encoding="utf-8")
    print(render_console(report, _display(path)))

    if args.compare:
        ok, message = compare(report, json.loads(args.compare.read_text(encoding="utf-8")))
        print(message)
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
