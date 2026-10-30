"""Build data/medsafe.db, a SQLite convenience cache of the pipeline's output.

    python tools/build_db.py --input data/pack/data --split train [--db data/medsafe.db]

For querying (``tools/query.py``) and for the UI. Never on the scoring path: ``run.py`` reads the
supplied input files directly and gives identical output with this database deleted. Rebuilt
from scratch on every run; nothing in it is hand-edited.

Each table, and the phase that fills it:

    patients          Phase 1   clinical context, unreadable fields and their notes
    medications       Phase 1-2 each line as written, and what it resolved to and how
    findings          Phase 3   every rule hit, including minor ones (the UI shows them)
    alerts            Phase 6   what the predictions file holds: table severity, no minor
    collapse_results  UI only   per patient, the drug set whose change clears the most edges
    metrics           Phase 1   load counts; the Phase 7 evaluation report later. Phase 7 stores
                                the missed near-misses as metric ``near_miss_recall`` with
                                detail ``{"missed": [{patient_id, rule_id, drugs, reason}]}``
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from medsafe.data.adapter import Dataset, load_dataset  # noqa: E402
from medsafe.pipeline import PatientResult, PipelineResult, Settings, run_pipeline  # noqa: E402

DEFAULT_DB = ROOT / "data" / "medsafe.db"
TABLES = ("patients", "medications", "findings", "alerts", "collapse_results", "metrics")

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE patients (
    patient_id        TEXT PRIMARY KEY,
    age               INTEGER,
    sex               TEXT,
    weight_kg         REAL,
    egfr              REAL,
    pregnant          INTEGER CHECK (pregnant IN (0, 1)),   -- NULL: not applicable or unknown
    diagnoses         TEXT NOT NULL,              -- JSON array
    allergies         TEXT,
    prescriber_count  INTEGER,
    medication_count  INTEGER NOT NULL,
    unreadable_fields TEXT NOT NULL,              -- JSON array: fields loaded as None, unreadable
    data_notes        TEXT NOT NULL               -- JSON array: what that means for the checks
);

-- Primary key leads with patient_id, so it doubles as the patient_id index.
CREATE TABLE medications (
    patient_id        TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    med_index         INTEGER NOT NULL,
    raw               TEXT NOT NULL,
    normalised        TEXT,                       -- the name words the resolver matched on
    resolved_generic  TEXT,                       -- ';'-joined; NULL for non-drug or abstained
    method            TEXT CHECK (method IN ('exact', 'synonym', 'parts', 'prefix', 'fuzzy',
                                             'non_drug', 'abstained')),
    confidence        REAL,
    abstained         INTEGER CHECK (abstained IN (0, 1)),
    abstain_reason    TEXT,
    PRIMARY KEY (patient_id, med_index)
);

CREATE TABLE findings (
    finding_id        INTEGER PRIMARY KEY,
    patient_id        TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    issue_type        TEXT NOT NULL,              -- interaction, duplicate_therapy, renal_dose,
                                                  -- contraindication
    rule_id           TEXT NOT NULL,
    drugs             TEXT NOT NULL,              -- JSON array of generics
    severity          TEXT NOT NULL,              -- the table's severity, unchanged (D-015)
    evidence          TEXT                        -- JSON: the patient values that triggered it
);
CREATE INDEX findings_patient_id ON findings(patient_id);

CREATE TABLE alerts (
    alert_id          INTEGER PRIMARY KEY,
    patient_id        TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    issue_type        TEXT NOT NULL,
    severity          TEXT NOT NULL,
    drugs_involved    TEXT NOT NULL,              -- ';'-joined generics, as in the submission
    suggested_action  TEXT NOT NULL,
    confidence        REAL NOT NULL,
    UNIQUE (patient_id, issue_type, drugs_involved)
);
CREATE INDEX alerts_patient_id ON alerts(patient_id);

CREATE TABLE collapse_results (
    patient_id        TEXT PRIMARY KEY REFERENCES patients(patient_id) ON DELETE CASCADE,
    chosen_drugs      TEXT NOT NULL,              -- JSON array
    edges_total       INTEGER NOT NULL,
    edges_cleared     INTEGER NOT NULL,
    edges_remaining   INTEGER NOT NULL,
    cleared_by        TEXT,                       -- JSON: drug -> edges it clears
    remaining_edges   TEXT,                       -- JSON
    suggested_action  TEXT
);

CREATE TABLE metrics (
    name              TEXT PRIMARY KEY,
    value             REAL,
    detail            TEXT                        -- JSON
);
"""


def insert_patients(conn: sqlite3.Connection, result: PipelineResult) -> None:
    """Insert one row per patient and one per medication as written. Missing stays NULL."""
    def patient_row(r: PatientResult) -> tuple:
        """One patients-table row. NULL stays NULL; lists are stored as JSON arrays."""
        p = r.patient
        return (p.patient_id, p.age, p.sex, p.weight_kg, p.egfr,
                None if p.pregnant is None else int(p.pregnant),
                json.dumps(list(p.diagnoses)), p.allergies, p.prescriber_count,
                len(p.medications), json.dumps(list(p.unreadable_fields)), json.dumps(list(r.notes)))

    conn.executemany(
        "INSERT INTO patients (patient_id, age, sex, weight_kg, egfr, pregnant, diagnoses, "
        "allergies, prescriber_count, medication_count, unreadable_fields, data_notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [patient_row(r) for r in result.patients])
    conn.executemany(
        "INSERT INTO medications (patient_id, med_index, raw, normalised, resolved_generic, "
        "method, confidence, abstained, abstain_reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(r.patient.patient_id, m.index, m.raw, res.normalised, res.resolved_generic,
          res.method, res.confidence, int(res.verify_manually), res.abstain_reason)
         for r in result.patients for m, res in zip(r.patient.medications, r.resolutions)])
    conn.executemany(
        "INSERT INTO findings (patient_id, issue_type, rule_id, drugs, severity, evidence) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(r.patient.patient_id, f.issue_type, f.rule_id, json.dumps(list(f.drugs)), f.severity,
          json.dumps(f.evidence)) for r in result.patients for f in r.findings])
    conn.executemany(
        "INSERT INTO alerts (patient_id, issue_type, severity, drugs_involved, suggested_action, "
        "confidence) VALUES (:patient_id, :issue_type, :severity, :drugs_involved, "
        ":suggested_action, :confidence)",
        [a for r in result.patients for a in r.alerts])


def insert_load_metrics(conn: sqlite3.Connection, dataset: Dataset, input_dir: Path) -> None:
    """Record what the adapter loaded and skipped, per file, plus the input it came from."""
    rows: list[tuple[str, float | None, str | None]] = [
        ("build.input_dir", None, json.dumps(str(input_dir))),
        ("load.medications", sum(len(p.medications) for p in dataset.patients), None),
    ]
    for report in dataset.reports:
        rows += [
            (f"load.{report.kind}.read", report.rows_read, None),
            (f"load.{report.kind}.loaded", report.loaded, None),
            (f"load.{report.kind}.loaded_clean", report.loaded_clean, None),
            (f"load.{report.kind}.loaded_degraded", report.loaded_degraded,
             json.dumps({"fields": report.degraded_fields})),
            (f"load.{report.kind}.skipped", report.skipped,
             json.dumps({"reasons": report.reasons, "notes": report.notes})),
        ]
    conn.executemany("INSERT INTO metrics (name, value, detail) VALUES (?, ?, ?)", rows)


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Row count per table, in schema order."""
    return {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in TABLES}


def build_db(input_dir: Path, db_path: Path = DEFAULT_DB, split: str = "train") -> dict[str, int]:
    """Run the pipeline stages built so far over ``input_dir`` and write them to ``db_path``.

    The database is written to a temporary file and moved into place, so a failed build never
    leaves a half-written cache behind.

    Args:
        input_dir: The pack's data folder, as for ``run.py --input``.
        db_path: Where to write the database. Replaced if it exists.
        split: ``train`` or ``test`` patients.

    Returns:
        Row count per table.

    Raises:
        SchemaError: The input does not match ``COLUMN_MAP``.
    """
    dataset = load_dataset(input_dir, split)
    result = run_pipeline(dataset, Settings())
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = db_path.with_name(db_path.name + ".tmp")
    temporary.unlink(missing_ok=True)
    with closing(sqlite3.connect(temporary)) as conn:
        conn.executescript(SCHEMA)
        insert_patients(conn, result)
        insert_load_metrics(conn, dataset, input_dir)
        conn.commit()
        counts = table_counts(conn)
    os.replace(temporary, db_path)
    return counts


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point. Returns the exit code."""
    parser = argparse.ArgumentParser(description="Build the SQLite convenience cache.")
    parser.add_argument("--input", required=True, type=Path, help="the pack's data folder")
    parser.add_argument("--split", choices=("train", "test"), default="train")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"default {DEFAULT_DB}")
    args = parser.parse_args(argv)
    counts = build_db(args.input, args.db, args.split)
    print(f"built {args.db}")
    for table, count in counts.items():
        print(f"  {table:<17} {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
