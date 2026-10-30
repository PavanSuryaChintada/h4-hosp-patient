"""The only module that knows the real file layout.

Reads the H4 data pack: patients (train or test split) and seven reference tables. Every column
name lives in ``COLUMN_MAP`` and every file name in ``INPUT_FILES``; nothing else in the pipeline
knows either. CSV and JSON are supported, sniffed by file extension.

A row is never dropped for one bad value: the field loads as ``None``, is named in the record's
``unreadable_fields`` and is logged as a degradation. A row is skipped only when it lacks what
makes it a row: a patient with no id, a repeated id, or no medications; a drug with no generic
name; an interaction missing either drug (docs/DECISIONS.md D-001, D-013). Every load is counted
in a ``LoadReport``.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple, TypeVar

from medsafe.data import validate
from medsafe.data.schema import (SEVERITIES, CombinationBrand, Condition, Contraindication,
                                 Drug, DuplicateGroup, InteractionPair, MedicationEntry, Patient,
                                 RenalRule)
from medsafe.data.validate import LoadReport, RowError, SchemaError

# Internal field -> source column name. Map a field to None if the source has no such column;
# it then loads as None. All real column names live here and nowhere else.
COLUMN_MAP: dict[str, dict[str, str | None]] = {
    "patients": {
        "patient_id": "patient_id",
        "age": "age",
        "sex": "sex",
        "weight_kg": "weight_kg",
        "egfr": "egfr_ml_min_1_73m2",
        "pregnant": "pregnant",
        "diagnoses": "diagnoses",
        "allergies": "allergies",
        "medications": "medication_list",
        "prescriber_count": "prescriber_count",
    },
    "drugs": {
        "generic": "generic_name",
        "drug_id": "drug_id",
        "drug_class": "drug_class",
        "therapeutic_group": "therapeutic_group",
        "duplicate_group": "duplicate_group",
        "brands": "common_brands",
        "dose_forms": "dose_forms",
        "usual_daily_dose": "usual_adult_daily_dose_range",
        "max_daily_dose_mg": "max_daily_dose_mg",
        "renal_adjust": "renal_adjustment_flag",
        "renal_rule": "renal_rule",
        "pregnancy_category": "pregnancy_category",
        "notes": "notes",
    },
    "combinations": {
        "brand": "brand_name",
        "strength_label": "strength_label",
        "dose_form": "dose_form",
        "components": "components",
        "generics": "generic_components",
    },
    "interactions": {
        "drug_a": "drug_a",
        "drug_b": "drug_b",
        "severity": "severity",
        "mechanism": "mechanism_effect",
        "action": "recommended_action",
    },
    "renal_rules": {
        "generic": "generic_name",
        "egfr_below": "egfr_below",
        "severity": "severity",
        "action": "recommended_action",
    },
    "duplicate_groups": {
        "group_id": "duplicate_group",
        "name": "group_name",
        "severity": "severity",
        "action": "recommended_action",
        "members": "member_generics",
    },
    "contraindications": {
        "condition_id": "condition_id",
        "condition_name": "condition_name",
        "generic": "generic_name",
        "severity": "severity",
        "reason": "reason",
        "action": "recommended_action",
    },
    "conditions": {
        "condition_id": "condition_id",
        "name": "condition_name",
        "kind": "kind",
        "description": "description",
        "example_terms": "example_terms",
    },
}

# File stem of each table inside the --input directory. ``{split}`` is train or test.
INPUT_FILES: dict[str, str] = {
    "patients": "patients_{split}",
    "drugs": "drug_reference",
    "combinations": "combination_brands",
    "interactions": "interactions",
    "renal_rules": "renal_rules",
    "duplicate_groups": "duplicate_therapy_groups",
    "contraindications": "drug_disease_contraindications",
    "conditions": "conditions",
}
SUPPORTED_EXTENSIONS = (".csv", ".json")
SPLITS = ("train", "test")

# Separates the items of a list held in one reference-table or diagnosis cell.
LIST_SEPARATOR = ";"
# A medication list's entries are separated by ';' or by a line break.
MEDICATION_SEPARATOR = re.compile(r"[;\r\n]")

# Cell contents that mean "no value". Only an empty cell, as the pack README instructs
# (load with keep_default_na=False): a word such as "NA" or "None" is data, not a blank.
MISSING_TOKENS = frozenset({""})

YES_NO = ("Y", "N")
SEXES = ("M", "F")
PREGNANCY_CATEGORIES = ("A", "B", "C", "D", "X", "N")
# The pregnancy column: "NA" is how the pack writes it for male patients, so not applicable.
PREGNANCY_STATUS = {"Y": True, "N": False, "NA": None}

logger = logging.getLogger(__name__)

T = TypeVar("T")


class FieldIssue(NamedTuple):
    """A field that failed validation inside a row that is still being loaded."""

    field: str
    raw_value: Any
    error: RowError


@dataclass(frozen=True)
class Table:
    """A source file read into memory, before any mapping or validation."""

    path: Path
    columns: tuple[str, ...]
    records: list[dict[str, Any]]
    is_csv: bool


@dataclass(frozen=True)
class Dataset:
    """Everything loaded from one input directory, with a load report per file."""

    patients: list[Patient]
    drugs: dict[str, Drug]
    combinations: list[CombinationBrand]
    interactions: list[InteractionPair]
    renal_rules: list[RenalRule]
    duplicate_groups: dict[str, DuplicateGroup]
    contraindications: list[Contraindication]
    conditions: dict[str, Condition]
    reports: tuple[LoadReport, ...]


def read_table(path: str | Path) -> Table:
    """Read a CSV or JSON file into a ``Table``, choosing the parser by extension.

    Args:
        path: File to read. ``.csv`` is read with a header row (quoted cells may hold line
            breaks); ``.json`` must hold a list of objects.

    Returns:
        The columns and raw records, unvalidated.

    Raises:
        SchemaError: Unsupported extension, duplicate CSV header names, or JSON that is not a
            list of objects.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            columns = tuple(reader.fieldnames or ())
            records = list(reader)
        if len(set(columns)) != len(columns):
            raise SchemaError(f"{path}: duplicate column names in header {list(columns)}")
        return Table(path, columns, records, is_csv=True)
    if suffix == ".json":
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise SchemaError(f"{path}: expected a JSON list of objects")
        columns = tuple(sorted({key for record in data for key in record}))
        return Table(path, columns, data, is_csv=False)
    raise SchemaError(f"{path}: unsupported extension {suffix!r}; expected one of "
                      f"{SUPPORTED_EXTENSIONS}")


def find_input(input_dir: str | Path, kind: str, split: str = "test") -> Path:
    """Locate the file for one table inside an input directory.

    Args:
        input_dir: Directory passed as ``--input`` (the pack's ``data/`` folder).
        kind: A key of ``INPUT_FILES``.
        split: ``train`` or ``test``; only the patients file depends on it.

    Returns:
        Path to ``<stem>.csv`` or ``<stem>.json``.

    Raises:
        SchemaError: Unknown split, neither file exists, or both do (the choice would be silent).
    """
    if split not in SPLITS:
        raise SchemaError(f"unknown split {split!r}; expected one of {SPLITS}")
    stem = INPUT_FILES[kind].format(split=split)
    found = [Path(input_dir) / f"{stem}{ext}" for ext in SUPPORTED_EXTENSIONS
             if (Path(input_dir) / f"{stem}{ext}").is_file()]
    if not found:
        raise SchemaError(f"{input_dir}: no {stem}.csv or {stem}.json for the {kind} table")
    if len(found) > 1:
        raise SchemaError(f"{input_dir}: both {found[0].name} and {found[1].name} exist; "
                          f"keep one")
    return found[0]


def split_medications(text: str | None) -> tuple[str, ...]:
    """Split a medication list on ';' and line breaks, trimming each entry; empty ones dropped.

    This is exactly how the scorer defines a written token, so resolution rows line up with it.
    """
    if text is None:
        return ()
    return tuple(part.strip() for part in MEDICATION_SEPARATOR.split(str(text)) if part.strip())


def load_patients(path: str | Path, report: LoadReport | None = None) -> list[Patient]:
    """Load patients, in file order.

    Args:
        path: CSV or JSON patients file.
        report: Filled in with counts, skipped rows and degraded fields if given.

    Returns:
        One ``Patient`` per row with a patient id and at least one medication. Missing clinical
        values are ``None``; unreadable ones are ``None`` too, named in ``unreadable_fields``.
        Medication entries are kept exactly as written, trimmed, and indexed from 0. A repeated
        ``patient_id`` keeps the first row and skips the rest.

    Raises:
        SchemaError: The file does not match ``COLUMN_MAP['patients']``.
    """
    return _load_table(path, "patients", _build_patient, lambda p: p.patient_id, report)


def load_drugs(path: str | Path, report: LoadReport | None = None) -> dict[str, Drug]:
    """Load the drug reference, keyed by generic name.

    Generic names are lowercased with whitespace collapsed, so every table joins on the same
    key. A repeated generic keeps the first row. A drug with an unreadable field is kept with
    that field ``None``: dropping it would silently remove it from every patient on it.
    """
    drugs = _load_table(path, "drugs", _build_drug, lambda d: d.generic, report)
    return {drug.generic: drug for drug in drugs}


def load_combinations(path: str | Path,
                      report: LoadReport | None = None) -> list[CombinationBrand]:
    """Load combination brands, one row per (brand, strength) variant, in file order."""
    return _load_table(path, "combinations", _build_combination,
                       lambda c: (c.brand.lower(), c.strength_label), report)


def load_interactions(path: str | Path,
                      report: LoadReport | None = None) -> list[InteractionPair]:
    """Load the interaction table, in file order. A pair missing either drug is skipped."""
    return _load_table(path, "interactions", _build_interaction,
                       lambda i: frozenset((i.drug_a, i.drug_b)), report)


def load_renal_rules(path: str | Path, report: LoadReport | None = None) -> list[RenalRule]:
    """Load the eGFR dose tiers, in file order."""
    return _load_table(path, "renal_rules", _build_renal_rule,
                       lambda r: (r.generic, r.egfr_below), report)


def load_duplicate_groups(path: str | Path,
                          report: LoadReport | None = None) -> dict[str, DuplicateGroup]:
    """Load the duplicate-therapy groups, keyed by group id."""
    groups = _load_table(path, "duplicate_groups", _build_duplicate_group,
                         lambda g: g.group_id, report)
    return {group.group_id: group for group in groups}


def load_contraindications(path: str | Path,
                           report: LoadReport | None = None) -> list[Contraindication]:
    """Load the drug x condition / allergy / pregnancy table, in file order."""
    return _load_table(path, "contraindications", _build_contraindication,
                       lambda c: (c.condition_id, c.generic), report)


def load_conditions(path: str | Path, report: LoadReport | None = None) -> dict[str, Condition]:
    """Load the condition ids, keyed by id."""
    conditions = _load_table(path, "conditions", _build_condition,
                             lambda c: c.condition_id, report)
    return {condition.condition_id: condition for condition in conditions}


def load_dataset(input_dir: str | Path, split: str = "test") -> Dataset:
    """Load the patients of one split and all seven reference tables.

    Args:
        input_dir: The pack's ``data/`` folder.
        split: ``train`` or ``test``.

    Returns:
        A ``Dataset`` with one ``LoadReport`` per file, patients first.

    Raises:
        SchemaError: A file is missing, ambiguous, or does not match ``COLUMN_MAP``.
    """
    reports = {kind: LoadReport() for kind in INPUT_FILES}

    def path(kind: str) -> Path:
        """The file for one table in this input directory and split."""
        return find_input(input_dir, kind, split)

    return Dataset(
        patients=load_patients(path("patients"), reports["patients"]),
        drugs=load_drugs(path("drugs"), reports["drugs"]),
        combinations=load_combinations(path("combinations"), reports["combinations"]),
        interactions=load_interactions(path("interactions"), reports["interactions"]),
        renal_rules=load_renal_rules(path("renal_rules"), reports["renal_rules"]),
        duplicate_groups=load_duplicate_groups(path("duplicate_groups"),
                                               reports["duplicate_groups"]),
        contraindications=load_contraindications(path("contraindications"),
                                                 reports["contraindications"]),
        conditions=load_conditions(path("conditions"), reports["conditions"]),
        reports=tuple(reports.values()),
    )


Builder = Callable[[Mapping[str, Any], list[FieldIssue]], T]


def _load_table(path: str | Path, kind: str, build: Builder[T], key: Callable[[T], Any],
                report: LoadReport | None) -> list[T]:
    """Read, map and validate one file, recording every skipped row and degraded field."""
    table = read_table(path)
    column_map = COLUMN_MAP[kind]
    notes = validate.require_columns(table.columns, column_map, kind, str(table.path))
    report = report if report is not None else LoadReport()
    report.kind, report.source = kind, str(table.path)
    report.notes.extend(notes)
    for note in notes:
        logger.warning("%s: %s", table.path.name, note)

    items: list[T] = []
    seen: set[Any] = set()
    for index, record in enumerate(table.records):
        report.rows_read += 1
        issues: list[FieldIssue] = []
        try:
            shape = _csv_shape_issue(record, len(table.columns)) if table.is_csv else None
            if shape is not None:
                issues.append(shape)
            item = build({name: _cell(record, column) for name, column in column_map.items()},
                         issues)
            item_key = key(item)
            if item_key in seen:
                raise RowError("duplicate", None, f"{_describe(item_key)} already loaded from "
                                                  f"an earlier row")
            seen.add(item_key)
        except RowError as error:
            skipped = report.record_skip(index, error)
            logger.warning("%s row %d skipped (%s): %s",
                           table.path.name, index, skipped.code, skipped.detail)
            continue
        for issue in issues:
            degradation = report.record_degradation(index, _describe(item_key), issue.field,
                                                    issue.raw_value, issue.error)
            logger.warning("%s row %d %s: %s loaded as None (%s)", table.path.name, index,
                           degradation.record_id, degradation.field, degradation.detail)
        items.append(item)
    report.loaded = len(items)
    return items


def _describe(key: Any) -> str:
    """A row key as readable text: ``P0042``, ``warfarin``, ``aspirin+warfarin``."""
    if isinstance(key, frozenset):
        return "+".join(sorted(key))
    if isinstance(key, tuple):
        return "/".join("" if part is None else str(part) for part in key)
    return str(key)


def _csv_shape_issue(record: Mapping[Any, Any], n_columns: int) -> FieldIssue | None:
    """Describe a CSV row with more or fewer fields than the header, or return None."""
    if None in record:
        extra = record[None]
        return FieldIssue("row", extra, RowError(
            "malformed_row", None, f"{len(extra)} more field(s) than the header; "
                                   f"values may be misaligned"))
    short = sum(1 for value in record.values() if value is None)
    if short:
        return FieldIssue("row", "", RowError(
            "malformed_row", None, f"{n_columns - short} field(s) where the header has "
                                   f"{n_columns}; the missing fields load as None"))
    return None


def _cell(record: Mapping[str, Any], column: str | None) -> Any:
    """The raw value of ``column`` in ``record``, or None if unmapped, absent or a missing token."""
    if column is None:
        return None
    value = record.get(column)
    if isinstance(value, str) and value.strip().lower() in MISSING_TOKENS:
        return None
    return value


def _split_list(value: Any, separator: str = LIST_SEPARATOR) -> tuple[str, ...]:
    """Split a list cell (JSON array or separator-joined text) into stripped, non-empty items."""
    if value is None:
        return ()
    items = value if isinstance(value, list) else str(value).split(separator)
    stripped = (str(item).strip() for item in items if item is not None)
    return tuple(item for item in stripped if item)


def _canonical_generic(name: str) -> str:
    """Lowercase a generic name and collapse internal whitespace."""
    return " ".join(name.lower().split())


class _Reader:
    """Reads optional fields of one row; a bad value becomes None and is recorded as an issue."""

    def __init__(self, cells: Mapping[str, Any], issues: list[FieldIssue]) -> None:
        self.cells = cells
        self.issues = issues

    def __call__(self, name: str, coerce: Callable[..., Any], *args: Any) -> Any:
        """Coerce and range-check field ``name``; on failure record the issue and return None."""
        try:
            return validate.check_range(coerce(self.cells[name], name, *args), name)
        except RowError as error:
            self.issues.append(FieldIssue(name, self.cells[name], error))
            return None

    def text(self, name: str) -> str | None:
        """An optional free-text field."""
        return self(name, validate.coerce_text)

    def severity(self, name: str = "severity") -> str | None:
        """An optional severity, one of the published scale."""
        return self(name, validate.coerce_choice, SEVERITIES)

    @property
    def unreadable(self) -> tuple[str, ...]:
        """Names of the fields that failed so far, in order."""
        return tuple(issue.field for issue in self.issues)


def _coerce_pregnancy(value: Any, name: str) -> bool | None:
    """Y -> True, N -> False, NA (not applicable) or blank -> None; anything else is unreadable."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().upper()
    if text not in PREGNANCY_STATUS:
        raise RowError("bad_value", name, f"{name}={value!r} is not one of Y, N, NA")
    return PREGNANCY_STATUS[text]


def _build_patient(cells: Mapping[str, Any], issues: list[FieldIssue]) -> Patient:
    """Build a Patient. Only a missing patient id or medication list raises RowError."""
    patient_id = validate.coerce_text(cells["patient_id"], "patient_id", required=True)
    listed = cells["medications"]
    medications = (_split_list(listed) if isinstance(listed, list)
                   else split_medications(None if listed is None else str(listed)))
    if not medications:
        raise RowError("missing_value", "medications", "medication list is missing or empty")
    read = _Reader(cells, issues)
    age = read("age", validate.coerce_int)
    sex = read("sex", validate.coerce_choice, SEXES)
    weight_kg = read("weight_kg", validate.coerce_float)
    egfr = read("egfr", validate.coerce_float)
    pregnant = read("pregnant", _coerce_pregnancy)
    allergies = read.text("allergies")
    prescriber_count = read("prescriber_count", validate.coerce_int)
    return Patient(
        patient_id=patient_id, age=age, sex=sex, weight_kg=weight_kg, egfr=egfr,
        pregnant=pregnant, diagnoses=_split_list(cells["diagnoses"]), allergies=allergies,
        medications=tuple(MedicationEntry(raw=raw, index=index)
                          for index, raw in enumerate(medications)),
        prescriber_count=prescriber_count, unreadable_fields=read.unreadable,
    )


def _build_drug(cells: Mapping[str, Any], issues: list[FieldIssue]) -> Drug:
    """Build a Drug. Only a missing generic name raises RowError."""
    generic = _canonical_generic(validate.coerce_text(cells["generic"], "generic", required=True))
    read = _Reader(cells, issues)
    drug_id = read.text("drug_id")
    drug_class = read.text("drug_class")
    therapeutic_group = read.text("therapeutic_group")
    duplicate_group = read.text("duplicate_group")
    usual_daily_dose = read.text("usual_daily_dose")
    max_daily_dose_mg = read("max_daily_dose_mg", validate.coerce_float)
    renal_flag = read("renal_adjust", validate.coerce_choice, YES_NO)
    renal_rule = read.text("renal_rule")
    pregnancy_category = read("pregnancy_category", validate.coerce_choice, PREGNANCY_CATEGORIES)
    notes = read.text("notes")
    return Drug(
        generic=generic, drug_id=drug_id, drug_class=drug_class,
        therapeutic_group=therapeutic_group, duplicate_group=duplicate_group,
        brands=_split_list(cells["brands"]), dose_forms=_split_list(cells["dose_forms"]),
        usual_daily_dose=usual_daily_dose, max_daily_dose_mg=max_daily_dose_mg,
        renal_adjust=None if renal_flag is None else renal_flag == "Y",
        renal_rule=renal_rule, pregnancy_category=pregnancy_category, notes=notes,
        unreadable_fields=read.unreadable,
    )


def _build_combination(cells: Mapping[str, Any], issues: list[FieldIssue]) -> CombinationBrand:
    """Build a CombinationBrand. A missing brand or component list raises RowError."""
    brand = validate.coerce_text(cells["brand"], "brand", required=True)
    generics = tuple(sorted(_canonical_generic(g) for g in _split_list(cells["generics"])))
    if not generics:
        raise RowError("missing_value", "generics", f"{brand!r} lists no generic components")
    read = _Reader(cells, issues)
    strength_label = read.text("strength_label")
    dose_form = read.text("dose_form")
    components = read.text("components")
    return CombinationBrand(brand=brand, strength_label=strength_label, dose_form=dose_form,
                            components=components, generics=generics,
                            unreadable_fields=read.unreadable)


def _build_interaction(cells: Mapping[str, Any], issues: list[FieldIssue]) -> InteractionPair:
    """Build an InteractionPair. A missing drug, or a drug paired with itself, raises RowError."""
    drug_a = _canonical_generic(validate.coerce_text(cells["drug_a"], "drug_a", required=True))
    drug_b = _canonical_generic(validate.coerce_text(cells["drug_b"], "drug_b", required=True))
    if drug_a == drug_b:
        raise RowError("self_pair", "drug_b", f"{drug_a!r} is paired with itself")
    read = _Reader(cells, issues)
    severity = read.severity()
    mechanism = read.text("mechanism")
    action = read.text("action")
    return InteractionPair(drug_a=drug_a, drug_b=drug_b, severity=severity, mechanism=mechanism,
                           action=action, unreadable_fields=read.unreadable)


def _build_renal_rule(cells: Mapping[str, Any], issues: list[FieldIssue]) -> RenalRule:
    """Build a RenalRule. A missing generic raises RowError; a bad threshold loads as None."""
    generic = _canonical_generic(validate.coerce_text(cells["generic"], "generic", required=True))
    read = _Reader(cells, issues)
    egfr_below = read("egfr_below", validate.coerce_int)
    severity = read.severity()
    action = read.text("action")
    return RenalRule(generic=generic, egfr_below=egfr_below, severity=severity, action=action,
                     unreadable_fields=read.unreadable)


def _build_duplicate_group(cells: Mapping[str, Any], issues: list[FieldIssue]) -> DuplicateGroup:
    """Build a DuplicateGroup. A missing group id raises RowError."""
    group_id = validate.coerce_text(cells["group_id"], "group_id", required=True)
    read = _Reader(cells, issues)
    name = read.text("name")
    severity = read.severity()
    action = read.text("action")
    return DuplicateGroup(group_id=group_id, name=name, severity=severity, action=action,
                          members=tuple(_canonical_generic(m) for m in _split_list(cells["members"])),
                          unreadable_fields=read.unreadable)


def _build_contraindication(cells: Mapping[str, Any],
                            issues: list[FieldIssue]) -> Contraindication:
    """Build a Contraindication. A missing condition id or generic raises RowError."""
    condition_id = validate.coerce_text(cells["condition_id"], "condition_id", required=True)
    generic = _canonical_generic(validate.coerce_text(cells["generic"], "generic", required=True))
    read = _Reader(cells, issues)
    condition_name = read.text("condition_name")
    severity = read.severity()
    reason = read.text("reason")
    action = read.text("action")
    return Contraindication(condition_id=condition_id, condition_name=condition_name,
                            generic=generic, severity=severity, reason=reason, action=action,
                            unreadable_fields=read.unreadable)


def _build_condition(cells: Mapping[str, Any], issues: list[FieldIssue]) -> Condition:
    """Build a Condition. A missing condition id raises RowError."""
    condition_id = validate.coerce_text(cells["condition_id"], "condition_id", required=True)
    read = _Reader(cells, issues)
    name = read.text("name")
    kind = read.text("kind")
    description = read.text("description")
    return Condition(condition_id=condition_id, name=name, kind=kind, description=description,
                     example_terms=_split_list(cells["example_terms"]),
                     unreadable_fields=read.unreadable)
