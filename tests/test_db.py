"""The SQLite database is a convenience cache, never the scoring path."""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest

from medsafe.data.adapter import load_patients

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
DEFAULT_DB = REPO_ROOT / "data" / "medsafe.db"
SQLITE_IMPORT = re.compile(r"^\s*(import sqlite3|from sqlite3\b)", re.MULTILINE)


def run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run a repo script with this interpreter from the repo root; fail the test on error."""
    return subprocess.run([sys.executable, *args], cwd=REPO_ROOT, check=True,
                          capture_output=True, text=True)


def build(db: Path) -> sqlite3.Connection:
    """Build the database from the fixtures at ``db`` and open it with foreign keys on."""
    run("tools/build_db.py", "--input", str(FIXTURES_DIR), "--db", str(db))
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@pytest.fixture
def default_db(tmp_path: Path) -> Iterator[Path]:
    """The default database path, with any database already there restored afterwards."""
    backup = tmp_path / "medsafe.db.backup"
    existed = DEFAULT_DB.exists()
    if existed:
        shutil.copy2(DEFAULT_DB, backup)
    yield DEFAULT_DB
    if existed:
        shutil.copy2(backup, DEFAULT_DB)
    else:
        DEFAULT_DB.unlink(missing_ok=True)


def test_pipeline_output_is_identical_with_the_database_deleted(tmp_path: Path,
                                                                default_db: Path) -> None:
    run("tools/build_db.py", "--input", "tests/fixtures")
    assert default_db.exists()
    with_db, without_db = tmp_path / "with_db.csv", tmp_path / "without_db.csv"
    run("run.py", "--input", "tests/fixtures", "--output", str(with_db))

    default_db.unlink()
    run("run.py", "--input", "tests/fixtures", "--output", str(without_db))

    assert not default_db.exists(), "run.py must never create the database"
    assert with_db.read_bytes() == without_db.read_bytes()
    assert with_db.read_text(encoding="utf-8").count("\n") > 1


def test_same_input_gives_the_same_output(tmp_path: Path) -> None:
    first, second = tmp_path / "first.csv", tmp_path / "second.csv"
    run("run.py", "--input", "tests/fixtures", "--output", str(first))
    run("run.py", "--input", "tests/fixtures", "--output", str(second))
    assert first.read_bytes() == second.read_bytes()


def test_scoring_path_never_imports_sqlite() -> None:
    scoring_path = [REPO_ROOT / "run.py", *sorted((REPO_ROOT / "src").rglob("*.py"))]
    offenders = [p.relative_to(REPO_ROOT) for p in scoring_path
                 if SQLITE_IMPORT.search(p.read_text(encoding="utf-8"))]
    assert not offenders


def test_build_db_loads_patients_and_medications_with_null_for_missing(tmp_path: Path) -> None:
    patients = load_patients(FIXTURES_DIR / "patients.csv")
    with closing(build(tmp_path / "medsafe.db")) as conn:
        assert conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 200
        assert conn.execute("SELECT COUNT(*) FROM medications").fetchone()[0] == \
            sum(len(p.medications) for p in patients)
        for column in ("age", "weight_kg", "egfr", "pregnant"):
            nulls = conn.execute(f"SELECT COUNT(*) FROM patients WHERE {column} IS NULL").fetchone()[0]
            assert nulls == sum(getattr(p, column) is None for p in patients), column
        assert conn.execute("SELECT COUNT(*) FROM patients WHERE egfr = 0").fetchone()[0] == 0
        metric = conn.execute("SELECT value FROM metrics WHERE name = 'load.patients.loaded'")
        assert metric.fetchone()[0] == 200


def test_build_db_has_foreign_keys_and_patient_id_indexes(tmp_path: Path) -> None:
    with closing(build(tmp_path / "medsafe.db")) as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        for table in ("medications", "findings", "alerts", "collapse_results"):
            targets = {row[2] for row in conn.execute(f"PRAGMA foreign_key_list({table})")}
            assert targets == {"patients"}, table
            leading = {conn.execute(f"PRAGMA index_info('{row[1]}')").fetchone()[2]
                       for row in conn.execute(f"PRAGMA index_list({table})")}
            assert "patient_id" in leading, table
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO medications (patient_id, med_index, raw) "
                         "VALUES ('NOBODY', 0, 'x')")


def test_build_db_replaces_rather_than_appends(tmp_path: Path) -> None:
    db = tmp_path / "medsafe.db"
    build(db).close()
    with closing(build(db)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 200


def test_canned_queries_return_the_right_rows(tmp_path: Path) -> None:
    """Seed the later-phase tables by hand and check what each query reports."""
    db = tmp_path / "medsafe.db"
    with closing(build(db)) as conn:
        conn.executemany(
            "INSERT INTO findings (patient_id, issue_type, rule_id, drugs, final_severity) "
            "VALUES (?, 'interaction', ?, '[]', ?)",
            [("P0001", "R1", "high"), ("P0001", "R2", "high"), ("P0002", "R3", "low")])
        conn.executemany(
            "INSERT INTO alerts (patient_id, alert_rank, issue_type, rule_id, severity, "
            "drugs_involved) VALUES (?, ?, 'interaction', ?, ?, '[]')",
            [("P0001", 1, "R1", "high"), ("P0001", 2, "R2", "high"), ("P0002", 1, "R3", "low")])
        conn.execute("UPDATE medications SET abstained = 1, abstain_reason = 'ambiguous', "
                     "confidence = 0.7 WHERE patient_id = 'P0003' AND med_index = 0")
        missed = [{"patient_id": "P0009", "rule_id": "WAR-NSAID-01",
                   "drugs": ["warfarin", "ibuprofen"], "reason": "brand unresolved"}]
        conn.execute("INSERT INTO metrics VALUES ('near_miss_recall', 0.9, ?)",
                     (json.dumps({"missed": missed}),))
        conn.commit()

    def query(name: str) -> list[str]:
        out = run("tools/query.py", name, "--db", str(db)).stdout.splitlines()
        return [line.split() for line in out[2:]]

    assert query("most-alerts")[0][:3] == ["P0001", "2", "2"]
    assert query("abstained")[0][:2] == ["P0003", "0"]
    assert query("severity") == [["high", "2", "2", "0.01", "0.01"],
                                 ["low", "1", "1", "0.01", "0.01"]]
    assert query("missed-near-misses")[0][:2] == ["P0009", "WAR-NSAID-01"]
    assert ["patients", "200"] in query("counts")


def test_degraded_patients_are_stored_and_queryable(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    shutil.copytree(FIXTURES_DIR, input_dir)
    patients_csv = input_dir / "patients.csv"
    text = patients_csv.read_text(encoding="utf-8").splitlines(keepends=True)
    fields = text[1].split(",")
    fields[3] = "n/k?"                     # P0001's egfr column
    text[1] = ",".join(fields)
    patients_csv.write_text("".join(text), encoding="utf-8")

    db = tmp_path / "medsafe.db"
    run("tools/build_db.py", "--input", str(input_dir), "--db", str(db))
    with closing(sqlite3.connect(db)) as conn:
        row = conn.execute("SELECT egfr, unreadable_fields, data_notes FROM patients "
                           "WHERE patient_id = 'P0001'").fetchone()
        assert row[0] is None and json.loads(row[1]) == ["egfr"]
        assert "renal checks not verifiable" in json.loads(row[2])[0]
        degraded = conn.execute("SELECT value FROM metrics "
                                "WHERE name = 'load.patients.loaded_degraded'").fetchone()[0]
        assert degraded == 1
    out = run("tools/query.py", "degraded", "--db", str(db)).stdout
    assert "P0001" in out and "renal checks not verifiable" in out


def test_query_without_a_database_says_how_to_build_it(tmp_path: Path) -> None:
    result = subprocess.run([sys.executable, "tools/query.py", "counts",
                             "--db", str(tmp_path / "absent.db")],
                            cwd=REPO_ROOT, capture_output=True, text=True)
    assert result.returncode == 1
    assert "tools/build_db.py" in result.stderr
