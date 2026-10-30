"""Phase 1: the adapter loads the pack's files into the internal schema, and never drops a row
for one bad value.

The swap tests run on the real pack (data/pack, or MEDSAFE_DATA_DIR):

    MEDSAFE_DATA_DIR=data/pack pytest -k swap
"""

from __future__ import annotations

import csv
import json
import logging
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from conftest import MINI_DIR, requires_pack
from eval.pack import data_dir
from medsafe.data import adapter
from medsafe.data.adapter import COLUMN_MAP, find_input, load_dataset, load_patients, split_medications
from medsafe.data.validate import LoadReport, RowError, SchemaError, check_range, coerce_float, coerce_int
from medsafe.resolve.resolver import NameIndex, Resolver

Rows = list[list[str]]


def mini_copy(tmp_path: Path, name: str, mutate: Callable[[Rows], None]) -> Path:
    """Copy the mini fixtures to tmp_path after ``mutate`` edits one file's rows (row 0 is the
    header). Returns the copied folder."""
    folder = tmp_path / "mini"
    shutil.copytree(MINI_DIR, folder)
    with (folder / name).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    mutate(rows)
    with (folder / name).open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)
    return folder


def set_cell(column: str, value: str, index: int = 0) -> Callable[[Rows], None]:
    """A mutation that overwrites one cell of data row ``index``."""
    def mutate(rows: Rows) -> None:
        rows[index + 1][rows[0].index(column)] = value
    return mutate


def report_for(dataset: adapter.Dataset, kind: str) -> LoadReport:
    """The load report of one table."""
    return next(r for r in dataset.reports if r.kind == kind)


# --- The mini fixtures: the real layout, always available -------------------------------------

def test_mini_loads_every_table_cleanly(mini: adapter.Dataset) -> None:
    sizes = (len(mini.patients), len(mini.drugs), len(mini.combinations), len(mini.interactions),
             len(mini.renal_rules), len(mini.duplicate_groups), len(mini.contraindications),
             len(mini.conditions))
    assert sizes == (6, 13, 7, 4, 5, 4, 2, 2)
    for report in mini.reports:
        assert report.skipped == 0 and report.loaded_degraded == 0, report.summary()


def test_medication_list_splits_on_semicolons_and_line_breaks(mini: adapter.Dataset) -> None:
    by_id = {p.patient_id: p for p in mini.patients}
    assert [m.raw for m in by_id["H4P-MINI0002"].medications] == [
        "Brufen 400 tds", "T. Pan 40 OD", "Physiotherapy"]
    assert [m.index for m in by_id["H4P-MINI0001"].medications] == [0, 1, 2, 3]
    assert split_medications(" a ;\n b\r\n;; c ") == ("a", "b", "c")


def test_blank_is_none_and_na_pregnancy_means_not_applicable(mini: adapter.Dataset) -> None:
    by_id = {p.patient_id: p for p in mini.patients}
    male = by_id["H4P-MINI0002"]
    assert (male.pregnant, male.weight_kg, male.egfr) == (None, None, None)
    assert male.unreadable_fields == ()
    assert by_id["H4P-MINI0003"].pregnant is True
    assert by_id["H4P-MINI0001"].pregnant is False
    assert by_id["H4P-MINI0004"].allergies is None
    assert by_id["H4P-MINI0002"].allergies == "allergic to penicillin"
    assert by_id["H4P-MINI0001"].diagnoses == ("HTN", "DM2", "CKD 3b")


def test_reference_tables_keep_their_structure(mini: adapter.Dataset) -> None:
    assert mini.drugs["paracetamol"].brands == ("Crocin", "Dolo", "Calpol")
    assert mini.drugs["ibuprofen"].renal_adjust is True
    assert mini.drugs["warfarin"].duplicate_group is None
    assert mini.drugs["warfarin"].pregnancy_category == "X"
    glycomet = [c for c in mini.combinations if c.brand == "Glycomet-GP"]
    assert [(c.strength_label, c.generics) for c in glycomet] == [
        ("1", ("glimepiride", "metformin")), ("2", ("glimepiride", "metformin"))]
    assert mini.duplicate_groups["paracetamol"].members == ("paracetamol",)
    assert {(r.generic, r.egfr_below) for r in mini.renal_rules} >= {("metformin", 30)}


def test_split_selects_the_patients_file() -> None:
    assert [p.patient_id for p in load_dataset(MINI_DIR, "test").patients] == [
        "H4P-MINIT001", "H4P-MINIT002"]
    with pytest.raises(SchemaError, match="unknown split"):
        find_input(MINI_DIR, "patients", "validation")


# --- Patients: a bad value degrades one field, the patient is kept (D-001) ------------------

@pytest.mark.parametrize(("column", "value", "field", "code"), [
    ("weight_kg", "seventy", "weight_kg", "bad_type:weight_kg"),
    ("weight_kg", "NA", "weight_kg", "bad_type:weight_kg"),   # only blank means missing
    ("egfr_ml_min_1_73m2", "250", "egfr", "out_of_range:egfr"),
    ("age", "72.5", "age", "bad_type:age"),
    ("pregnant", "maybe", "pregnant", "bad_value:pregnant"),
    ("sex", "X", "sex", "bad_value:sex"),
    ("prescriber_count", "0", "prescriber_count", "out_of_range:prescriber_count"),
])
def test_bad_patient_value_degrades_the_field(tmp_path: Path, caplog: pytest.LogCaptureFixture,
                                              column: str, value: str, field: str, code: str) -> None:
    folder = mini_copy(tmp_path, "patients_train.csv", set_cell(column, value))
    with caplog.at_level(logging.WARNING, logger="medsafe.data.adapter"):
        dataset = load_dataset(folder, "train")
    report = report_for(dataset, "patients")
    assert (report.loaded, report.loaded_degraded, report.skipped) == (6, 1, 0)
    assert report.degraded_fields == {code: 1}
    assert report.degradations[0].record_id == "H4P-MINI0001"
    assert report.degradations[0].raw_value == value
    patient = dataset.patients[0]
    assert getattr(patient, field) is None and patient.unreadable_fields == (field,)
    assert len(patient.medications) == 4
    assert f"H4P-MINI0001: {field} loaded as None" in caplog.text


@pytest.mark.parametrize(("column", "value", "code"), [
    ("patient_id", "", "missing_value:patient_id"),
    ("medication_list", "", "missing_value:medications"),
    ("medication_list", " ; \n ", "missing_value:medications"),
    ("patient_id", "H4P-MINI0002", "duplicate"),
])
def test_only_no_id_duplicate_id_or_no_medications_skip_a_patient(
        tmp_path: Path, column: str, value: str, code: str) -> None:
    folder = mini_copy(tmp_path, "patients_train.csv", set_cell(column, value))
    report = report_for(load_dataset(folder, "train"), "patients")
    assert (report.loaded, report.skipped) == (5, 1)
    assert report.reasons == {code: 1}


def test_summary_separates_clean_degraded_and_skipped(tmp_path: Path) -> None:
    def mutate(rows: Rows) -> None:
        set_cell("weight_kg", "heavy", index=0)(rows)
        set_cell("patient_id", "", index=1)(rows)
    report = report_for(load_dataset(mini_copy(tmp_path, "patients_train.csv", mutate), "train"),
                        "patients")
    assert "6 read, 5 loaded (4 clean, 1 degraded), 1 skipped" in report.summary()
    assert report.to_dict()["degradations"][0]["record_id"] == "H4P-MINI0001"


# --- Reference rows: the same rule (E3) ------------------------------------------------------

def test_drug_with_one_bad_field_is_kept_and_its_patients_still_resolve(tmp_path: Path) -> None:
    """Paracetamol is on four of the mini patients' lists. A bad pregnancy letter must not
    remove it: dropping the row would silently stop every check on every one of them."""
    row = 1 - 1                                   # paracetamol is the first drug row
    folder = mini_copy(tmp_path, "drug_reference.csv", set_cell("pregnancy_category", "Q", row))
    dataset = load_dataset(folder, "train")
    report = report_for(dataset, "drugs")
    assert (report.loaded, report.skipped, report.degraded_fields) == (13, 0, {
        "bad_value:pregnancy_category": 1})
    paracetamol = dataset.drugs["paracetamol"]
    assert paracetamol.pregnancy_category is None
    assert paracetamol.unreadable_fields == ("pregnancy_category",)
    resolver = Resolver(NameIndex.build(dataset.drugs, dataset.combinations))
    assert resolver.resolve("Dolo 650 SOS").generics == ("paracetamol",)
    assert resolver.resolve("T. PCM 650 SOS").generics == ("paracetamol",)


@pytest.mark.parametrize(("name", "column", "value", "kind", "outcome"), [
    ("drug_reference.csv", "generic_name", "", "drugs", "skipped"),
    ("drug_reference.csv", "renal_adjustment_flag", "maybe", "drugs", "degraded"),
    ("interactions.csv", "drug_b", "", "interactions", "skipped"),
    ("interactions.csv", "severity", "severe", "interactions", "degraded"),
    ("renal_rules.csv", "egfr_below", "thirty", "renal_rules", "degraded"),
    ("combination_brands.csv", "generic_components", "", "combinations", "skipped"),
    ("duplicate_therapy_groups.csv", "severity", "high", "duplicate_groups", "degraded"),
    ("drug_disease_contraindications.csv", "generic_name", "", "contraindications", "skipped"),
])
def test_reference_rows_skip_only_when_the_row_is_not_a_row(
        tmp_path: Path, name: str, column: str, value: str, kind: str, outcome: str) -> None:
    report = report_for(load_dataset(mini_copy(tmp_path, name, set_cell(column, value)), "train"),
                        kind)
    assert (report.skipped, report.loaded_degraded) == ((1, 0) if outcome == "skipped" else (0, 1))


# --- COLUMN_MAP is the single point of change --------------------------------------------------

def test_changing_column_map_redirects_a_field(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def add_column(rows: Rows) -> None:
        rows[0].append("egfr_lab")
        for row in rows[1:]:
            row.append("42")
    folder = mini_copy(tmp_path, "patients_train.csv", add_column)
    before = load_patients(folder / "patients_train.csv")
    monkeypatch.setitem(COLUMN_MAP["patients"], "egfr", "egfr_lab")
    after = load_patients(folder / "patients_train.csv")
    assert {p.egfr for p in after} == {42.0} and {p.egfr for p in before} != {42.0}
    assert [p.age for p in after] == [p.age for p in before]


def test_mapped_column_absent_from_the_file_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(COLUMN_MAP["patients"], "egfr", "egfr_mdrd")
    with pytest.raises(SchemaError, match="egfr_mdrd"):
        load_patients(MINI_DIR / "patients_train.csv")


def test_json_input_loads_identically_to_csv(tmp_path: Path) -> None:
    with (MINI_DIR / "patients_train.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    path = tmp_path / "patients_train.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    assert load_patients(path) == load_patients(MINI_DIR / "patients_train.csv")


def test_coercion_edge_cases() -> None:
    assert coerce_int("72.0", "age") == 72
    assert coerce_float(" 38.5 ", "egfr") == 38.5
    assert check_range(0.0, "egfr") == 0.0
    for bad in ("72.5", "nan", True):
        with pytest.raises(RowError):
            coerce_int(bad, "age")
    with pytest.raises(RowError):
        check_range(200.5, "egfr")


# --- Swap tests: the real pack ------------------------------------------------------------------

@requires_pack
def test_swap_pack_loads_completely() -> None:
    train, test = load_dataset(data_dir(), "train"), load_dataset(data_dir(), "test")
    assert (len(train.patients), len(test.patients)) == (1500, 3500)
    sizes = (len(train.drugs), len(train.combinations), len(train.interactions),
             len(train.renal_rules), len(train.duplicate_groups), len(train.contraindications),
             len(train.conditions))
    assert sizes == (496, 98, 2196, 169, 74, 152, 58)
    for report in train.reports + test.reports:
        assert report.skipped == 0 and report.loaded_degraded == 0, report.summary()


@requires_pack
@pytest.mark.parametrize("split", ["train", "test"])
def test_swap_every_patient_fully_populated(split: str) -> None:
    for patient in load_dataset(data_dir(), split).patients:
        assert patient.patient_id and patient.medications
        assert type(patient.age) is int and patient.sex in ("M", "F")
        assert patient.weight_kg is None or type(patient.weight_kg) is float
        assert patient.egfr is None or type(patient.egfr) is float
        assert patient.pregnant is None or type(patient.pregnant) is bool
        assert patient.pregnant is None if patient.sex == "M" else patient.pregnant is not None
        assert type(patient.prescriber_count) is int
        assert all(m.raw == m.raw.strip() and m.raw for m in patient.medications)
        assert patient.unreadable_fields == ()


@requires_pack
def test_swap_blank_loads_as_none_never_zero(pack_train: adapter.Dataset) -> None:
    with (data_dir() / "patients_train.csv").open(newline="", encoding="utf-8") as handle:
        raw = {row["patient_id"]: row for row in csv.DictReader(handle)}
    for patient in pack_train.patients:
        assert (patient.egfr is None) == (raw[patient.patient_id]["egfr_ml_min_1_73m2"] == "")
        assert (patient.weight_kg is None) == (raw[patient.patient_id]["weight_kg"] == "")
    assert sum(p.egfr is None for p in pack_train.patients) == 116
    assert sum(p.weight_kg is None for p in pack_train.patients) == 41


@requires_pack
def test_swap_written_tokens_match_the_official_resolution_rows(pack_train: adapter.Dataset) -> None:
    with (data_dir() / "train_resolution.csv").open(newline="", encoding="utf-8") as handle:
        official: dict[str, list[str]] = {}
        for row in csv.DictReader(handle):
            official.setdefault(row["patient_id"], []).append(row["written_token"])
    ours = {p.patient_id: sorted(m.raw for m in p.medications) for p in pack_train.patients}
    assert ours == {pid: sorted(tokens) for pid, tokens in official.items()}   # order is not scored
