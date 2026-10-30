"""Graphs of the dataset and the three trained-model experiments, as PNGs in docs/figures/.

    python -m eval.ml_challenger     # trains, scores, writes eval/reports/<stamp>-ml-challenger.json
    python -m eval.ml_plots          # draws docs/figures/*.png from that report and the pack,
                                     # and copies them to ui/public/figures/ for the web app

Every number drawn comes from the newest ml-challenger report or from the pack's own CSV files.
Needs matplotlib (requirements-dev.txt); run.py and src/ never import it.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from eval.pack import ROOT, data_dir  # noqa: E402

REPORTS_DIR = ROOT / "eval" / "reports"
FIGURES_DIR = ROOT / "docs" / "figures"
SITE_FIGURES_DIR = ROOT / "ui" / "public" / "figures"
RULES, MODEL, STANDARD, GRID = "#1C4F86", "#8A96A0", "#A32A20", "#D2D9DF"
SEVERITY_COLOURS = {"contraindicated": "#6E1A14", "major": "#A32A20", "moderate": "#85590A", "minor": "#AFB9C2"}

plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 130, "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#AFB9C2",
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "legend.frameon": False, "figure.facecolor": "white",
})


def newest_report(reports_dir: Path = REPORTS_DIR) -> tuple[Path, dict[str, Any]]:
    """The newest three-stage ml-challenger report."""
    for path in sorted(reports_dir.glob("*-ml-challenger.json"), reverse=True):
        report = json.loads(path.read_text(encoding="utf-8"))
        if "names" in report:
            return path, report
    raise SystemExit("no ml-challenger report: run python -m eval.ml_challenger first")


def rows(name: str) -> list[dict[str, str]]:
    """One of the pack's CSV files as rows."""
    with (data_dir() / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def label_bars(ax, bars, fmt: str = "{:.3f}") -> None:
    """Write each bar's value above it."""
    for bar in bars:
        ax.annotate(fmt.format(bar.get_height()), (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    ha="center", va="bottom", fontsize=8, xytext=(0, 2), textcoords="offset points")


def save(fig, name: str, source: str) -> Path:
    """Footnote the source, save under docs/figures, close."""
    fig.text(0.01, 0.005, f"Source: {source}", fontsize=7, color="#78868F", ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    path = FIGURES_DIR / name
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


def fig_dataset() -> Path:
    """What the organisers gave us: patients, labelled issues, and how lines are written."""
    train, test = rows("patients_train.csv"), rows("patients_test.csv")
    labels, tokens = rows("train_labels.csv"), rows("train_resolution.csv")
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8), gridspec_kw={"width_ratios": [0.7, 1.2, 1.4]})

    ax = axes[0]
    bars = ax.bar(["Training\n(labels public)", "Test\n(labels hidden)"], [len(train), len(test)], color=[RULES, MODEL])
    label_bars(ax, bars, "{:,.0f}")
    ax.set_title("Patients")

    ax = axes[1]
    types = ["interaction", "duplicate_therapy", "renal_dose", "contraindication"]
    count = Counter((r["issue_type"], r["severity"]) for r in labels)
    left = [0] * len(types)
    for severity, colour in SEVERITY_COLOURS.items():
        values = [count[(t, severity)] for t in types]
        ax.barh([t.replace("_", " ") for t in types], values, left=left, color=colour, label=severity)
        left = [a + b for a, b in zip(left, values)]
    for y, total in enumerate(left):
        ax.annotate(f"{total:,}", (total, y), va="center", fontsize=8, xytext=(3, 0), textcoords="offset points")
    ax.invert_yaxis()
    ax.set_title(f"Labelled issues in training ({len(labels):,})")
    ax.legend(fontsize=7, loc="lower right")

    ax = axes[2]
    kinds = Counter(r["token_kind"] for r in tokens).most_common()
    ax.barh([k.replace("_", " ") for k, _ in kinds], [n for _, n in kinds],
            color=[STANDARD if k.startswith("misspelled") else RULES for k, _ in kinds])
    for y, (_, n) in enumerate(kinds):
        ax.annotate(f"{n:,}", (n, y), va="center", fontsize=8, xytext=(3, 0), textcoords="offset points")
    ax.invert_yaxis()
    ax.set_title(f"How {len(tokens):,} training lines are written (red: misspelled)")
    return save(fig, "1_dataset.png", "the H4 data pack: patients_*.csv, train_labels.csv, train_resolution.csv")


def fig_scores(report: dict[str, Any], source: str) -> Path:
    """The headline: every trained model against the rules, same holdout, same scorer."""
    names = report["names"]["submissions"]
    conditions, triage = report["conditions"]["official"], report["triage"]["official"]
    groups = [
        ("Stage 1\nreading drug names", [("Rules (shipped)", names["rules (shipped)"]["official"]["primary_score"], RULES),
                                         ("Learned matcher", names["ML challenger"]["official"]["primary_score"], MODEL)]),
        ("Stage 2\nreading conditions", [("Rules (shipped)", conditions["rules (shipped)"]["primary_score"], RULES),
                                         ("Learned reader", conditions["learned reader"]["primary_score"], MODEL)]),
        ("Stage 3\nalert triage", [("Standard EHR check", triage["standard check"]["primary_score"], STANDARD),
                                   ("Standard check + learned triage", triage["standard check + learned triage"]["primary_score"], MODEL),
                                   ("Rules (shipped)", triage["rules (shipped)"]["primary_score"], RULES)]),
    ]
    fig, ax = plt.subplots(figsize=(11, 4.2))
    x, ticks, seen = 0.0, [], set()
    for title, bars in groups:
        start = x
        for name, value, colour in bars:
            legend = {RULES: "Rules (shipped)", MODEL: "Learned model", STANDARD: "Standard EHR check"}[colour]
            bar = ax.bar(x, value, width=0.8, color=colour, label=None if legend in seen else legend)
            seen.add(legend)
            label_bars(ax, bar)
            x += 1
        ticks.append(((start + x - 1) / 2, title))
        x += 0.8
    ax.set_xticks([t for t, _ in ticks], [label for _, label in ticks])
    ax.set_ylim(0, 1.12)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Official score (evaluate.py)")
    ax.set_title("Trained models against the rules, on the 300 holdout patients")
    ax.legend(ncol=3, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.17))
    return save(fig, "2_scores.png", f"{source}; holdout is out of sample for the models only (D-025)")


def fig_names(report: dict[str, Any], source: str) -> Path:
    """Stage 1: accuracy by how a line is written, the learning curve, and the threshold search."""
    stage = report["names"]
    rules, ml = stage["submissions"]["rules (shipped)"]["lines"], stage["submissions"]["ML challenger"]["lines"]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2), gridspec_kw={"width_ratios": [1.3, 1, 1]})

    ax = axes[0]
    kinds = sorted(ml["by_kind"], key=lambda k: ml["by_kind"][k]["accuracy"])
    y = range(len(kinds))
    ax.barh([i + 0.2 for i in y], [rules["by_kind"][k]["accuracy"] for k in kinds], height=0.4, color=RULES, label="Rules (shipped)")
    ax.barh([i - 0.2 for i in y], [ml["by_kind"][k]["accuracy"] for k in kinds], height=0.4, color=MODEL, label="Learned matcher")
    ax.set_yticks(list(y), [f"{k.replace('_', ' ')} ({ml['by_kind'][k]['lines']})" for k in kinds])
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Holdout lines resolved exactly right")
    ax.set_title("Accuracy by how the line was written")
    ax.grid(axis="y", visible=False)
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.45, -0.14), ncol=2)

    ax = axes[1]
    curve = stage["learning_curve"]
    xs = [p["training_lines"] for p in curve]
    ax.plot(xs, [p["accuracy"] for p in curve], marker="o", color=MODEL, label="Learned matcher, all lines")
    ax.plot(xs, [p["misspelled_accuracy"] for p in curve], marker="o", color=STANDARD, label="Learned matcher, misspelled")
    ax.axhline(rules["accuracy"], color=RULES, linestyle="--", label=f"Rules, all lines ({rules['accuracy']:.3f})")
    ax.set_xlabel("Labelled dev lines the matcher trained on")
    ax.set_ylabel("Holdout accuracy")
    ax.set_title("Learning curve")
    ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=1)

    ax = axes[2]
    grid = [g for g in stage["thresholds"]["grid"] if g[1] == 0.0]
    ax.plot([g[0] for g in grid], [g[2] for g in grid], marker="o", color=MODEL)
    chosen = stage["thresholds"]["min_similarity"]
    ax.axvline(chosen, color=RULES, linestyle=":", label=f"chosen: {chosen}")
    ax.set_xlabel("Minimum similarity to answer (below it, abstain)")
    ax.set_ylabel(f"{stage['thresholds']['folds']}-fold cross-validated accuracy, dev")
    ax.set_title("Choosing the abstain threshold")
    ax.legend(fontsize=8)
    fig.suptitle(f"Stage 1, reading drug names: {ml['wrong_confident']} confident wrong names for the matcher, "
                 f"{rules['wrong_confident']} for the rules", fontsize=11, fontweight="bold")
    return save(fig, "3_names.png", source)


def fig_conditions(report: dict[str, Any], source: str) -> Path:
    """Stage 2: training loss, the threshold search, and the result against the rules."""
    stage = report["conditions"]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))

    ax = axes[0]
    history = stage["loss_history"]
    ax.plot(range(1, len(history) + 1), history, marker="o", markersize=3, color=MODEL)
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Training log-loss")
    ax.set_title(f"Training: logistic regression on {stage['examples']:,} pairs ({stage['present']} present)")

    ax = axes[1]
    ax.plot([g[0] for g in stage["grid"]], [g[1] for g in stage["grid"]], marker="o", color=MODEL)
    ax.axvline(stage["threshold"], color=RULES, linestyle=":", label=f"chosen: {stage['threshold']}")
    ax.set_xlabel("Probability threshold for 'condition present'")
    ax.set_ylabel(f"{stage['folds']}-fold cross-validated F1, dev")
    ax.set_title("Choosing the threshold")
    ax.legend(fontsize=8)

    ax = axes[2]
    pairs, official = stage["pairs"], stage["official"]
    metrics = [("Conditions found:\nprecision", lambda n: pairs[n]["precision"]),
               ("Conditions found:\nrecall", lambda n: pairs[n]["recall"]),
               ("Serious contra-\nindications caught", lambda n: official[n]["per_issue_type"]["contraindication"]["serious_recall"])]
    xs = range(len(metrics))
    label_bars(ax, ax.bar([i - 0.2 for i in xs], [f("rules (shipped)") for _, f in metrics], width=0.4, color=RULES, label="Rules (shipped)"), "{:.2f}")
    label_bars(ax, ax.bar([i + 0.2 for i in xs], [f("learned reader") for _, f in metrics], width=0.4, color=MODEL, label="Learned reader"), "{:.2f}")
    ax.set_xticks(list(xs), [m for m, _ in metrics])
    ax.set_ylim(0, 1.15)
    ax.grid(axis="x", visible=False)
    ax.set_title("Holdout result")
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2)
    fig.suptitle("Stage 2, reading conditions and negation", fontsize=11, fontweight="bold")
    return save(fig, "4_conditions.png", source)


def fig_triage(report: dict[str, Any], source: str) -> Path:
    """Stage 3: ROC, the boosting curve, what the trees split on, and the scored result."""
    stage = report["triage"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))

    ax = axes[0][0]
    roc = stage["roc"]
    ax.plot([p[0] for p in roc], [p[1] for p in roc], color=MODEL, linewidth=2, label=f"Boosted trees, AUC {stage['holdout_auc']:.3f}")
    ax.plot([0, 1], [0, 1], color=GRID, linestyle="--", label="Chance")
    ax.set_xlabel("False-positive rate (noise alerts kept)")
    ax.set_ylabel("True-positive rate (real alerts kept)")
    ax.set_title(f"ROC on {stage['holdout_alerts']} holdout alerts")
    ax.legend(fontsize=8, loc="lower right")

    ax = axes[0][1]
    curve = stage["trees_curve"]
    ax.plot([c[0] for c in curve], [c[1] for c in curve], marker="o", color=MODEL)
    ax.set_xscale("log")
    ax.set_xlabel("Trees in the ensemble")
    ax.set_ylabel("Holdout AUC")
    ax.set_title("Training curve: adding trees")

    ax = axes[1][0]
    importance = stage["importance_all"][:10][::-1]
    ax.barh([f.replace("_", " ") for f, _ in importance], [g for _, g in importance], color=MODEL)
    ax.set_xlabel("Total split gain")
    ax.grid(axis="y", visible=False)
    ax.set_title("What the trees split on")

    ax = axes[1][1]
    names = ["standard check", "standard check + learned triage", "rules (shipped)"]
    colours = [STANDARD, MODEL, RULES]
    official = stage["official"]
    xs = range(len(names))
    label_bars(ax, ax.bar(list(xs), [official[n]["primary_score"] for n in names], color=colours))
    ax2 = ax.twinx()
    ax2.plot(list(xs), [official[n]["components"]["noise_alerts_per_patient"] for n in names], color="#14202B",
             marker="D", linestyle="none", label="Noise alerts per patient (right axis)")
    ax2.set_ylim(0, 1.4)
    ax2.grid(False)
    ax.set_xticks(list(xs), ["Standard\ncheck", "Standard check\n+ learned triage", "Rules\n(shipped)"])
    ax.set_ylim(0, 1.12)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Official score")
    ax.set_title(f"Held back {stage['held_back']} alerts, {stage['held_back_worth_showing']} of them real")
    ax2.legend(fontsize=8, loc="upper left")
    fig.suptitle("Stage 3, which alerts are worth showing: gradient-boosted trees", fontsize=11, fontweight="bold")
    return save(fig, "5_triage.png", source)


def main(argv: list[str] | None = None) -> int:
    """Draw every figure. Returns 0."""
    argparse.ArgumentParser(description="Draw the dataset and trained-model graphs.").parse_args(argv)
    path, report = newest_report()
    source = path.relative_to(ROOT).as_posix()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    SITE_FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    for drawn in (fig_dataset(), fig_scores(report, source), fig_names(report, source),
                  fig_conditions(report, source), fig_triage(report, source)):
        shutil.copyfile(drawn, SITE_FIGURES_DIR / drawn.name)
        print(f"wrote {drawn.relative_to(ROOT).as_posix()} (and ui/public/figures/{drawn.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
