"""Phase 1: the adapter loads source files into the internal schema, and refuses bad rows loudly.

The swap tests run against tests/fixtures by default. When the real dataset lands, edit
COLUMN_MAP and point the same tests at it:

    MEDSAFE_DATA_DIR=data pytest tests/test_adapter.py -k swap

If they pass, everything downstream of the adapter works on the real files.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from medsafe.data import adapter
from medsafe.data.adapter import (COLUMN_MAP, MISSING_TOKENS, find_input, load_dataset,
                                  load_drugs, load_interactions, load_patients)
from medsafe.data.validate import (LoadReport, RowError, SchemaError, check_range, coerce_bool,
                                   coerce_float, coerce_int, coerce_text)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DATA_DIR = Path(os.environ.get("MEDSAFE_DATA_DIR", FIXTURES_DIR))
OPTIONAL_PATIENT_FIELDS = ("age", "weight_kg", "egfr", "pregnant")
CORRUPT_INDEX = 41  # 0-based record index of the row the malformed-row tests break (P0042)

fixtures_only = pytest.mark.skipif(DATA_DIR.resolve() != FIXTURES_DIR.resolve(),
                                   reason="counts specific to the synthetic fixtures")


@pytest.fixture(scope="module")
def dataset() -> adapter.Dataset:
    """Everything in DATA_DIR, loaded once for the module."""
    return load_dataset(DATA_DIR)


def write_copy(tmp_path: Path, name: str, mutate: Callable[[list[list[str]]], None]) -> Path:
    """Copy a fixture CSV into tmp_path after ``mutate`` edits its rows (row 0 is the header)."""
    with (FIXTURES_DIR / name).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    mutate(rows)
    path = tmp_path / name
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)
    return path


def set_cell(column: str, value: str, index: int = CORRUPT_INDEX) -> Callable[[list[list[str]]], None]:
    """A mutation that overwrites one cell of record ``index``."""
    def mutate(rows: list[list[str]]) -> None:
        rows[index + 1][rows[0].index(column)] = value
    return mutate


# --- Swap tests: hold for the fixtures now and for the real dataset later ---------------------

def test_swap_every_patient_fully_populated(dataset: adapter.Dataset) -> None:
    assert dataset.patients, "no patients loaded"
    for patient in dataset.patients:
        assert type(patient.patient_id) is str and patient.patient_id
        assert patient.patient_id == patient.patient_id.strip()
        assert patient.age is None or type(patient.age) is int
        assert patient.weight_kg is None or type(patient.weight_kg) is float
        assert patient.egfr is None or type(patient.egfr) is float
        assert patient.pregnant is None or type(patient.pregnant) is bool
        assert type(patient.diagnoses) is tuple
        assert all(type(d) is str and d for d in patient.diagnoses)
        assert type(patient.medications) is tuple and patient.medications, patient.patient_id
        assert [m.index for m in patient.medications] == list(range(len(patient.medications)))
        assert all(type(m.raw) is str and m.raw and m.raw == m.raw.strip()
                   for m in patient.medications)


def test_swap_missing_loads_as_none_never_zero(dataset: adapter.Dataset) -> None:
    """A blank source cell loads as None, and a filled one never does."""
    table = adapter.read_table(find_input(DATA_DIR, "patients"))
    id_column = COLUMN_MAP["patients"]["patient_id"]
    first_record: dict[str, dict] = {}
    for record in table.records:
        first_record.setdefault(str(record.get(id_column)).strip(), record)

    for patient in dataset.patients:
        record = first_record[patient.patient_id]
        for name in OPTIONAL_PATIENT_FIELDS:
            column = COLUMN_MAP["patients"][name]
            cell = record.get(column) if column else None
            blank = cell is None or (isinstance(cell, str)
                                     and cell.strip().lower() in MISSING_TOKENS)
            value = getattr(patient, name)
            assert (value is None) == blank, f"{patient.patient_id}.{name}: {cell!r} -> {value!r}"


def test_swap_reference_tables_fully_populated(dataset: adapter.Dataset) -> None:
    assert dataset.drugs and dataset.interactions
    for key, drug in dataset.drugs.items():
        assert key == drug.generic and drug.generic == drug.generic.lower().strip() != ""
        assert type(drug.drug_class) is str and drug.drug_class
        assert type(drug.brands) is tuple and all(type(b) is str and b for b in drug.brands)
        assert type(drug.renal_adjust) is bool
        assert drug.pregnancy_category is None or drug.pregnancy_category
    for pair in dataset.interactions:
        assert pair.drug_a and pair.drug_b and pair.drug_a != pair.drug_b
        assert type(pair.severity) is str and pair.severity
        assert pair.mechanism is None or pair.mechanism


# --- The synthetic fixtures specifically ------------------------------------------------------

@fixtures_only
def test_fixtures_load_200_patients_with_nothing_skipped(dataset: adapter.Dataset) -> None:
    assert len(dataset.patients) == 200
    assert len(dataset.drugs) == 68
    assert len(dataset.interactions) == 195
    for report in dataset.reports:
        assert report.skipped == 0 and not report.notes, report.summary()


@fixtures_only
def test_fixtures_have_the_shape_the_brief_describes(dataset: adapter.Dataset) -> None:
    patients = dataset.patients
    assert all(4 <= len(p.medications) <= 12 for p in patients)
    egfrs = [p.egfr for p in patients if p.egfr is not None]
    assert 15 <= min(egfrs) < 30 and max(egfrs) <= 110
    assert any(p.pregnant for p in patients)
    assert any(p.age is not None and p.age > 75 for p in patients)


@fixtures_only
def test_fixtures_exercise_every_missing_value_path(dataset: adapter.Dataset) -> None:
    for name in OPTIONAL_PATIENT_FIELDS:
        assert any(getattr(p, name) is None for p in dataset.patients), name


@fixtures_only
def test_ground_truth_lines_up_with_loaded_medications(dataset: adapter.Dataset) -> None:
    with (FIXTURES_DIR / "ground_truth.csv").open(newline="", encoding="utf-8") as handle:
        truth = list(csv.DictReader(handle))
    loaded = {(p.patient_id, m.index): m.raw for p in dataset.patients for m in p.medications}
    assert len(truth) == len(loaded)
    for row in truth:
        assert loaded[(row["patient_id"], int(row["med_index"]))] == row["raw"]


# --- Malformed rows: skipped, logged with their index, counted --------------------------------

@pytest.mark.parametrize(("column", "value", "code"), [
    ("egfr", "abc", "bad_type:egfr"),
    ("egfr", "250", "out_of_range:egfr"),
    ("egfr", "-3", "out_of_range:egfr"),
    ("age", "130", "out_of_range:age"),
    ("age", "72.5", "bad_type:age"),
    ("weight_kg", "400", "out_of_range:weight_kg"),
    ("pregnant", "maybe", "bad_type:pregnant"),
    ("patient_id", "", "missing_value:patient_id"),
])
def test_corrupted_row_is_skipped_logged_and_counted(tmp_path: Path, caplog: pytest.LogCaptureFixture,
                                                     column: str, value: str, code: str) -> None:
    path = write_copy(tmp_path, "patients.csv", set_cell(column, value))
    report = LoadReport()
    with caplog.at_level(logging.WARNING, logger="medsafe.data.adapter"):
        patients = load_patients(path, report)

    assert (report.rows_read, report.loaded, report.skipped) == (200, 199, 1)
    assert report.reasons == {code: 1}
    assert report.skipped_rows[0].index == CORRUPT_INDEX
    assert f"row {CORRUPT_INDEX} skipped ({code})" in caplog.text
    assert len(patients) == 199 and "P0042" not in {p.patient_id for p in patients}


def test_row_with_an_extra_field_is_skipped(tmp_path: Path) -> None:
    path = write_copy(tmp_path, "patients.csv", lambda rows: rows[CORRUPT_INDEX + 1].append("x"))
    report = LoadReport()
    assert len(load_patients(path, report)) == 199
    assert report.reasons == {"malformed_row": 1}


def test_truncated_row_is_skipped(tmp_path: Path) -> None:
    def truncate(rows: list[list[str]]) -> None:
        del rows[CORRUPT_INDEX + 1][3:]
    report = LoadReport()
    assert len(load_patients(write_copy(tmp_path, "patients.csv", truncate), report)) == 199
    assert report.reasons == {"malformed_row": 1}


def test_duplicate_patient_id_keeps_the_first_row(tmp_path: Path) -> None:
    original = load_patients(FIXTURES_DIR / "patients.csv")[0]
    report = LoadReport()
    patients = load_patients(write_copy(tmp_path, "patients.csv", set_cell("patient_id", "P0001")),
                             report)
    assert report.reasons == {"duplicate:patient_id": 1}
    assert report.skipped_rows[0].index == CORRUPT_INDEX
    assert patients[0] == original


def test_report_summary_names_counts_and_reasons(tmp_path: Path) -> None:
    report = LoadReport()
    load_patients(write_copy(tmp_path, "patients.csv", set_cell("egfr", "abc")), report)
    summary = report.summary()
    assert "200 read, 199 loaded, 1 skipped" in summary
    assert "bad_type:egfr: 1" in summary
    assert report.to_dict()["skipped_rows"][0]["index"] == CORRUPT_INDEX


def test_self_paired_interaction_is_skipped(tmp_path: Path) -> None:
    def self_pair(rows: list[list[str]]) -> None:
        rows[1][rows[0].index("drug_b")] = rows[1][rows[0].index("drug_a")]
    report = LoadReport()
    assert len(load_interactions(write_copy(tmp_path, "interactions.csv", self_pair), report)) == 194
    assert report.reasons == {"self_pair:drug_b": 1}


def test_drug_without_a_renal_flag_is_skipped_not_defaulted(tmp_path: Path) -> None:
    report = LoadReport()
    drugs = load_drugs(write_copy(tmp_path, "drugs.csv", set_cell("renal_adjust", "", index=0)),
                       report)
    assert len(drugs) == 67 and "warfarin" not in drugs
    assert report.reasons == {"missing_value:renal_adjust": 1}


# --- Missing is a value, not zero -------------------------------------------------------------

def test_egfr_zero_is_a_value_and_blank_is_none(tmp_path: Path) -> None:
    def mutate(rows: list[list[str]]) -> None:
        column = rows[0].index("egfr")
        rows[1][column], rows[2][column], rows[3][column] = "0", "", "NA"
    patients = load_patients(write_copy(tmp_path, "patients.csv", mutate))
    assert patients[0].egfr == 0.0 and patients[0].egfr is not None
    assert patients[1].egfr is None
    assert patients[2].egfr is None


# --- COLUMN_MAP is the single point of change -------------------------------------------------

def test_changing_column_map_redirects_a_field(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    def add_lab_column(rows: list[list[str]]) -> None:
        rows[0].append("egfr_lab")
        for row in rows[1:]:
            row.append("42")
    path = write_copy(tmp_path, "patients.csv", add_lab_column)
    before = load_patients(path)
    assert not all(p.egfr == 42.0 for p in before)

    monkeypatch.setitem(COLUMN_MAP["patients"], "egfr", "egfr_lab")
    after = load_patients(path)
    assert all(p.egfr == 42.0 for p in after)
    assert [p.age for p in after] == [p.age for p in before]


def test_mapped_column_absent_from_the_file_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(COLUMN_MAP["patients"], "egfr", "eGFR_mL_min")
    with pytest.raises(SchemaError, match="eGFR_mL_min"):
        load_patients(FIXTURES_DIR / "patients.csv")


def test_unmapped_optional_field_loads_as_none_with_a_note(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(COLUMN_MAP["patients"], "pregnant", None)
    report = LoadReport()
    patients = load_patients(FIXTURES_DIR / "patients.csv", report)
    assert len(patients) == 200 and all(p.pregnant is None for p in patients)
    assert any(note.startswith("pregnant:") for note in report.notes)


def test_unmapped_required_field_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(COLUMN_MAP["patients"], "medications", None)
    with pytest.raises(SchemaError, match="medications"):
        load_patients(FIXTURES_DIR / "patients.csv")


# --- File formats -----------------------------------------------------------------------------

def test_json_input_loads_identically_to_csv(tmp_path: Path) -> None:
    with (FIXTURES_DIR / "patients.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    records = [{
        "patient_id": row["patient_id"],
        "age": int(row["age"]) if row["age"] else None,
        "weight_kg": float(row["weight_kg"]) if row["weight_kg"] else None,
        "egfr": float(row["egfr"]) if row["egfr"] else None,
        "pregnant": {"Y": True, "N": False}.get(row["pregnant"]),
        "diagnoses": row["diagnoses"].split("|") if row["diagnoses"] else [],
        "medications": row["medications"].split("|"),
    } for row in rows]
    path = tmp_path / "patients.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    assert load_patients(path) == load_patients(FIXTURES_DIR / "patients.csv")


def test_unsupported_extension_raises(tmp_path: Path) -> None:
    path = tmp_path / "patients.xlsx"
    path.write_bytes(b"")
    with pytest.raises(SchemaError, match="unsupported extension"):
        load_patients(path)


def test_find_input_refuses_a_missing_or_ambiguous_table(tmp_path: Path) -> None:
    with pytest.raises(SchemaError, match="no patients.csv or patients.json"):
        find_input(tmp_path, "patients")
    (tmp_path / "patients.csv").write_text("patient_id\n", encoding="utf-8")
    (tmp_path / "patients.json").write_text("[]", encoding="utf-8")
    with pytest.raises(SchemaError, match="both"):
        find_input(tmp_path, "patients")


# --- Coercion edge cases ----------------------------------------------------------------------

@pytest.mark.parametrize(("token", "expected"), [
    ("Y", True), ("yes", True), ("TRUE", True), ("1", True), (True, True),
    ("n", False), ("No", False), ("0", False), (False, False), (None, None),
])
def test_coerce_bool_tokens(token: object, expected: bool | None) -> None:
    assert coerce_bool(token, "pregnant") is expected


def test_coerce_text_blank_is_none_and_structures_are_refused() -> None:
    assert coerce_text("  Warf 5 ", "raw") == "Warf 5"
    assert coerce_text("   ", "raw") is None
    with pytest.raises(RowError, match="missing"):
        coerce_text("", "patient_id", required=True)
    with pytest.raises(RowError, match="not text"):
        coerce_text(["P0001"], "patient_id")


def test_coerce_int_takes_whole_numbers_only() -> None:
    assert coerce_int("72", "age") == 72
    assert coerce_int("72.0", "age") == 72
    for bad in ("72.5", "seventy", "nan", True):
        with pytest.raises(RowError):
            coerce_int(bad, "age")


def test_coerce_float_refuses_non_finite() -> None:
    assert coerce_float(" 38.5 ", "egfr") == 38.5
    for bad in ("inf", "nan", "38,5"):
        with pytest.raises(RowError):
            coerce_float(bad, "egfr")


def test_range_bounds_are_inclusive() -> None:
    assert check_range(0.0, "egfr") == 0.0
    assert check_range(200.0, "egfr") == 200.0
    assert check_range(None, "egfr") is None
    with pytest.raises(RowError, match="outside 0-200"):
        check_range(200.5, "egfr")
