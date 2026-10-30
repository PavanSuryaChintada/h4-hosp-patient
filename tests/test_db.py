"""The SQLite database is a convenience cache, never the scoring path."""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest

from conftest import MINI_DIR, REPO_ROOT

DEFAULT_DB = REPO_ROOT / "data" / "medsafe.db"
OUTPUT_FILES = ("H4_predictions.csv", "H4_resolution.csv")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run a repo script with this interpreter from the repo root; fail the test on error."""
    return subprocess.run([sys.executable, *args], cwd=REPO_ROOT, check=True,
                          capture_output=True, text=True)


def build(db: Path, input_dir: Path = MINI_DIR) -> sqlite3.Connection:
    """Build the database from the mini fixtures at ``db`` and open it with foreign keys on."""
    run("tools/build_db.py", "--input", str(input_dir), "--db", str(db))
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
    run("tools/build_db.py", "--input", str(MINI_DIR))
    assert default_db.exists()
    run("run.py", "--input", str(MINI_DIR), "--split", "train", "--output", str(tmp_path / "with"))
    default_db.unlink()
    run("run.py", "--input", str(MINI_DIR), "--split", "train", "--output", str(tmp_path / "without"))
    assert not default_db.exists(), "run.py must never create the database"
    for name in OUTPUT_FILES:
        assert (tmp_path / "with" / name).read_bytes() == (tmp_path / "without" / name).read_bytes()


def test_same_input_gives_the_same_output(tmp_path: Path) -> None:
    for folder in ("first", "second"):
        run("run.py", "--input", str(MINI_DIR), "--split", "train", "--output", str(tmp_path / folder))
    for name in OUTPUT_FILES:
        assert (tmp_path / "first" / name).read_bytes() == (tmp_path / "second" / name).read_bytes()


def test_build_db_stores_patients_and_resolutions_with_null_for_missing(tmp_path: Path) -> None:
    with closing(build(tmp_path / "medsafe.db")) as conn:
        assert conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 6
        assert conn.execute("SELECT COUNT(*) FROM medications").fetchone()[0] == 19
        male = conn.execute("SELECT pregnant, egfr, weight_kg, sex FROM patients "
                            "WHERE patient_id = 'H4P-MINI0002'").fetchone()
        assert male == (None, None, None, "M")
        assert conn.execute("SELECT COUNT(*) FROM patients WHERE egfr = 0").fetchone()[0] == 0
        rows = dict(conn.execute("SELECT raw, method FROM medications").fetchall())
        assert rows["Physiotherapy"] == "non_drug" and rows["T. PCM 650 SOS"] == "synonym"
        combo = conn.execute("SELECT resolved_generic FROM medications "
                             "WHERE raw = 'Tab Glycomet-GP 1 1-0-1'").fetchone()[0]
        assert combo == "glimepiride;metformin"


def test_build_db_has_foreign_keys_and_patient_id_indexes(tmp_path: Path) -> None:
    with closing(build(tmp_path / "medsafe.db")) as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        for table in ("medications", "findings", "alerts", "collapse_results"):
            assert {row[2] for row in conn.execute(f"PRAGMA foreign_key_list({table})")} == {"patients"}
            leading = {conn.execute(f"PRAGMA index_info('{row[1]}')").fetchone()[2]
                       for row in conn.execute(f"PRAGMA index_list({table})")}
            assert "patient_id" in leading, table
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO medications (patient_id, med_index, raw) VALUES ('NOBODY', 0, 'x')")


def test_build_db_replaces_rather_than_appends(tmp_path: Path) -> None:
    db = tmp_path / "medsafe.db"
    build(db).close()
    with closing(build(db)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 6


def test_canned_queries_return_the_right_rows(tmp_path: Path) -> None:
    """Seed the later-phase tables by hand and check what each query reports."""
    db = tmp_path / "medsafe.db"
    with closing(build(db)) as conn:
        conn.executemany("INSERT INTO findings (patient_id, issue_type, rule_id, drugs, severity) "
                         "VALUES (?, 'interaction', ?, '[]', ?)",
                         [("H4P-MINI0001", "R1", "major"), ("H4P-MINI0001", "R2", "minor")])
        conn.execute("INSERT INTO alerts (patient_id, issue_type, severity, drugs_involved, "
                     "suggested_action, confidence) VALUES ('H4P-MINI0001', 'interaction', "
                     "'major', 'a;b', 'Review', 0.9)")
        conn.execute("UPDATE medications SET abstained = 1, abstain_reason = 'ambiguous' "
                     "WHERE patient_id = 'H4P-MINI0004' AND med_index = 0")
        missed = [{"patient_id": "H4P-MINI0001", "rule_id": "RENAL", "drugs": ["metformin"],
                   "reason": "brand unresolved"}]
        conn.execute("INSERT INTO metrics VALUES ('near_miss_recall', 0.5, ?)",
                     (json.dumps({"missed": missed}),))
        conn.commit()

    def query(name: str) -> list[list[str]]:
        out = run("tools/query.py", name, "--db", str(db)).stdout.splitlines()
        return [line.split() for line in out[2:]]

    assert query("most-alerts")[0][:3] == ["H4P-MINI0001", "1", "1"]
    assert query("abstained")[0][:2] == ["H4P-MINI0004", "0"]
    assert query("severity") == [["major", "1", "1", "0.17", "0.17"], ["minor", "1", "0", "0.17", "0.0"]]
    assert query("missed-near-misses")[0][:2] == ["H4P-MINI0001", "RENAL"]
    assert ["patients", "6"] in query("counts")


def test_degraded_patients_are_stored_and_queryable(tmp_path: Path) -> None:
    folder = tmp_path / "mini"
    shutil.copytree(MINI_DIR, folder)
    path = folder / "patients_train.csv"
    path.write_text(path.read_text(encoding="utf-8").replace(",61.5,28,", ",61.5,n/k?,", 1),
                    encoding="utf-8")
    db = tmp_path / "medsafe.db"
    with closing(build(db, folder)) as conn:
        egfr, fields, notes = conn.execute("SELECT egfr, unreadable_fields, data_notes FROM patients "
                                           "WHERE patient_id = 'H4P-MINI0001'").fetchone()
        assert egfr is None and json.loads(fields) == ["egfr"]
        assert "renal checks not verifiable" in json.loads(notes)[0]
    out = run("tools/query.py", "degraded", "--db", str(db)).stdout
    assert "H4P-MINI0001" in out and "renal checks not verifiable" in out


def test_query_without_a_database_says_how_to_build_it(tmp_path: Path) -> None:
    result = subprocess.run([sys.executable, "tools/query.py", "counts", "--db", str(tmp_path / "x.db")],
                            cwd=REPO_ROOT, capture_output=True, text=True)
    assert result.returncode == 1 and "tools/build_db.py" in result.stderr
