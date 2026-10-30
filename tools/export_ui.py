"""Writes the demo UI's data file from pipeline output. The UI reads this file and nothing else.

    python tools/export_ui.py                  # training patients -> ui/public/data/pipeline.json

The UI holds no detection logic (docs/phases/09-ui.md R1). Every number it shows is in this
file, computed here from ``run_pipeline``, from the standard-check reproduction
(``tools/ehr_reference.py``) or from the latest evaluation report. The schema is mirrored in
``ui/src/data/contract.ts``: change both together and bump ``SCHEMA_VERSION``.

A pipeline stage that is not built is exported as null, so the UI says "not built yet", never
"no issue found". A stage that is built but has no converter here raises
``NotImplementedError`` naming it, so the export can never silently drop alerts the pipeline
produced (the same seam as eval/trace.py, docs/DECISIONS.md D-008).

Demo patients are chosen by the ``pick_*`` criteria below, on the training split. Where a
criterion is about what is really wrong with a patient it reads the training labels: the labels
choose who is shown, the pipeline decides what is shown. docs/ui-demo.md lists the criteria.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import tempfile
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "src", REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from eval.pack import data_dir  # noqa: E402
from eval.truth import Truth, load_truth  # noqa: E402
from medsafe.data.adapter import Dataset, load_dataset  # noqa: E402
from medsafe.data.schema import SERIOUS, SEVERITIES, Patient  # noqa: E402
from medsafe.explain.limitations import DISCLAIMER, alert_limitations, not_checked, patient_summary  # noqa: E402
from medsafe.explain.prioritise import collapse as collapse_findings, prioritise  # noqa: E402
from medsafe.output.policy import submitted  # noqa: E402
from medsafe.output.writer import token_key  # noqa: E402
from medsafe.pipeline import STAGES, PatientResult, PipelineResult, run_pipeline  # noqa: E402
from medsafe.resolve.resolver import Resolution  # noqa: E402
from medsafe.rules.regimen import Regimen  # noqa: E402
from medsafe.rules.types import Finding  # noqa: E402
from medsafe import workflow  # noqa: E402
from tools.ehr_reference import (EhrAlert, EhrResult, EhrTables, check_all, name_words,  # noqa: E402
                                 write_submission)

SCHEMA_VERSION = 2
DEFAULT_OUTPUT = REPO_ROOT / "ui" / "public" / "data" / "pipeline.json"
REPORTS_DIR = REPO_ROOT / "eval" / "reports"
EHR_SCORE_SPLIT = "holdout"                 # the split eval/run.py reports untuned numbers on

STAGE_PHASES = {"load": "Phase 1", "resolve": "Phase 2", "rules": "Phase 3", "output": "Phase 6"}
COLLAPSE_PHASE = "Phase 5"                  # the clinician view's collapse, explain/prioritise.py
FATIGUE_MAX_LINES = 12                      # demo patients must fit on one screen
EGFR_PAIR_HIGH = 80                         # the pair's well-kidney patient: eGFR nearest this
NO_ISSUE_MIN_MEDICINES = 6                  # "stays quiet" means something only on a long list

# KDIGO eGFR categories, for display only (the kidney gauge and the queue histogram). The renal
# alerts never use these: they use each drug's own tiers from renal_rules.csv.
EGFR_STAGES = (("G1", 90, None, "normal or high"), ("G2", 60, 90, "mildly decreased"),
               ("G3a", 45, 60, "mildly to moderately decreased"), ("G3b", 30, 45, "moderately to severely decreased"),
               ("G4", 15, 30, "severely decreased"), ("G5", 0, 15, "kidney failure"))
CONFIDENCE_BINS = tuple(round(0.40 + 0.05 * i, 2) for i in range(13))     # 0.40 .. 1.00
METHOD_GROUPS = {"exact": "exact", "synonym": "exact", "parts": "approximate", "prefix": "approximate",
                 "fuzzy": "approximate", "abstained": "abstained"}


# ---- per patient -------------------------------------------------------------------------------

def combination_kind(resolution: Resolution) -> str | None:
    """``brand`` for a product that hides several generics, ``written`` for one written as parts
    ("ibuprofen + paracetamol"), None for a single generic or nothing."""
    if len(resolution.generics) < 2:
        return None
    return "written" if resolution.method == "parts" else "brand"


def medication_view(raw: str, index: int, resolution: Resolution,
                    truth_generics: frozenset[str] | None, truth_kind: str | None,
                    status: str | None = None) -> dict[str, Any]:
    """One written line: as written, what the pipeline resolved it to, whether the rules counted
    it (``status``: active, stopped, not_a_medicine, unresolved), and (train only) the label.

    The label fields are read by the Resolution screen only, never the patient screen.
    """
    return {
        "index": index,
        "raw": raw,
        "status": status,
        "generics": list(resolution.generics),
        "method": resolution.method,
        "confidence": round(resolution.confidence, 4),
        "abstain_reason": resolution.abstain_reason,
        "candidates": ([[g, round(s, 4)] for g, s in resolution.candidates]
                       if resolution.verify_manually else []),
        "combination": combination_kind(resolution),
        "truth": None if truth_generics is None else _truth_view(resolution, truth_generics, truth_kind),
    }


def _truth_view(resolution: Resolution, generics: frozenset[str], kind: str | None) -> dict[str, Any]:
    """The label for one line: whether the pipeline matched it, and the true generics if not."""
    match = frozenset(resolution.generics) == generics
    return {"match": match, "kind": kind, **({} if match else {"generics": sorted(generics)})}


def alert_key(finding: Finding) -> str:
    """How the audit log names an alert: ``issue_type:drug;drug`` (medsafe.workflow.AuditEvent)."""
    return f"{finding.issue_type}:{';'.join(finding.drugs)}"


def reasons(finding: Finding) -> list[str]:
    """The patient values and table rows behind one finding, in plain words, from its evidence."""
    evidence = finding.evidence
    out = []
    if finding.issue_type == "renal_dose":
        out.append(f"Patient eGFR {evidence['egfr']:g} is below {evidence['egfr_below']}.")
    elif finding.issue_type == "interaction" and evidence.get("mechanism"):
        out.append(evidence["mechanism"])
    elif finding.issue_type == "duplicate_therapy":
        out.append(f"Written on {len(evidence.get('entries', []))} lines"
                   + (f", duplicate group {evidence['group']}" if evidence.get("group") else "") + ".")
    elif finding.issue_type == "contraindication" and evidence.get("because"):
        out.append(f"Because: {evidence['because']}.")
    if finding.raw_drugs:
        out.append("As written: " + " | ".join(f'"{r}"' for r in finding.raw_drugs))
    return out


def alert_view(rank: int, finding: Finding, patient: Patient, regimen: Regimen) -> dict[str, Any]:
    """One Medsafe finding as the patient screen shows it: the table's severity and action,
    the evidence, and the confidence-and-limitations text the pack requires."""
    if finding.issue_type == "duplicate_therapy" and finding.evidence.get("entries"):
        entries = sorted(finding.evidence["entries"])
    else:
        entries = sorted({e.index for e in regimen.entries
                          if e.active and set(e.generics) & set(finding.drugs)})
    return {
        "rank": rank,
        "key": alert_key(finding),
        "issue_type": finding.issue_type,
        "severity": finding.severity,
        "drugs": list(finding.drugs),
        "suggested_action": finding.action,
        "confidence": round(finding.confidence, 4),
        "rule_id": finding.rule_id,
        "reasons": reasons(finding),
        "limitations": alert_limitations(finding, patient, regimen),
        "entries": entries,
        "tier": ({"egfr_below": finding.evidence["egfr_below"], "severity": finding.severity}
                 if finding.issue_type == "renal_dose" else None),
        "submitted": bool(submitted([{"severity": finding.severity}])),
    }


def medsafe_view(result: PatientResult) -> dict[str, Any]:
    """What the pipeline found beyond names, ordered and collapsed by the clinician layer.

    ``alerts`` is every finding, minor included, in ``prioritise`` order. ``actions`` is what a
    prescriber is asked to do: the collapse first, when one drug clears two or more serious
    interactions, then every other alert that is submitted. Minor alerts stay in ``alerts``,
    marked not submitted, and are shown last. A stage that is not built exports as null.
    """
    if result.findings is None or result.rules is None:
        return {"alerts": None, "actions": None, "collapse": None, "suppressed": None,
                "summary": None, "not_checked": None}
    patient, regimen = result.patient, result.rules.regimen
    ordered = prioritise(result.findings)
    alerts = [alert_view(i + 1, f, patient, regimen) for i, f in enumerate(ordered)]
    chosen = collapse_findings(result.findings)
    cleared = set(chosen.cleared) if chosen else set()
    actions: list[dict[str, Any]] = []
    if chosen:
        actions.append({"kind": "collapse", "summary": chosen.summary, "drugs": list(chosen.drugs),
                        "covers": [a["rank"] for a, f in zip(alerts, ordered)
                                   if f.issue_type == "interaction" and f.drugs in cleared]})
    covered = set(actions[0]["covers"]) if actions else set()
    actions += [{"kind": "alert", "rank": a["rank"]} for a in alerts
                if a["submitted"] and a["rank"] not in covered]
    interactions = [f for f in result.findings if f.issue_type == "interaction"]
    return {
        "alerts": alerts,
        "actions": actions,
        "collapse": {
            "chosen": list(chosen.drugs) if chosen else [],
            "summary": chosen.summary if chosen else None,
            "total": chosen.total if chosen else sum(1 for f in interactions if f.severity in SERIOUS),
            "nodes": sorted({d for f in interactions for d in f.drugs}),
            "edges": [{"a": f.drugs[0], "b": f.drugs[1], "severity": f.severity,
                       "cleared": f.drugs in cleared} for f in interactions],
        },
        "suppressed": sum(1 for a in alerts if not a["submitted"]),
        "summary": patient_summary(patient, regimen, len(result.alerts or ())),
        "not_checked": list(not_checked(patient, regimen)),
    }


def egfr_tier(view: dict[str, Any]) -> dict[str, Any] | None:
    """The renal tier behind the most severe renal alert, for the header; None if none fired."""
    renal = [a for a in view["alerts"] or () if a["issue_type"] == "renal_dose"]
    if not renal:
        return None
    top = min(renal, key=lambda a: (SEVERITIES.index(a["severity"]), a["tier"]["egfr_below"], a["drugs"]))
    return {"generic": top["drugs"][0], **top["tier"]}


def ehr_alert_view(alert: EhrAlert) -> dict[str, Any]:
    """One standard-check alert, as the EHR mode draws it."""
    return {"issue_type": alert.issue_type, "severity": alert.severity, "drugs": list(alert.drugs),
            "entries": list(alert.entries), "source": alert.source, "effect": alert.effect,
            "action": alert.action}


def egfr_stage(egfr: float | None) -> str | None:
    """The KDIGO category of an eGFR, for display only; None when eGFR is not recorded."""
    if egfr is None:
        return None
    return next(code for code, low, _, _ in EGFR_STAGES if egfr >= low)


def top_severity(medsafe: dict[str, Any]) -> str:
    """The most severe submitted alert's severity, or "none" when nothing was submitted."""
    submitted = [a["severity"] for a in medsafe["alerts"] if a["submitted"]]
    return min(submitted, key=SEVERITIES.index) if submitted else "none"


def comparison(patient: Patient, resolutions: Sequence[Resolution], ehr: EhrResult,
               medsafe: dict[str, Any]) -> dict[str, Any]:
    """The header strip: what each checker did with the same list, counted here, not in the UI."""
    unrecognised = [r for e, r in zip(ehr.entries, resolutions)
                    if e.generic is None and r.method != "non_drug"]
    brand_combinations = [(e, r) for e, r in zip(ehr.entries, resolutions)
                          if combination_kind(r) == "brand"]
    severities = Counter(a.severity for a in ehr.alerts)
    return {
        "ehr": {
            "alerts": len(ehr.alerts),
            "by_severity": {s: severities.get(s, 0) for s in SEVERITIES},
            "not_in_formulary": len(unrecognised),
            "combinations_unexpanded": sum(1 for e, r in brand_combinations
                                           if set(r.generics) - {e.generic}),
            "egfr_read": False,
        },
        "medsafe": {
            "lines": len(patient.medications),
            "medicines": sum(1 for r in resolutions if r.method != "non_drug"),
            "checked": sum(1 for r in resolutions if r.generics),
            "dropped": len(patient.medications) - len(resolutions),
            "to_verify": sum(1 for r in resolutions if r.verify_manually),
            "combinations_expanded": len(brand_combinations),
            "actions": None if medsafe["actions"] is None else len(medsafe["actions"]),
            "egfr": patient.egfr,
            "egfr_tier": None if medsafe["alerts"] is None else egfr_tier(medsafe),
            "egfr_stage": egfr_stage(patient.egfr),
            "findings": None if medsafe["alerts"] is None else len(medsafe["alerts"]),
            "submitted": None if medsafe["alerts"] is None else sum(a["submitted"] for a in medsafe["alerts"]),
            "top_severity": None if medsafe["alerts"] is None else top_severity(medsafe),
        },
    }


def patient_view(result: PatientResult, ehr: EhrResult,
                 truth: Mapping[str, tuple[frozenset[str], str]] | None) -> dict[str, Any]:
    """Everything the UI shows for one patient.

    Args:
        result: The pipeline's result for this patient.
        ehr: The standard check's result for this patient.
        truth: Token key -> (true generics, token kind) for this patient's lines, or None.
    """
    patient = result.patient
    resolutions = result.resolutions or ()
    status = {e.index: e.status for e in result.rules.regimen.entries} if result.rules else {}
    medications = []
    for entry, resolution in zip(patient.medications, resolutions):
        label = truth.get(token_key(entry.raw)) if truth is not None else None
        medications.append(medication_view(entry.raw, entry.index, resolution,
                                           label[0] if label else None, label[1] if label else None,
                                           status.get(entry.index)))
    medsafe = medsafe_view(result)
    return {
        "id": patient.patient_id,
        "age": patient.age,
        "sex": patient.sex,
        "weight_kg": patient.weight_kg,
        "egfr": patient.egfr,
        "pregnant": patient.pregnant,
        "diagnoses": list(patient.diagnoses),
        "allergies": patient.allergies,
        "prescriber_count": patient.prescriber_count,
        "unreadable_fields": list(patient.unreadable_fields),
        "notes": list(result.notes),
        "medications": medications,
        "medsafe": medsafe,
        "ehr": {"matched": [e.generic for e in ehr.entries],
                "alerts": [ehr_alert_view(a) for a in ehr.alerts]},
        "compare": comparison(patient, resolutions, ehr, medsafe),
    }


# ---- demo patients -----------------------------------------------------------------------------

class TruthIndex:
    """The training labels, indexed for choosing demo patients."""

    def __init__(self, truth: Truth):
        self.issues: dict[str, list[Any]] = {}
        for issue in truth.issues:
            self.issues.setdefault(issue.patient_id, []).append(issue)
        self.tokens: dict[str, dict[str, tuple[frozenset[str], str]]] = {}
        for token in truth.tokens:
            self.tokens.setdefault(token.patient_id, {})[token_key(token.written_token)] = (
                token.generics, token.token_kind)

    def line_generics(self, patient: Patient) -> list[frozenset[str]]:
        """The true generics of each written line, in list order (empty if unlabelled)."""
        tokens = self.tokens.get(patient.patient_id, {})
        return [tokens.get(token_key(m.raw), (frozenset(), ""))[0] for m in patient.medications]


def _label(issue: Any) -> dict[str, Any]:
    """A training label as the demo cards show it: the answer key, never Medsafe's output."""
    return {"issue_type": issue.issue_type, "severity": issue.severity,
            "drugs": sorted(issue.drugs), "near_miss": issue.near_miss}


def _raised_by(result: EhrResult, issue: Any) -> int | None:
    """Index of the standard-check alert that raises ``issue`` (same type and drugs), or None."""
    for i, alert in enumerate(result.alerts):
        if alert.issue_type == issue.issue_type and frozenset(alert.drugs) == issue.drugs:
            return i
    return None


def _rank(issue: Any) -> int:
    """Severity rank: 0 is most severe."""
    return SEVERITIES.index(issue.severity)


def pick_brand_chaos(patients: Sequence[Patient], ehr: Mapping[str, EhrResult],
                     labels: TruthIndex) -> dict[str, Any] | None:
    """One medicine written on several lines in different words, which the standard check misses.

    A labelled same-generic duplicate whose every line is that generic alone (a combination is
    the hidden-generic card), where the standard check recognised at most one of the lines, so
    it cannot see the duplicate. Most lines first, then most severe, then shortest list.
    """
    candidates = []
    for patient in patients:
        lines = labels.line_generics(patient)
        for issue in labels.issues.get(patient.patient_id, []):
            if issue.issue_type != "duplicate_therapy" or len(issue.drugs) != 1:
                continue
            generic = next(iter(issue.drugs))
            alone = [i for i, g in enumerate(lines) if g == {generic}]
            anywhere = [i for i, g in enumerate(lines) if generic in g]
            seen = [i for i in alone if ehr[patient.patient_id].entries[i].generic == generic]
            if len(alone) >= 2 and alone == anywhere and len(seen) <= 1:
                candidates.append(((-len(alone), _rank(issue), len(lines), patient.patient_id),
                                   {"patient_id": patient.patient_id, "generic": generic,
                                    "lines": alone, "label": _label(issue),
                                    "ehr_alert": _raised_by(ehr[patient.patient_id], issue)}))
    return min(candidates, key=lambda c: c[0])[1] if candidates else None


def pick_hidden_generic(patients: Sequence[Patient], ehr: Mapping[str, EhrResult],
                        labels: TruthIndex) -> dict[str, Any] | None:
    """A combination brand hiding a generic the patient also takes on another line.

    A labelled same-generic duplicate where one line is a combination containing it and the
    standard check did not see the generic on that line. Prefers cases the standard check misses
    entirely, then most severe, then shortest list.
    """
    candidates = []
    for patient in patients:
        lines = labels.line_generics(patient)
        result = ehr[patient.patient_id]
        for issue in labels.issues.get(patient.patient_id, []):
            if issue.issue_type != "duplicate_therapy" or len(issue.drugs) != 1:
                continue
            generic = next(iter(issue.drugs))
            combos = [i for i, g in enumerate(lines) if generic in g and len(g) > 1
                      and result.entries[i].generic != generic]
            others = [i for i, g in enumerate(lines) if generic in g and i not in combos]
            if not combos or not others:
                continue
            raised = _raised_by(result, issue)
            candidates.append(((raised is not None, _rank(issue), len(lines), patient.patient_id),
                               {"patient_id": patient.patient_id, "generic": generic,
                                "combination_lines": combos, "other_lines": others,
                                "label": _label(issue), "ehr_alert": raised}))
    return min(candidates, key=lambda c: c[0])[1] if candidates else None


def _strength(raw: str) -> str | None:
    """The first number written on a line ("Glyciphage 500 SR bd" -> "500"), or None."""
    match = re.search(r"\d+(?:\.\d+)?", raw)
    return match.group(0) if match else None


def _first_name_word(raw: str) -> str | None:
    """The first name word of a line, lowercased ("T. Glyciphage 500" -> "glyciphage"), or None."""
    words = name_words(raw)
    return words[0].lower() if words else None


def pick_egfr_pair(patients: Sequence[Patient], dataset: Dataset, ehr: Mapping[str, EhrResult],
                   labels: TruthIndex) -> dict[str, Any] | None:
    """The same drug at the same written strength in two patients either side of its renal tiers.

    Drugs are tried in order of how many renal labels they carry. The low patient has a label at
    the drug's most restrictive tier; the high patient has the drug, a recorded eGFR at or above
    every tier, and no renal label for it. Pairs written with the same name and strength win,
    then the high eGFR nearest ``EGFR_PAIR_HIGH``, then the low eGFR nearest its threshold.
    """
    tiers: dict[str, list[Any]] = {}
    for rule in dataset.renal_rules:
        if rule.egfr_below is not None:
            tiers.setdefault(rule.generic, []).append(rule)
    renal_labels = Counter(next(iter(i.drugs)) for issues in labels.issues.values()
                           for i in issues if i.issue_type == "renal_dose")
    by_id = {p.patient_id: p for p in patients}

    def single_line(patient: Patient, generic: str) -> int | None:
        lines = [i for i, g in enumerate(labels.line_generics(patient)) if g == {generic}]
        return lines[0] if len(lines) == 1 else None

    for generic, _ in sorted(renal_labels.items(), key=lambda kv: (-kv[1], kv[0])):
        ladder = sorted(tiers.get(generic, []), key=lambda r: r.egfr_below)
        if not ladder:
            continue
        lowest, highest = ladder[0], ladder[-1]
        low, high = [], []
        for pid, issues in labels.issues.items():
            for issue in issues:
                if (issue.issue_type == "renal_dose" and issue.drugs == {generic}
                        and issue.severity == lowest.severity and pid in by_id):
                    line = single_line(by_id[pid], generic)
                    if line is not None and by_id[pid].egfr is not None:
                        low.append((by_id[pid], line))
        for patient in patients:
            labelled = any(i.issue_type == "renal_dose" and generic in i.drugs
                           for i in labels.issues.get(patient.patient_id, []))
            line = single_line(patient, generic)
            if (line is not None and not labelled and patient.egfr is not None
                    and patient.egfr >= highest.egfr_below):
                high.append((patient, line))
        pairs = []
        for lp, ll in low:
            for hp, hl in high:
                raw_l, raw_h = lp.medications[ll].raw, hp.medications[hl].raw
                same_name = _first_name_word(raw_l) is not None and _first_name_word(raw_l) == _first_name_word(raw_h)
                same_strength = _strength(raw_l) is not None and _strength(raw_l) == _strength(raw_h)
                pairs.append(((not (same_name and same_strength), not same_strength,
                               abs(hp.egfr - EGFR_PAIR_HIGH), lowest.egfr_below - lp.egfr,
                               lp.patient_id, hp.patient_id),
                              (lp, ll, hp, hl)))
        if pairs:
            lp, ll, hp, hl = min(pairs, key=lambda p: p[0])[1]
            label = next(i for i in labels.issues[lp.patient_id]
                         if i.issue_type == "renal_dose" and i.drugs == {generic})
            return {"generic": generic,
                    "low": {"patient_id": lp.patient_id, "line": ll, "egfr": lp.egfr,
                            "ehr_alert": _raised_by(ehr[lp.patient_id], label)},
                    "high": {"patient_id": hp.patient_id, "line": hl, "egfr": hp.egfr,
                             "ehr_alert": _raised_by(ehr[hp.patient_id], label)},
                    "ladder": [{"egfr_below": r.egfr_below, "severity": r.severity, "action": r.action}
                               for r in ladder],
                    "label": _label(label)}
    return None


def pick_collapse_hero(patients: Sequence[Patient], labels: TruthIndex) -> dict[str, Any] | None:
    """The patient whose serious labelled interactions most share one drug.

    Chosen from the labels until the collapse (Phase 5) exists, so the choice does not depend on
    how well Medsafe does on the patient. At most ``FATIGUE_MAX_LINES`` lines if any qualifies.
    """
    candidates = []
    for patient in patients:
        serious = [i for i in labels.issues.get(patient.patient_id, [])
                   if i.issue_type == "interaction" and i.severity in SERIOUS]
        if len(serious) < 3:
            continue
        hubs = Counter(d for i in serious for d in i.drugs)
        hub, degree = min(hubs.items(), key=lambda kv: (-kv[1], kv[0]))
        too_long = len(patient.medications) > FATIGUE_MAX_LINES
        candidates.append(((too_long, -degree, -len(serious), len(patient.medications),
                            patient.patient_id),
                           {"patient_id": patient.patient_id, "hub": hub, "hub_serious": degree,
                            "serious_interactions": len(serious)}))
    return min(candidates, key=lambda c: c[0])[1] if candidates else None


def pick_alert_fatigue(patients: Sequence[Patient], ehr: Mapping[str, EhrResult],
                       labels: TruthIndex) -> dict[str, Any] | None:
    """The loudest standard screen that still misses serious labelled issues.

    Most standard-check alerts first, then most serious labelled issues absent from those
    alerts, then shortest list. Only patients with at least one serious issue the check missed:
    the card is about the serious one being lost in the noise, so it has to be lost.
    """
    candidates = []
    for patient in patients:
        alerts = ehr[patient.patient_id].alerts
        raised = {(a.issue_type, frozenset(a.drugs)) for a in alerts}
        serious = [i for i in labels.issues.get(patient.patient_id, []) if i.severity in SERIOUS]
        missed = [i for i in serious if (i.issue_type, i.drugs) not in raised]
        if missed:
            candidates.append(((-len(alerts), -len(missed), len(patient.medications), patient.patient_id),
                               {"patient_id": patient.patient_id, "ehr_alerts": len(alerts),
                                "serious_labelled": len(serious),
                                "serious_raised": len(serious) - len(missed),
                                "missed": [_label(i) for i in sorted(missed, key=lambda i: (_rank(i), sorted(i.drugs)))]}))
    return min(candidates, key=lambda c: c[0])[1] if candidates else None


def pick_abstention(results: Sequence[PatientResult]) -> dict[str, Any] | None:
    """The patient with the most lines the resolver would not guess, then the shortest list."""
    candidates = [((-n, len(r.resolutions), r.patient.patient_id),
                   {"patient_id": r.patient.patient_id, "lines": [i for i, x in enumerate(r.resolutions)
                                                                  if x.verify_manually]})
                  for r in results if r.resolutions
                  for n in [sum(1 for x in r.resolutions if x.verify_manually)] if n]
    return min(candidates, key=lambda c: c[0])[1] if candidates else None


def pick_no_issue(patients: Sequence[Patient], labels: TruthIndex) -> dict[str, Any] | None:
    """A long list with no labelled issue at all: the case where a checker should stay quiet.

    At least ``NO_ISSUE_MIN_MEDICINES`` lines that are medicines, eGFR recorded; most medicines
    first, older patients first, then patient id.
    """
    candidates = []
    for patient in patients:
        if labels.issues.get(patient.patient_id) or patient.egfr is None:
            continue
        medicines = sum(1 for g in labels.line_generics(patient) if g)
        if medicines >= NO_ISSUE_MIN_MEDICINES:
            candidates.append(((-medicines, -(patient.age or 0), patient.patient_id),
                               {"patient_id": patient.patient_id, "medicines": medicines}))
    return min(candidates, key=lambda c: c[0])[1] if candidates else None


def demo_view(result: PipelineResult, dataset: Dataset, ehr: Mapping[str, EhrResult],
              labels: TruthIndex) -> dict[str, Any]:
    """The pinned demo patients and the four /why cards."""
    patients = [r.patient for r in result.patients]
    hero = pick_collapse_hero(patients, labels)
    pair = pick_egfr_pair(patients, dataset, ehr, labels)
    hidden = pick_hidden_generic(patients, ehr, labels)
    abstention = pick_abstention(result.patients)
    quiet = pick_no_issue(patients, labels)
    pins = [
        {"slot": "collapse_hero", "patient_ids": [hero["patient_id"]] if hero else [],
         "basis": "labels", "why": hero and (f"{hero['serious_interactions']} serious labelled "
                                             f"interactions, {hero['hub_serious']} of them with {hero['hub']}")},
        {"slot": "egfr_pair", "patient_ids": [pair["low"]["patient_id"], pair["high"]["patient_id"]] if pair else [],
         "basis": "labels", "why": pair and (f"{pair['generic']} at eGFR {pair['low']['egfr']:g} "
                                             f"and eGFR {pair['high']['egfr']:g}")},
        {"slot": "combination_duplicate", "patient_ids": [hidden["patient_id"]] if hidden else [],
         "basis": "labels", "why": hidden and f"{hidden['generic']} inside a combination brand and on its own line"},
        {"slot": "abstention", "patient_ids": [abstention["patient_id"]] if abstention else [],
         "basis": "pipeline", "why": abstention and f"{len(abstention['lines'])} line(s) the resolver would not guess"},
        {"slot": "no_issue", "patient_ids": [quiet["patient_id"]] if quiet else [],
         "basis": "labels", "why": quiet and f"{quiet['medicines']} medicines, no labelled issue"},
    ]
    cards = {"brand_chaos": pick_brand_chaos(patients, ehr, labels), "hidden_generic": hidden,
             "egfr_pair": pair, "alert_fatigue": pick_alert_fatigue(patients, ehr, labels)}
    # Which Medsafe alert raises each card's labelled issue, by index into that patient's alerts,
    # matched here so the UI never matches alerts to labels itself.
    by_id = {r.patient.patient_id: r for r in result.patients}
    for card in (cards["brand_chaos"], cards["hidden_generic"]):
        if card:
            card["medsafe_alert"] = medsafe_alert(by_id[card["patient_id"]], card["label"])
    if pair:
        for side in (pair["low"], pair["high"]):
            side["medsafe_alert"] = medsafe_alert(by_id[side["patient_id"]], pair["label"],
                                                  drugs_only=True)
    return {"pins": pins, "cards": cards}


def medsafe_alert(result: PatientResult, label: dict[str, Any], drugs_only: bool = False) -> int | None:
    """Index into the patient's prioritised alerts of the one raising a labelled issue, or None.

    ``drugs_only`` matches the issue type and drugs whatever the severity: the eGFR pair asks
    whether a renal alert fired on each patient at all.
    """
    if result.findings is None:
        return None
    for i, finding in enumerate(prioritise(result.findings)):
        if finding.issue_type == label["issue_type"] and sorted(finding.drugs) == label["drugs"]:
            return i
    return None


# ---- cohort-level numbers ----------------------------------------------------------------------

def workflow_view(dataset: Dataset) -> dict[str, Any]:
    """Who may do and enter what, the override reasons, and the disclaimer, from medsafe.workflow
    and medsafe.explain.limitations. The portal enforces these; it defines none of them."""
    return {"roles": list(workflow.ROLES), "events": list(workflow.EVENTS),
            "permissions": {r: list(p) for r, p in workflow.PERMISSIONS.items()},
            "entries": {r: list(e) for r, e in workflow.ENTRIES.items()},
            "override_reasons": list(workflow.OVERRIDE_REASONS), "disclaimer": DISCLAIMER,
            "generics": sorted(dataset.drugs)}


def resolution_summary(result: PipelineResult, patients: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """How every exported line was resolved, counted once here so the UI never counts.

    ``label_mismatches`` counts lines whose resolution differs from the training label; None
    without labels.
    """
    resolutions = [r for p in result.patients for r in (p.resolutions or ())]
    methods = Counter(r.method for r in resolutions)
    labelled = [m["truth"] for p in patients for m in p["medications"] if m["truth"] is not None]
    return {"lines": len(resolutions), "by_method": dict(sorted(methods.items())),
            "brand_combinations": sum(1 for r in resolutions if combination_kind(r) == "brand"),
            "patients_with_lines_to_verify": sum(1 for p in result.patients
                                                 if any(r.verify_manually for r in p.resolutions or ())),
            "label_mismatches": sum(1 for t in labelled if not t["match"]) if labelled else None}


def cohort_view(patients: Sequence[dict[str, Any]], ehr: Mapping[str, EhrResult]) -> dict[str, Any]:
    """Cohort figures for the queue overview and the evaluation charts, counted here so the UI
    never counts: the queue order, severity per patient, eGFR categories, alert totals by
    severity for the standard check and for Medsafe, and how confident each name match was."""
    n = max(len(patients), 1)
    built = all(p["medsafe"]["alerts"] is not None for p in patients)
    order = sorted(patients, key=lambda p: (
        (SEVERITIES + ("none",)).index(p["compare"]["medsafe"]["top_severity"] or "none"),
        -(p["compare"]["medsafe"]["actions"] or 0), p["id"])) if built else patients
    egfr = Counter(p["compare"]["medsafe"]["egfr_stage"] for p in patients)
    ehr_sev = Counter(a.severity for r in ehr.values() for a in r.alerts)
    ms_sev = Counter(a["severity"] for p in patients for a in p["medsafe"]["alerts"] or () if a["submitted"])
    bins: dict[str, list[int]] = {g: [0] * (len(CONFIDENCE_BINS) - 1) for g in ("exact", "approximate", "abstained")}
    below: Counter = Counter()
    for p in patients:
        for m in p["medications"]:
            group = METHOD_GROUPS.get(m["method"])
            if group is None:
                continue
            if m["confidence"] < CONFIDENCE_BINS[0]:
                below[group] += 1
                continue
            k = min(int((m["confidence"] - CONFIDENCE_BINS[0]) / 0.05 + 1e-9), len(CONFIDENCE_BINS) - 2)
            bins[group][k] += 1
    return {
        "queue_order": [p["id"] for p in order],
        "by_top_severity": dict(Counter(p["compare"]["medsafe"]["top_severity"] for p in patients)) if built else None,
        "egfr_stages": [{"code": c, "from": low, "to": high, "label": label, "patients": egfr.get(c, 0)}
                        for c, low, high, label in EGFR_STAGES] + [{"code": None, "label": "not recorded", "patients": egfr.get(None, 0)}],
        "totals": {"patients": len(patients), "ehr_alerts": sum(len(r.alerts) for r in ehr.values()),
                   "medsafe_findings": sum(p["compare"]["medsafe"]["findings"] or 0 for p in patients),
                   "medsafe_submitted": sum(p["compare"]["medsafe"]["submitted"] or 0 for p in patients),
                   "medsafe_actions": sum(p["compare"]["medsafe"]["actions"] or 0 for p in patients),
                   "lines_to_verify": sum(p["compare"]["medsafe"]["to_verify"] for p in patients)},
        "per_patient_by_severity": {s: {"ehr": round(ehr_sev.get(s, 0) / n, 3), "medsafe": round(ms_sev.get(s, 0) / n, 3)}
                                    for s in SEVERITIES},
        "confidence_histogram": {"edges": list(CONFIDENCE_BINS), "below_first": dict(below), "counts": bins},
    }


def ehr_cohort_stats(ehr: Mapping[str, EhrResult]) -> dict[str, Any]:
    """How loud the standard check is across the exported patients."""
    alerts = [a for r in ehr.values() for a in r.alerts]
    patients = max(len(ehr), 1)
    severities = Counter(a.severity for a in alerts)
    lines = [e for r in ehr.values() for e in r.entries]
    return {"patients": len(ehr), "alerts": len(alerts),
            "alerts_per_patient": round(len(alerts) / patients, 3),
            "alerts_per_patient_by_severity": {s: round(severities.get(s, 0) / patients, 3)
                                               for s in SEVERITIES},
            "lines": len(lines), "lines_not_in_formulary": sum(1 for e in lines if e.generic is None)}


def score_ehr_reference(dataset: Dataset, ehr: Mapping[str, EhrResult],
                        split: str = EHR_SCORE_SPLIT) -> dict[str, Any]:
    """Score the standard-check reproduction with the organisers' evaluate.py, on ``split``.

    The same scorer, truth subset and split as eval/run.py, so its numbers sit next to
    Medsafe's. Returns ``{"split", "official"}``, or ``{"split", "unavailable": reason}`` when
    the scorer cannot run here (it needs pandas and numpy).
    """
    from eval import official
    from eval.split import split_ids
    from eval.truth import write_truth_subset

    if not official.scorer_available():
        return {"split": split, "unavailable": "the official scorer needs the H4 pack, pandas and numpy"}
    ids = split_ids((p.patient_id for p in dataset.patients), split)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        predictions, resolution = folder / "H4_predictions.csv", folder / "H4_resolution.csv"
        write_submission([ehr[pid] for pid in sorted(ids)], predictions, resolution)
        labels, truth_resolution = write_truth_subset(data_dir(), ids, folder / "truth")
        report = official.score(predictions, resolution, labels, truth_resolution, folder / "score.json")
    return {"split": split, "official": report}


def latest_report(reports_dir: Path = REPORTS_DIR) -> dict[str, Any] | None:
    """The newest eval/reports/*.json in the current format (with ``splits``), copied unchanged.

    Returns ``{"path", "report"}``, or ``{"path": None, "unavailable": reason}`` when there is no
    such report.
    """
    for path in sorted(reports_dir.glob("*.json"), reverse=True):
        report = json.loads(path.read_text(encoding="utf-8"))
        if "splits" in report:
            return {"path": path.relative_to(REPO_ROOT).as_posix(), "report": report}
    return {"path": None, "unavailable": "no evaluation report in the current format; run python -m eval.run"}


def latest_challenger(reports_dir: Path = REPORTS_DIR) -> dict[str, Any] | None:
    """The newest eval/reports/*-ml-challenger.json (python -m eval.ml_challenger), trimmed to what
    the Evaluation screen shows; None if the experiment has not been run."""
    paths = [p for p in sorted(reports_dir.glob("*-ml-challenger.json"), reverse=True)
             if "names" in json.loads(p.read_text(encoding="utf-8"))]
    if not paths:
        return None
    report = json.loads(paths[0].read_text(encoding="utf-8"))
    names, conditions, triage = report["names"], report["conditions"], report["triage"]
    brief = lambda o: {"primary_score": o["primary_score"], "components": o["components"],  # noqa: E731
                       "contraindication": o["per_issue_type"]["contraindication"]}
    return {"path": paths[0].relative_to(REPO_ROOT).as_posix(), "generated_at": report.get("generated_at"),
            "names": {"thresholds": names["thresholds"], "training_lines": names["training_lines"],
                      "holdout_patients": names["holdout_patients"],
                      "submissions": {n: {**brief(s["official"]), "lines": s["lines"]}
                                      for n, s in names["submissions"].items()}},
            "conditions": {k: conditions[k] for k in ("examples", "present", "threshold", "cv_f1", "folds", "pairs")}
                          | {"official": {n: brief(o) for n, o in conditions["official"].items()}},
            "triage": {k: triage[k] for k in ("training_alerts", "worth_showing", "threshold", "holdout_alerts",
                                              "holdout_auc", "held_back", "held_back_worth_showing", "importance")}
                      | {"official": {n: brief(o) for n, o in triage["official"].items()}}}


# ---- the file ----------------------------------------------------------------------------------

def build_export(dataset: Dataset, result: PipelineResult, truth: Truth | None,
                 reports_dir: Path = REPORTS_DIR, score_ehr: bool = True) -> dict[str, Any]:
    """Assemble the UI data file.

    Args:
        dataset: The loaded patients and reference tables.
        result: ``run_pipeline`` over ``dataset``.
        truth: The training labels for these patients; None for the test split, which has no
            demo cards and no label column.
        reports_dir: Where eval/run.py writes its reports.
        score_ehr: Also score the standard-check reproduction with the official scorer.

    Returns:
        A JSON-serialisable dict, schema ``SCHEMA_VERSION``. Deterministic for a given input,
        pipeline and report.
    """
    ehr = check_all((r.patient for r in result.patients), EhrTables.from_dataset(dataset))
    labels = TruthIndex(truth) if truth is not None else None
    patients = [patient_view(r, ehr[r.patient.patient_id],
                             labels.tokens.get(r.patient.patient_id, {}) if labels else None)
                for r in result.patients]
    evaluation = latest_report(reports_dir)
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {"split": "train" if truth is not None else "test", "patients": len(patients),
                   "generator": "tools/export_ui.py",
                   "command": "python tools/export_ui.py"},
        "stages": [{"id": s, "phase": STAGE_PHASES.get(s), "built": s in result.stages_built}
                   for s in STAGES] + [{"id": "collapse", "phase": COLLAPSE_PHASE,
                                    "built": "rules" in result.stages_built}],
        "settings": {k: v for k, v in vars(result.settings).items()},
        "patients": patients,
        "workflow": workflow_view(dataset),
        "resolution": resolution_summary(result, patients),
        "cohort": cohort_view(patients, ehr),
        "demo": demo_view(result, dataset, ehr, labels) if labels else None,
        "ehr_reference": {"cohort": ehr_cohort_stats(ehr),
                          "score": score_ehr_reference(dataset, ehr) if score_ehr and truth is not None else None},
        "evaluation": evaluation,
        "ml_challenger": latest_challenger(reports_dir),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line: ``--input`` (the pack's data folder), ``--split``, ``--output``."""
    parser = argparse.ArgumentParser(description="Write the demo UI's data file from pipeline output.")
    parser.add_argument("--input", type=Path, default=data_dir(), help="the pack's data folder")
    parser.add_argument("--split", choices=("train", "test"), default="train")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-ehr-score", action="store_true",
                        help="skip scoring the standard-check reproduction with evaluate.py")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the pipeline and write the UI data file. Returns 0."""
    args = parse_args(argv)
    dataset = load_dataset(args.input, args.split)
    result = run_pipeline(dataset)
    truth = load_truth(args.input, {p.patient_id for p in dataset.patients}) if args.split == "train" else None
    export = build_export(dataset, result, truth, score_ehr=not args.no_ehr_score)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(export, ensure_ascii=False, separators=(",", ":")) + "\n",
                           encoding="utf-8")
    pins = {p["slot"]: p["patient_ids"] for p in export["demo"]["pins"]} if export["demo"] else {}
    print(f"patients: {len(export['patients'])}  stages built: {list(result.stages_built)}")
    print(f"standard check: {export['ehr_reference']['cohort']['alerts_per_patient']} alerts per patient")
    for slot, ids in pins.items():
        print(f"pin {slot}: {', '.join(ids) or 'none found'}")
    print(f"evaluation report: {export['evaluation'].get('path') or export['evaluation'].get('unavailable')}")
    print(f"wrote {args.output} ({args.output.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
