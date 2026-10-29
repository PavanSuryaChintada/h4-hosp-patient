"""Build data/medsafe.db, a SQLite convenience cache of the pipeline's output.

    python tools/build_db.py --input tests/fixtures [--db data/medsafe.db]

For querying (``tools/query.py``) and for the UI. Never on the scoring path: ``run.py`` reads the
supplied input files directly and gives identical output with this database deleted. Rebuilt
from scratch on every run; nothing in it is hand-edited.

Each table, and the phase that fills it:

    patients          Phase 1   clinical context, unreadable fields and their notes;
                                alerts_suppressed from Phase 6
    medications       Phase 1   raw strings; resolution columns from Phase 2
    findings          Phase 3-4 every rule hit before collapse, with table and final severity
    alerts            Phase 6   what ships after collapse and the cap: one submission row each
    collapse_results  Phase 5   per patient, the chosen drug set and the edges it clears
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
    weight_kg         REAL,
    egfr              REAL,
    pregnant          INTEGER CHECK (pregnant IN (0, 1)),
    diagnoses         TEXT NOT NULL,              -- JSON array
    medication_count  INTEGER NOT NULL,
    unreadable_fields TEXT NOT NULL,              -- JSON array: fields loaded as None, unreadable
    data_notes        TEXT NOT NULL,              -- JSON array: what that means for the checks
    alerts_suppressed INTEGER                     -- Phase 6
);

-- Primary key leads with patient_id, so it doubles as the patient_id index.
CREATE TABLE medications (
    patient_id        TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    med_index         INTEGER NOT NULL,
    raw               TEXT NOT NULL,
    normalised        TEXT,                       -- Phase 2 onward
    resolved_generic  TEXT,
    method            TEXT CHECK (method IN ('exact', 'fuzzy', 'abstained')),
    confidence        REAL,
    abstained         INTEGER CHECK (abstained IN (0, 1)),
    abstain_reason    TEXT,
    PRIMARY KEY (patient_id, med_index)
);

CREATE TABLE findings (
    finding_id        INTEGER PRIMARY KEY,
    patient_id        TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    issue_type        TEXT NOT NULL,              -- interaction, duplicate, renal, contraindication
    rule_id           TEXT NOT NULL,
    drugs             TEXT NOT NULL,              -- JSON array of generics
    table_severity    TEXT,
    final_severity    TEXT,
    reasons           TEXT                        -- JSON
);
CREATE INDEX findings_patient_id ON findings(patient_id);

CREATE TABLE alerts (
    alert_id          INTEGER PRIMARY KEY,
    patient_id        TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    alert_rank        INTEGER NOT NULL,
    issue_type        TEXT NOT NULL,
    rule_id           TEXT NOT NULL,
    severity          TEXT NOT NULL,
    drugs_involved    TEXT NOT NULL,              -- JSON array of generics
    suggested_action  TEXT,
    confidence        REAL,
    reasons           TEXT,
    limitations       TEXT,
    UNIQUE (patient_id, alert_rank)
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
        return (p.patient_id, p.age, p.weight_kg, p.egfr,
                None if p.pregnant is None else int(p.pregnant),
                json.dumps(list(p.diagnoses)), len(p.medications),
                json.dumps(list(p.unreadable_fields)), json.dumps(list(r.notes)))

    conn.executemany(
        "INSERT INTO patients (patient_id, age, weight_kg, egfr, pregnant, diagnoses, "
        "medication_count, unreadable_fields, data_notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [patient_row(r) for r in result.patients])
    conn.executemany(
        "INSERT INTO medications (patient_id, med_index, raw) VALUES (?, ?, ?)",
        [(r.patient.patient_id, m.index, m.raw)
         for r in result.patients for m in r.patient.medications])


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


def build_db(input_dir: Path, db_path: Path = DEFAULT_DB) -> dict[str, int]:
    """Run the pipeline stages built so far over ``input_dir`` and write them to ``db_path``.

    The database is written to a temporary file and moved into place, so a failed build never
    leaves a half-written cache behind.

    Args:
        input_dir: Directory of supplied input files, as for ``run.py --input``.
        db_path: Where to write the database. Replaced if it exists.

    Returns:
        Row count per table.

    Raises:
        SchemaError: The input does not match ``COLUMN_MAP``.
    """
    dataset = load_dataset(input_dir)
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
    parser.add_argument("--input", required=True, type=Path, help="directory of input files")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"default {DEFAULT_DB}")
    args = parser.parse_args(argv)
    counts = build_db(args.input, args.db)
    print(f"built {args.db}")
    for table, count in counts.items():
        print(f"  {table:<17} {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
