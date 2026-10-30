"""What a standard hospital drug-safety check sees on the same list. The demo's comparison, only.

Never on the scoring path: nothing in run.py or src/medsafe/ imports this (tests/test_guards.py).
It exists so the demo UI can put a typical clinical-decision-support (CDS) layer next to
Medsafe on the same patient, built from the same reference tables, without the UI computing
anything (docs/ui-demo.md).

What it reproduces, deliberately and no further:

    match      exact formulary lookup. The name words of a line (dose form, strength and
               frequency stripped, as the pack's baseline/baseline.py does) must equal a
               generic or a single-ingredient brand. Misspellings, abbreviations and
               combination brands are "not in formulary" and silently left out of every check.
    interact   every pair of recognised generics listed in interactions.csv, at the table
               severity, minor included. One alert per pair.
    duplicate  the same generic in two recognised lines, or two recognised generics from one
               duplicate_therapy_groups.csv group, at the group severity (moderate if none).
    renal      one flat warning per recognised drug with renal rules: the most restrictive
               tier's severity and action, whatever the patient's eGFR. eGFR is never read.

Not reproduced: drug-disease and allergy checks (diagnoses and allergies are free text here, and
a CDS layer needs them coded), and pregnancy checks. Leaving them out lowers this checker's
alert count, so the comparison does not inflate the noise it is shown to make.

Deterministic: same tables and list, same alerts, in the same order.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from medsafe.data.adapter import Dataset
from medsafe.output.writer import token_key
from medsafe.data.schema import SEVERITIES, Drug, DuplicateGroup, InteractionPair, Patient, RenalRule

# Copied unchanged from the pack's baseline/baseline.py, so "exact match" means exactly what
# the organisers' honest baseline means by it.
FORM_WORDS = frozenset({"tab", "tab.", "t.", "t", "cap", "cap.", "c.", "inj", "inj.", "syp", "syp.",
                        "syr", "inh", "inh.", "mdi", "rotacap", "sachet", "sach.", "patch", "susp",
                        "drops", "powder", "neb", "respule", "gel"})
STOP_WORDS = frozenset({"od", "bd", "tds", "hs", "sos", "prn", "bid", "tid", "once", "twice", "x",
                        "at", "if", "after", "before", "weekly", "every", "daily", "puffs", "puff",
                        "empty", "ml", "u", "-", "--", "(cont.)"})

DEFAULT_DUPLICATE_SEVERITY = "moderate"     # the pack's rule for a drug with no group
SAME_DRUG_ACTION = "Same medicine listed more than once - keep one source"
ISSUE_ORDER = ("interaction", "duplicate_therapy", "renal_dose")


@dataclass(frozen=True)
class Formulary:
    """Every name the standard check recognises: generics and single-ingredient brands."""

    names: dict[str, str]                  # formulary key -> generic

    @classmethod
    def build(cls, drugs: Mapping[str, Drug]) -> Formulary:
        """Index generic names and their single-ingredient brands. Combination brands are absent."""
        names: dict[str, str] = {}
        for generic in sorted(drugs):
            names.setdefault(formulary_key(generic), generic)
            for brand in drugs[generic].brands:
                names.setdefault(formulary_key(brand), generic)
        names.pop("", None)
        return cls(names)


@dataclass(frozen=True)
class EhrEntry:
    """One written line as the standard check saw it. ``generic`` None: not in formulary."""

    index: int
    raw: str
    generic: str | None


@dataclass(frozen=True)
class EhrAlert:
    """One alert the standard check raises, with the reference row it came from."""

    issue_type: str                        # interaction | duplicate_therapy | renal_dose
    severity: str                          # copied from the table, never re-scored
    drugs: tuple[str, ...]                 # sorted generics
    entries: tuple[int, ...]               # indices of the lines involved
    source: str                            # the table and row that fired
    effect: str | None
    action: str | None


@dataclass(frozen=True)
class EhrResult:
    """The standard check's view of one patient."""

    patient_id: str
    entries: tuple[EhrEntry, ...]
    alerts: tuple[EhrAlert, ...]


@dataclass(frozen=True)
class EhrTables:
    """The reference tables the standard check reads, indexed for lookup."""

    formulary: Formulary
    interactions: dict[tuple[str, str], InteractionPair]
    renal: dict[str, tuple[RenalRule, ...]]            # generic -> tiers, most restrictive first
    groups: dict[str, DuplicateGroup]                  # generic -> its duplicate group

    @classmethod
    def from_dataset(cls, dataset: Dataset) -> EhrTables:
        """Index the dataset's drug, interaction, renal and duplicate-group tables."""
        interactions = {tuple(sorted((row.drug_a, row.drug_b))): row
                        for row in dataset.interactions if row.severity in SEVERITIES}
        renal: dict[str, list[RenalRule]] = {}
        for rule in dataset.renal_rules:
            if rule.egfr_below is not None and rule.severity in SEVERITIES:
                renal.setdefault(rule.generic, []).append(rule)
        groups = {member: group for group in dataset.duplicate_groups.values()
                  for member in group.members}
        return cls(Formulary.build(dataset.drugs), interactions,
                   {g: tuple(sorted(tiers, key=lambda r: (r.egfr_below, r.severity)))
                    for g, tiers in renal.items()},
                   groups)


def formulary_key(text: str) -> str:
    """Lowercase letters and digits only: how the baseline compares names."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def name_words(raw: str) -> list[str]:
    """The name part of a written line: leading dose forms dropped, cut at the first number or
    frequency word. Same rules as the pack's baseline."""
    words = raw.split()
    while words and words[0].lower() in FORM_WORDS:
        words = words[1:]
    name: list[str] = []
    for word in words:
        lower = word.lower()
        if lower in STOP_WORDS or re.match(r"^[0-9]", lower) or re.fullmatch(r"[0-9]-[0-9]-[0-9].*", lower):
            break
        name.append(word)
    return name


def match_line(raw: str, formulary: Formulary) -> str | None:
    """The generic a line names exactly, or None if it is not in the formulary.

    Longest run of name words first, as the baseline does: "Ecosprin AV" is not a formulary
    name, so it matches "Ecosprin" (aspirin) and the atorvastatin inside is never seen.
    """
    words = name_words(raw)
    for n in range(len(words), 0, -1):
        generic = formulary.names.get(formulary_key(" ".join(words[:n])))
        if generic is not None:
            return generic
    return None


def check_patient(patient: Patient, tables: EhrTables) -> EhrResult:
    """Run the standard check on one patient's list as written.

    Args:
        patient: The patient. Only the medication lines are read: no eGFR, age, pregnancy,
            diagnosis or allergy, because this check does not use them.
        tables: The indexed reference tables.

    Returns:
        Every line with what it matched (or None), and every alert, ordered by severity, then
        issue type, then drugs.
    """
    entries = tuple(EhrEntry(m.index, m.raw, match_line(m.raw, tables.formulary))
                    for m in patient.medications)
    lines_of: dict[str, list[int]] = {}
    for entry in entries:
        if entry.generic is not None:
            lines_of.setdefault(entry.generic, []).append(entry.index)
    generics = sorted(lines_of)

    alerts = [*_interactions(generics, lines_of, tables), *_duplicates(generics, lines_of, tables),
              *_renal(generics, lines_of, tables)]
    alerts.sort(key=lambda a: (SEVERITIES.index(a.severity), ISSUE_ORDER.index(a.issue_type), a.drugs))
    return EhrResult(patient.patient_id, entries, tuple(alerts))


def check_all(patients: Iterable[Patient], tables: EhrTables) -> dict[str, EhrResult]:
    """Run the standard check on every patient, keyed by patient id, in input order."""
    return {p.patient_id: check_patient(p, tables) for p in patients}


def write_submission(results: Iterable[EhrResult], predictions: Path, resolution: Path,
                     keep: Callable[[str, EhrAlert], bool] | None = None) -> None:
    """Write the standard check's alerts and name matches as the two submission files.

    Args:
        results: One result per patient.
        predictions: Where H4_predictions.csv goes.
        resolution: Where H4_resolution.csv goes: each line's formulary match, empty if none.
        keep: Write only the alerts this returns True for (patient id, alert); all when None.
    """
    rows = []
    with predictions.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["patient_id", "issue_type", "severity", "drugs_involved", "suggested_action", "confidence"])
        for result in results:
            for alert in result.alerts:
                if keep is None or keep(result.patient_id, alert):
                    writer.writerow([result.patient_id, alert.issue_type, alert.severity, ";".join(alert.drugs),
                                     alert.action or "Review", "1.0"])
            seen: set[str] = set()
            for entry in result.entries:
                if token_key(entry.raw) not in seen:
                    seen.add(token_key(entry.raw))
                    rows.append([result.patient_id, entry.raw, entry.generic or ""])
    with resolution.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["patient_id", "written_token", "resolved_generic"])
        writer.writerows(rows)


def _lines(drugs: Sequence[str], lines_of: Mapping[str, list[int]]) -> tuple[int, ...]:
    """The sorted line indices on which any of ``drugs`` was recognised."""
    return tuple(sorted({i for d in drugs for i in lines_of[d]}))


def _interactions(generics: list[str], lines_of: Mapping[str, list[int]],
                  tables: EhrTables) -> list[EhrAlert]:
    """Every listed pair among the recognised generics, at the table severity."""
    alerts = []
    for pair in combinations(generics, 2):
        row = tables.interactions.get(pair)
        if row is not None:
            alerts.append(EhrAlert("interaction", row.severity, pair, _lines(pair, lines_of),
                                   f"interactions.csv: {pair[0]} + {pair[1]}", row.mechanism, row.action))
    return alerts


def _duplicates(generics: list[str], lines_of: Mapping[str, list[int]],
                tables: EhrTables) -> list[EhrAlert]:
    """One generic on two recognised lines, or two recognised members of one group."""
    alerts = []
    for generic in generics:
        if len(lines_of[generic]) > 1:
            group = tables.groups.get(generic)
            alerts.append(EhrAlert(
                "duplicate_therapy",
                group.severity if group and group.severity in SEVERITIES else DEFAULT_DUPLICATE_SEVERITY,
                (generic,), _lines((generic,), lines_of),
                f"duplicate_therapy_groups.csv: {group.group_id}" if group else "same generic on two lines",
                None, (group.action if group else None) or SAME_DRUG_ACTION))
    for a, b in combinations(generics, 2):
        group = tables.groups.get(a)
        if group is not None and group is tables.groups.get(b) and group.severity in SEVERITIES:
            alerts.append(EhrAlert("duplicate_therapy", group.severity, (a, b), _lines((a, b), lines_of),
                                   f"duplicate_therapy_groups.csv: {group.group_id}", group.name,
                                   group.action))
    return alerts


def _renal(generics: list[str], lines_of: Mapping[str, list[int]], tables: EhrTables) -> list[EhrAlert]:
    """One flat warning per recognised drug with renal rules: the most restrictive tier, always."""
    alerts = []
    for generic in generics:
        tiers = tables.renal.get(generic)
        if tiers:
            top = tiers[0]
            ladder = "; ".join(f"eGFR < {t.egfr_below}: {t.severity}" for t in reversed(tiers))
            alerts.append(EhrAlert("renal_dose", top.severity, (generic,), _lines((generic,), lines_of),
                                   f"renal_rules.csv: {generic}", f"Renal dose adjustment ({ladder})",
                                   top.action))
    return alerts
