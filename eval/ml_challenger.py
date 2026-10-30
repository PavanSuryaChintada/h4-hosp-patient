"""Trained models scored against the rules: drug names (here), conditions (eval/ml_conditions.py)
and alert triage (eval/ml_triage.py). Off the scoring path.

    python -m eval.ml_challenger          # all three; writes docs/ml-challenger.md

The submission is rules only (CLAUDE.md rule 1). This experiment asks whether a model trained
on the labelled lines would resolve names better, and answers with the organisers' scorer.

The model, in the standard library only (no PyTorch, no downloads):

    features   character 3- and 4-grams of a line's name words (medsafe.resolve.normalise), TF-IDF
               weighted, L2-normalised: the classical form of "embed the name, look up the nearest"
    training   every reference name (generic, brand, combination brand) plus every labelled line of
               the dev split (train_resolution.csv, dev patients only)
    predict    the label (set of generics, or "not a medicine") of the most similar training name
    abstain    when that similarity is below MIN_SIMILARITY, or within MIN_MARGIN of the best
               different label: the same contract as the rule-based resolver

The two thresholds are chosen by 5-fold cross-validation inside dev. Holdout is used once, at
the end: both resolvers' output goes through the same rule engine and output policy, and both
submissions are scored by evaluate.py. Because a model trained on labelled lines can memorise
lines that repeat, accuracy is also reported on holdout lines never seen in dev.

Never imported by run.py, src/, eval/run.py or eval/sweep.py.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval import official
from eval.pack import ROOT, data_dir, require_pack
from eval.split import split_ids
from eval.truth import load_truth
from medsafe.data.adapter import Dataset, load_dataset
from medsafe.output.writer import PREDICTIONS_FILE, RESOLUTION_FILE, token_key, write_predictions, write_resolution
from medsafe.pipeline import run_pipeline
from medsafe.resolve.normalise import clean, normalise
from medsafe.resolve.resolver import Resolution

NGRAMS = (3, 4)
FOLDS = 5
SIMILARITY_GRID = tuple(round(0.30 + 0.05 * i, 2) for i in range(11))     # 0.30 .. 0.80
MARGIN_GRID = (0.0, 0.02, 0.05, 0.10)
DOCS_PATH = ROOT / "docs" / "ml-challenger.md"
REPORTS_DIR = ROOT / "eval" / "reports"
MISSPELLED = {"misspelled_brand", "misspelled_generic", "misspelled_truncated"}

Label = tuple[str, ...]                 # sorted generics; () means "not a medicine"


def name_text(raw: str) -> str:
    """The words a line names a drug with, as the rule-based resolver reads them; the whole cleaned
    line if it has none."""
    words = normalise(raw).name_words
    return " ".join(words) if words else clean(raw)


def ngrams(text: str) -> Counter:
    """Character n-grams of ``text`` padded with '#', for every n in NGRAMS."""
    padded = f"#{text.replace(' ', '#')}#"
    return Counter(padded[i:i + n] for n in NGRAMS for i in range(len(padded) - n + 1))


@dataclass(frozen=True)
class Prediction:
    """The model's best label for one line, how similar it was, and the runner-up."""

    label: Label
    similarity: float
    runner_up: float
    candidates: tuple[tuple[Label, float], ...]


class NgramNearestNeighbour:
    """TF-IDF character n-gram vectors with nearest-neighbour labels, over an inverted index.

    Args:
        examples: (written text, label) pairs to learn from. Identical texts with the same label
            are one example.
    """

    def __init__(self, examples: Iterable[tuple[str, Label]]):
        unique = sorted({(name_text(text), label) for text, label in examples})
        counts = [ngrams(text) for text, _ in unique]
        documents = Counter(g for c in counts for g in c)
        self.idf = {g: math.log((1 + len(unique)) / (1 + df)) + 1.0 for g, df in documents.items()}
        self.labels = [label for _, label in unique]
        self.postings: dict[str, list[tuple[int, float]]] = defaultdict(list)
        for doc, count in enumerate(counts):
            vector = self._weigh(count)
            for gram, weight in vector.items():
                self.postings[gram].append((doc, weight))

    def _weigh(self, count: Counter) -> dict[str, float]:
        """TF-IDF weights for known n-grams, L2-normalised. Unknown n-grams are dropped."""
        vector = {g: (1 + math.log(n)) * self.idf[g] for g, n in count.items() if g in self.idf}
        norm = math.sqrt(sum(w * w for w in vector.values())) or 1.0
        return {g: w / norm for g, w in vector.items()}

    def predict(self, raw: str) -> Prediction:
        """The most similar training name's label, the best similarity of any other label, and
        the top three labels. Ties break alphabetically, so the same line always gets the same answer."""
        scores: dict[int, float] = defaultdict(float)
        for gram, weight in self._weigh(ngrams(name_text(raw))).items():
            for doc, doc_weight in self.postings[gram]:
                scores[doc] += weight * doc_weight
        best: dict[Label, float] = {}
        for doc, score in scores.items():
            label = self.labels[doc]
            if score > best.get(label, -1.0):
                best[label] = score
        ranked = sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))
        if not ranked:
            return Prediction((), 0.0, 0.0, ())
        return Prediction(ranked[0][0], ranked[0][1], ranked[1][1] if len(ranked) > 1 else 0.0,
                          tuple(ranked[:3]))


class ModelResolver:
    """The model behind the resolver interface ``run_pipeline`` takes, so the rule engine and
    output policy downstream are exactly the shipped ones."""

    def __init__(self, model: NgramNearestNeighbour, min_similarity: float, min_margin: float):
        self.model, self.min_similarity, self.min_margin = model, min_similarity, min_margin
        self.cache: dict[str, Resolution] = {}

    def resolve(self, raw: str) -> Resolution:
        """Resolve one written line, or abstain."""
        if raw not in self.cache:
            self.cache[raw] = to_resolution(raw, self.model.predict(raw), self.min_similarity, self.min_margin)
        return self.cache[raw]


def to_resolution(raw: str, p: Prediction, min_similarity: float, min_margin: float) -> Resolution:
    """A prediction as a Resolution: abstained below the thresholds, otherwise the label."""
    candidates = tuple((";".join(label) or "(not a medicine)", round(score, 4)) for label, score in p.candidates)
    if p.similarity < min_similarity or p.similarity - p.runner_up < min_margin:
        return Resolution(raw, name_text(raw), (), "abstained", round(p.similarity, 4), candidates,
                          "no_confident_match" if p.similarity < min_similarity else "ambiguous")
    method = "non_drug" if not p.label else "exact" if p.similarity >= 0.999 else "fuzzy"
    return Resolution(raw, name_text(raw), p.label, method, round(p.similarity, 4), candidates)


def reference_examples(dataset: Dataset) -> list[tuple[str, Label]]:
    """Every name in the reference tables, labelled with its generics."""
    examples = []
    for generic, drug in dataset.drugs.items():
        examples.append((generic, (generic,)))
        examples += [(brand, (generic,)) for brand in drug.brands]
    examples += [(c.brand, tuple(sorted(c.generics))) for c in dataset.combinations]
    return examples


def accuracy(rows: Sequence[tuple[Label, Label]]) -> float:
    """Share of (predicted, true) pairs that agree exactly, the scorer's resolution rule."""
    return sum(1 for predicted, true in rows if predicted == true) / max(len(rows), 1)


def choose_thresholds(dataset: Dataset, dev_tokens: Sequence[Any]) -> dict[str, Any]:
    """Pick MIN_SIMILARITY and MIN_MARGIN by 5-fold cross-validation over dev patients.

    Each fold's lines are predicted by a model trained on the reference names and the other four
    folds, so no line is scored by a model that saw it. Returns the chosen pair and its accuracy.
    """
    patients = sorted({t.patient_id for t in dev_tokens})
    fold_of = {pid: i % FOLDS for i, pid in enumerate(patients)}
    reference = reference_examples(dataset)
    held: list[tuple[Prediction, Label]] = []
    for fold in range(FOLDS):
        train = [(t.written_token, tuple(sorted(t.generics))) for t in dev_tokens if fold_of[t.patient_id] != fold]
        model = NgramNearestNeighbour(reference + train)
        held += [(model.predict(t.written_token), tuple(sorted(t.generics)))
                 for t in dev_tokens if fold_of[t.patient_id] == fold]
    grid = []
    for similarity in SIMILARITY_GRID:
        for margin in MARGIN_GRID:
            rows = [(to_resolution("", p, similarity, margin).generics, true) for p, true in held]
            grid.append((accuracy(rows), similarity, margin))
    best = max(grid, key=lambda g: (round(g[0], 6), g[1], -g[2]))
    return {"min_similarity": best[1], "min_margin": best[2], "cv_accuracy": round(best[0], 4),
            "folds": FOLDS, "lines": len(held)}


def score_submission(dataset: Dataset, ids: frozenset[str], resolver: Any, folder: Path) -> tuple[dict, Any]:
    """Run the shipped pipeline on ``ids`` with ``resolver`` and score it with evaluate.py."""
    subset = replace(dataset, patients=[p for p in dataset.patients if p.patient_id in ids])
    result = run_pipeline(subset, resolver=resolver) if resolver is not None else run_pipeline(subset)
    write_resolution(result, folder / RESOLUTION_FILE)
    write_predictions([a for p in result.patients for a in p.alerts or ()], folder / PREDICTIONS_FILE)
    from eval.truth import write_truth_subset
    labels, truth_resolution = write_truth_subset(data_dir(), ids, folder / "truth")
    return official.score(folder / PREDICTIONS_FILE, folder / RESOLUTION_FILE, labels, truth_resolution,
                          folder / "score.json"), result


def line_breakdown(result: Any, tokens: Sequence[Any], seen: set[str]) -> dict[str, Any]:
    """Accuracy on every holdout line, on misspelled ones, and on ones never seen in dev."""
    truth = {(t.patient_id, token_key(t.written_token)): t for t in tokens}
    rows = []
    for patient in result.patients:
        for medication, resolution in zip(patient.patient.medications, patient.resolutions):
            t = truth.get((patient.patient.patient_id, token_key(medication.raw)))
            if t is not None:
                rows.append((resolution, t))
    pairs = lambda keep: [(tuple(r.generics), tuple(sorted(t.generics))) for r, t in rows if keep(r, t)]  # noqa: E731
    unseen = lambda r, t: token_key(t.written_token) not in seen  # noqa: E731
    return {
        "lines": len(rows),
        "accuracy": round(accuracy(pairs(lambda r, t: True)), 4),
        "misspelled_accuracy": round(accuracy(pairs(lambda r, t: t.token_kind in MISSPELLED)), 4),
        "unseen_lines": len(pairs(unseen)),
        "unseen_accuracy": round(accuracy(pairs(unseen)), 4),
        "unseen_misspelled_accuracy": round(accuracy(pairs(lambda r, t: unseen(r, t) and t.token_kind in MISSPELLED)), 4),
        "wrong_confident": sum(1 for r, t in rows if r.method != "abstained" and tuple(r.generics) != tuple(sorted(t.generics))),
        "abstained": sum(1 for r, _ in rows if r.method == "abstained"),
    }


def run(dataset: Dataset) -> dict[str, Any]:
    """Train on dev, choose thresholds by cross-validation, score both resolvers on holdout."""
    ids = [p.patient_id for p in dataset.patients]
    dev, holdout = split_ids(ids, "dev"), split_ids(ids, "holdout")
    truth = load_truth(data_dir(), set(ids))
    dev_tokens = [t for t in truth.tokens if t.patient_id in dev]
    holdout_tokens = [t for t in truth.tokens if t.patient_id in holdout]
    chosen = choose_thresholds(dataset, dev_tokens)
    model = NgramNearestNeighbour(reference_examples(dataset)
                                  + [(t.written_token, tuple(sorted(t.generics))) for t in dev_tokens])
    seen = {token_key(t.written_token) for t in dev_tokens}
    out: dict[str, Any] = {"thresholds": chosen, "training_lines": len(dev_tokens),
                           "holdout_patients": len(holdout), "submissions": {}}
    with tempfile.TemporaryDirectory() as tmp:
        for name, resolver in (("rules (shipped)", None),
                               ("ML challenger", ModelResolver(model, chosen["min_similarity"], chosen["min_margin"]))):
            folder = Path(tmp) / name.split()[0]
            report, result = score_submission(dataset, holdout, resolver, folder)
            out["submissions"][name] = {"official": report, "lines": line_breakdown(result, holdout_tokens, seen)}
    return out


def run_conditions(dataset: Dataset, dev: frozenset[str], holdout: frozenset[str],
                   issues: Mapping[str, list[Any]]) -> dict[str, Any]:
    """Stage 2: train the learned condition reader on dev, then score both readers on holdout."""
    from eval import ml_conditions as stage2
    from medsafe.rules.conditions import detect_conditions

    full = run_pipeline(dataset)
    dev_results = [r for r in full.patients if r.patient.patient_id in dev]
    holdout_results = [r for r in full.patients if r.patient.patient_id in holdout]
    reader, info = stage2.train(dev_results, issues, dataset)
    pairs = stage2.weak_labels(holdout_results, issues, dataset, stage2.text_conditions(dataset))
    out: dict[str, Any] = {**info, "pairs": {"rules (shipped)": stage2.pair_accuracy(holdout_results, pairs, detect_conditions),
                                             "learned reader": stage2.pair_accuracy(holdout_results, pairs, reader)},
                           "official": {}}
    with tempfile.TemporaryDirectory() as tmp:
        out["official"]["rules (shipped)"] = score_submission(dataset, holdout, None, Path(tmp) / "rules")[0]
        with stage2.patched(reader):
            out["official"]["learned reader"] = score_submission(dataset, holdout, None, Path(tmp) / "learned")[0]
    return out


def run_triage(dataset: Dataset, dev: frozenset[str], holdout: frozenset[str],
               issues: Mapping[str, list[Any]]) -> dict[str, Any]:
    """Stage 3: train the alert-triage trees on the standard check's dev alerts, score holdout."""
    from eval import ml_triage as stage3
    from tools.ehr_reference import EhrTables, check_all

    ehr = check_all(dataset.patients, EhrTables.from_dataset(dataset))
    out = stage3.run(dataset, ehr, dev, holdout, issues)
    with tempfile.TemporaryDirectory() as tmp:
        out["official"]["rules (shipped)"] = score_submission(dataset, holdout, None, Path(tmp) / "rules")[0]
    return out


def run_all(dataset: Dataset) -> dict[str, Any]:
    """All three challengers on the same dev / holdout split."""
    ids = [p.patient_id for p in dataset.patients]
    dev, holdout = split_ids(ids, "dev"), split_ids(ids, "holdout")
    issues: dict[str, list[Any]] = defaultdict(list)
    for issue in load_truth(data_dir(), set(ids)).issues:
        issues[issue.patient_id].append(issue)
    return {"names": run(dataset), "conditions": run_conditions(dataset, dev, holdout, issues),
            "triage": run_triage(dataset, dev, holdout, issues)}


CAVEAT = ("Holdout is not a clean out-of-sample estimate for the rules. The condition vocabulary and stop "
          "markers were built by reading all training text, holdout included (docs/DECISIONS.md D-025), and the "
          "resolver's synonym list comes from dev failures plus general prescribing knowledge (D-014), which git "
          "cannot prove line by line. So the rules' perfect holdout rows are optimistic, and the hidden test set "
          "may score lower. Each comparison below is fair only as \"how a learned model does on the same "
          "patients\", not as rules against model generalisation. The models' own numbers are out of sample: "
          "none trained or tuned on holdout.")


def _table(columns: Sequence[str], rows: Sequence[tuple[str, Sequence[Any]]]) -> list[str]:
    """A markdown table: one header row, then one row per (label, values)."""
    return ["| | " + " | ".join(columns) + " |", "|---" * (len(columns) + 1) + "|",
            *[f"| {label} | " + " | ".join(str(v) for v in values) + " |" for label, values in rows]]


def render_names(report: dict[str, Any]) -> list[str]:
    """Stage 1: the confident-wrong finding first, then the numbers."""
    t = report["thresholds"]
    rules, ml = report["submissions"]["rules (shipped)"], report["submissions"]["ML challenger"]
    get = lambda f: [f(rules), f(ml)]  # noqa: E731
    return [
        "## Stage 1: reading drug names",
        "",
        f"A matcher trained on the labelled lines resolved **{ml['lines']['wrong_confident']} holdout lines "
        f"confidently wrong** (the shipped resolver: {rules['lines']['wrong_confident']}), and abstained on "
        f"{ml['lines']['abstained']}. A confidently wrong name is the failure that hides a real interaction: the "
        "line is checked as the wrong drug, and nothing on screen says to verify it. An abstention is shown to a "
        "person as \"verify manually\" instead.",
        "",
        f"- **Model:** character 3- and 4-gram TF-IDF, nearest neighbour. Trained on the reference names and the "
        f"{report['training_lines']} labelled lines of the dev split.",
        f"- **Abstains** below similarity {t['min_similarity']} or a margin under {t['min_margin']}, chosen by "
        f"{t['folds']}-fold cross-validation inside dev (accuracy {t['cv_accuracy']} on {t['lines']} lines).",
        "",
        *_table(["Rules (shipped)", "Learned matcher"], [
            ("Wrong and not abstained", get(lambda s: s["lines"]["wrong_confident"])),
            ("Abstained", get(lambda s: s["lines"]["abstained"])),
            ("Primary score", get(lambda s: s["official"]["primary_score"])),
            ("Serious recall", get(lambda s: s["official"]["components"]["serious_recall"])),
            ("Resolution accuracy, all lines", get(lambda s: s["lines"]["accuracy"])),
            ("Resolution accuracy, misspelled lines", get(lambda s: s["lines"]["misspelled_accuracy"])),
            ("Accuracy on lines never seen in dev", get(lambda s: s["lines"]["unseen_accuracy"])),
        ]),
        "",
        "\"Never seen in dev\" is out of sample for the model only.",
        "",
    ]


def render_conditions(report: dict[str, Any]) -> list[str]:
    """Stage 2: the learned condition reader against the rules, component and end to end."""
    rules_pairs, ml_pairs = report["pairs"]["rules (shipped)"], report["pairs"]["learned reader"]
    rules_off, ml_off = report["official"]["rules (shipped)"], report["official"]["learned reader"]
    contra = lambda o: o["per_issue_type"]["contraindication"]  # noqa: E731
    return [
        "## Stage 2: reading conditions and negation",
        "",
        "A logistic-regression reader of the diagnosis and allergy text, swapped in for the shipped rules "
        "inside the unchanged rule engine. It learned from contraindication labels alone: a condition is absent "
        "when a drug it contraindicates carries no label, present when only it explains a drug's label.",
        "",
        f"- **Trained on** {report['examples']} (patient, condition) pairs from dev, {report['present']} present; "
        f"threshold {report['threshold']} chosen by {report['folds']}-fold cross-validation (F1 {report['cv_f1']}).",
        f"- **Holdout pairs** labelled the same way: {rules_pairs['pairs']}, {rules_pairs['present']} present.",
        "",
        *_table(["Rules (shipped)", "Learned reader"], [
            ("Conditions found: precision", [rules_pairs["precision"], ml_pairs["precision"]]),
            ("Conditions found: recall", [rules_pairs["recall"], ml_pairs["recall"]]),
            ("Contraindication serious recall", [contra(rules_off)["serious_recall"], contra(ml_off)["serious_recall"]]),
            ("Contraindication alerts (matched)", [f"{contra(rules_off)['alerts']} ({contra(rules_off)['alerts_matched']})",
                                                    f"{contra(ml_off)['alerts']} ({contra(ml_off)['alerts_matched']})"]),
            ("Primary score", [rules_off["primary_score"], ml_off["primary_score"]]),
        ]),
        "",
    ]


def render_triage(report: dict[str, Any]) -> list[str]:
    """Stage 3: learned triage of a standard check's alerts, against that check and the rules."""
    off = report["official"]
    names = ["standard check", "standard check + learned triage", "rules (shipped)"]
    col = lambda f: [f(off[n]) for n in names]  # noqa: E731
    return [
        "## Stage 3: which alerts are worth a prescriber's time",
        "",
        "The textbook version predicts adverse drug events or whether a prescriber acts on an alert. This "
        "dataset records neither, so that model cannot be trained honestly here. Instead, gradient-boosted trees "
        "learn which of a standard hospital check's alerts match a real issue that is not minor, and hold back "
        "the rest.",
        "",
        f"- **Trained on** the standard check's {report['training_alerts']} alerts on dev patients "
        f"({report['worth_showing']} worth showing). Hold-back threshold {report['threshold']}, chosen with the "
        f"organisers' scorer on {report['folds']}-fold out-of-fold scores.",
        f"- **Holdout:** {report['holdout_alerts']} alerts; ranking AUC {report['holdout_auc']}. Held back "
        f"{report['held_back']}, of which {report['held_back_worth_showing']} were worth showing.",
        "- **What the trees split on most:** " + ", ".join(f"{name} ({gain})" for name, gain in report["importance"]) + ".",
        "",
        *_table(["Standard check", "+ learned triage", "Rules (shipped)"], [
            ("Primary score", col(lambda o: o["primary_score"])),
            ("Noise per patient", col(lambda o: o["components"]["noise_alerts_per_patient"])),
            ("Precision", col(lambda o: o["components"]["precision_all"])),
            ("Serious recall", col(lambda o: o["components"]["serious_recall"])),
        ]),
        "",
        "Triage can only hold back what a check raised. It cannot raise what the check never saw: the "
        "standard check's recall is capped by the names its formulary does not recognise.",
        "",
    ]


def render(report: dict[str, Any]) -> str:
    """docs/ml-challenger.md: the caveat, then one section per stage. Every number from ``report``."""
    lines = [
        "# Trained models against the rules",
        "",
        f"Generated by `python -m eval.ml_challenger` at {report['generated_at']}. Do not edit by hand.",
        "",
        "The submission is rules only (CLAUDE.md rule 1). Three models are trained here, each standard library "
        "only, each on the dev split, each scored once on the holdout split with the organisers' `evaluate.py`, "
        "and none on the scoring path.",
        "",
        "## What these comparisons can and cannot say",
        "",
        CAVEAT,
        "",
        *render_names(report["names"]),
        *render_conditions(report["conditions"]),
        *render_triage(report["triage"]),
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run all three experiments, write the JSON report and docs/ml-challenger.md. Returns 0."""
    parser = argparse.ArgumentParser(description="Score trained models against the rules, on holdout.")
    parser.add_argument("--docs", type=Path, default=DOCS_PATH)
    args = parser.parse_args(argv)
    require_pack()
    report = run_all(load_dataset(data_dir(), "train"))
    report["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (REPORTS_DIR / f"{stamp}-ml-challenger.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.docs.write_text(render(report), encoding="utf-8")
    for name, s in report["names"]["submissions"].items():
        print(f"names       {name:26} primary {s['official']['primary_score']:.4f}  wrong {s['lines']['wrong_confident']}")
    for name, o in report["conditions"]["official"].items():
        print(f"conditions  {name:26} primary {o['primary_score']:.4f}  "
              f"contraindication recall {o['per_issue_type']['contraindication']['serious_recall']}")
    for name, o in report["triage"]["official"].items():
        print(f"triage      {name:26} primary {o['primary_score']:.4f}  noise {o['components']['noise_alerts_per_patient']}")
    print(f"wrote {args.docs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
