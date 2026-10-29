"""The only module that knows the real file layout.

When the real dataset lands, edit ``COLUMN_MAP`` (and ``INPUT_FILES`` if the file names differ)
and nothing else. Every other module speaks the internal schema in ``medsafe.data.schema``.

Supports CSV and JSON, sniffed by file extension. A JSON file is a list of objects; list fields
may be JSON arrays or ``LIST_SEPARATOR``-joined strings. Every load goes through
``medsafe.data.validate`` and is counted in a ``LoadReport``.

A patient is never dropped for a bad clinical value: the field loads as ``None``, is named in
``Patient.unreadable_fields`` and is logged as a degradation. A patient row is skipped only when
it has no usable patient id, repeats an earlier id, or has no medications (docs/DECISIONS.md).
Drug and interaction rows are still skipped whole when malformed.
"""

from __future__ import annotations

import csv
import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple, TypeVar

from medsafe.data import validate
from medsafe.data.schema import Drug, InteractionPair, MedicationEntry, Patient
from medsafe.data.validate import LoadReport, RowError, SchemaError

# Internal field -> source column name. Map a field to None if the source has no such column;
# it then loads as None. All real column names live here and nowhere else.
COLUMN_MAP: dict[str, dict[str, str | None]] = {
    "patients": {
        "patient_id": "patient_id",
        "age": "age",
        "weight_kg": "weight_kg",
        "egfr": "egfr",
        "pregnant": "pregnant",
        "diagnoses": "diagnoses",
        "medications": "medications",
    },
    "drugs": {
        "generic": "generic",
        "drug_class": "drug_class",
        "brands": "brands",
        "renal_adjust": "renal_adjust",
        "pregnancy_category": "pregnancy_category",
    },
    "interactions": {
        "drug_a": "drug_a",
        "drug_b": "drug_b",
        "severity": "severity",
        "mechanism": "mechanism",
    },
}

# File stem of each table inside the --input directory. The extension is sniffed.
INPUT_FILES: dict[str, str] = {
    "patients": "patients",
    "drugs": "drugs",
    "interactions": "interactions",
}
SUPPORTED_EXTENSIONS = (".csv", ".json")

# Separates the items of a list held in one cell: medications, diagnoses, brands.
LIST_SEPARATOR = "|"

# Cell contents that mean "no value" in the source. Compared case-insensitively after strip.
MISSING_TOKENS = frozenset({"", "na", "n/a", "nan", "null", "none"})

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
    interactions: list[InteractionPair]
    reports: tuple[LoadReport, ...]


def read_table(path: str | Path) -> Table:
    """Read a CSV or JSON file into a ``Table``, choosing the parser by extension.

    Args:
        path: File to read. ``.csv`` is read with a header row; ``.json`` must hold a list of
            objects.

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


def find_input(input_dir: str | Path, kind: str) -> Path:
    """Locate the file for one table inside an input directory.

    Args:
        input_dir: Directory passed as ``--input``.
        kind: ``patients``, ``drugs`` or ``interactions``.

    Returns:
        Path to ``<INPUT_FILES[kind]>.csv`` or ``.json``.

    Raises:
        SchemaError: Neither file exists, or both do (the choice would be silent).
    """
    stem = INPUT_FILES[kind]
    found = [Path(input_dir) / f"{stem}{ext}" for ext in SUPPORTED_EXTENSIONS
             if (Path(input_dir) / f"{stem}{ext}").is_file()]
    if not found:
        raise SchemaError(f"{input_dir}: no {stem}.csv or {stem}.json for the {kind} table")
    if len(found) > 1:
        raise SchemaError(f"{input_dir}: both {found[0].name} and {found[1].name} exist; "
                          f"keep one")
    return found[0]


def load_patients(path: str | Path, report: LoadReport | None = None) -> list[Patient]:
    """Load patients, in file order.

    Args:
        path: CSV or JSON patients file.
        report: Filled in with counts and skipped rows if given.

    Returns:
        One ``Patient`` per row with a patient id and at least one medication. Missing clinical
        values are ``None``; unreadable ones are ``None`` too, named in ``unreadable_fields`` and
        recorded in the report as degradations. Medication strings are kept exactly as written,
        stripped of surrounding whitespace only, and indexed from 0. A repeated ``patient_id``
        keeps the first row and skips the rest.

    Raises:
        SchemaError: The file does not match ``COLUMN_MAP['patients']``.
    """
    return _load_table(path, "patients", _build_patient, "patient_id", report, degradable=True)


def load_drugs(path: str | Path, report: LoadReport | None = None) -> dict[str, Drug]:
    """Load the drug reference table, keyed by generic name.

    Args:
        path: CSV or JSON drugs file.
        report: Filled in with counts and skipped rows if given.

    Returns:
        Generic name to ``Drug``, in file order. Generic names are lowercased with whitespace
        collapsed, so drug and interaction tables join on the same key. A repeated generic keeps
        the first row and skips the rest.

    Raises:
        SchemaError: The file does not match ``COLUMN_MAP['drugs']``.
    """
    drugs = _load_table(path, "drugs", _build_drug, "generic", report)
    return {drug.generic: drug for drug in drugs}


def load_interactions(path: str | Path,
                      report: LoadReport | None = None) -> list[InteractionPair]:
    """Load the interaction table, in file order.

    Args:
        path: CSV or JSON interactions file.
        report: Filled in with counts and skipped rows if given.

    Returns:
        One ``InteractionPair`` per valid row. Generic names are canonicalised as in
        ``load_drugs``; severity is kept as given in the source. A drug paired with itself is
        skipped.

    Raises:
        SchemaError: The file does not match ``COLUMN_MAP['interactions']``.
    """
    return _load_table(path, "interactions", _build_interaction, None, report)


def load_dataset(input_dir: str | Path) -> Dataset:
    """Load all three tables from an input directory.

    Args:
        input_dir: Directory holding the patients, drugs and interactions files.

    Returns:
        A ``Dataset`` with the loaded tables and one ``LoadReport`` per file.

    Raises:
        SchemaError: A file is missing, ambiguous, or does not match ``COLUMN_MAP``.
    """
    reports = (LoadReport(), LoadReport(), LoadReport())
    patients = load_patients(find_input(input_dir, "patients"), reports[0])
    drugs = load_drugs(find_input(input_dir, "drugs"), reports[1])
    interactions = load_interactions(find_input(input_dir, "interactions"), reports[2])
    return Dataset(patients, drugs, interactions, reports)


Builder = Callable[[Mapping[str, Any], list[FieldIssue]], T]


def _load_table(path: str | Path, kind: str, build: Builder[T], unique_field: str | None,
                report: LoadReport | None, *, degradable: bool = False) -> list[T]:
    """Read, map and validate one file, recording every skipped row and degraded field.

    With ``degradable``, a builder may load a bad field as None and report it as a FieldIssue,
    and a CSV row of the wrong width is kept as degraded. Otherwise both skip the row.
    """
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
                if not degradable:
                    raise shape.error
                issues.append(shape)
            item = build({name: _cell(record, column) for name, column in column_map.items()},
                         issues)
            if unique_field is not None:
                key = getattr(item, unique_field)
                if key in seen:
                    raise RowError("duplicate", unique_field,
                                   f"{unique_field}={key!r} already loaded from an earlier row")
                seen.add(key)
        except RowError as error:
            skipped = report.record_skip(index, error)
            logger.warning("%s row %d skipped (%s): %s",
                           table.path.name, index, skipped.code, skipped.detail)
            continue
        for issue in issues:
            degradation = report.record_degradation(index, getattr(item, unique_field),
                                                    issue.field, issue.raw_value, issue.error)
            logger.warning("%s row %d %s: %s loaded as None (%s)", table.path.name, index,
                           degradation.patient_id, degradation.field, degradation.detail)
        items.append(item)
    report.loaded = len(items)
    return items


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


def _split_list(value: Any) -> tuple[str, ...]:
    """Split a list cell (JSON array or separator-joined text) into stripped, non-empty items."""
    if value is None:
        return ()
    items = value if isinstance(value, list) else str(value).split(LIST_SEPARATOR)
    stripped = (str(item).strip() for item in items if item is not None)
    return tuple(item for item in stripped if item)


def _canonical_generic(name: str) -> str:
    """Lowercase a generic name and collapse internal whitespace."""
    return " ".join(name.lower().split())


def _build_patient(cells: Mapping[str, Any], issues: list[FieldIssue]) -> Patient:
    """Build a Patient from mapped cells. Bad clinical fields load as None and join ``issues``.

    Raises:
        RowError: No patient id, or no medications. Only these drop the patient.
    """
    patient_id = validate.coerce_text(cells["patient_id"], "patient_id", required=True)
    medications = _split_list(cells["medications"])
    if not medications:
        raise RowError("missing_value", "medications", "medication list is missing or empty")

    def readable(name: str, coerce: Callable[[Any, str], Any]) -> Any:
        """Coerce and range-check one field; on failure record the issue and return None."""
        try:
            return validate.check_range(coerce(cells[name], name), name)
        except RowError as error:
            issues.append(FieldIssue(name, cells[name], error))
            return None

    age = readable("age", validate.coerce_int)
    weight_kg = readable("weight_kg", validate.coerce_float)
    egfr = readable("egfr", validate.coerce_float)
    pregnant = readable("pregnant", validate.coerce_bool)
    return Patient(
        patient_id=patient_id,
        age=age,
        weight_kg=weight_kg,
        egfr=egfr,
        pregnant=pregnant,
        diagnoses=_split_list(cells["diagnoses"]),
        medications=tuple(MedicationEntry(raw=raw, index=index)
                          for index, raw in enumerate(medications)),
        unreadable_fields=tuple(issue.field for issue in issues),
    )


def _build_drug(cells: Mapping[str, Any], issues: list[FieldIssue]) -> Drug:
    """Build a Drug from mapped cells, or raise RowError."""
    generic = validate.coerce_text(cells["generic"], "generic", required=True)
    return Drug(
        generic=_canonical_generic(generic),
        drug_class=validate.coerce_text(cells["drug_class"], "drug_class", required=True),
        brands=_split_list(cells["brands"]),
        renal_adjust=validate.coerce_bool(cells["renal_adjust"], "renal_adjust", required=True),
        pregnancy_category=validate.coerce_text(cells["pregnancy_category"],
                                                "pregnancy_category"),
    )


def _build_interaction(cells: Mapping[str, Any], issues: list[FieldIssue]) -> InteractionPair:
    """Build an InteractionPair from mapped cells, or raise RowError."""
    drug_a = _canonical_generic(validate.coerce_text(cells["drug_a"], "drug_a", required=True))
    drug_b = _canonical_generic(validate.coerce_text(cells["drug_b"], "drug_b", required=True))
    if drug_a == drug_b:
        raise RowError("self_pair", "drug_b", f"{drug_a!r} is paired with itself")
    return InteractionPair(
        drug_a=drug_a,
        drug_b=drug_b,
        severity=validate.coerce_text(cells["severity"], "severity", required=True),
        mechanism=validate.coerce_text(cells["mechanism"], "mechanism"),
    )
