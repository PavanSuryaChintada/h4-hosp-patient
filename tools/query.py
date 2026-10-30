"""Canned queries over data/medsafe.db.

    python tools/query.py <name> [--db data/medsafe.db] [--limit 20]

    most-alerts          patients with the most alerts
    abstained            every medication the resolver declined to resolve
    severity             by severity: every finding detected, and the alerts submitted
                         (minor findings are detected and shown, never submitted: D-018)
    missed-near-misses   near-misses the pipeline did not catch, with the reason for each
    degraded             patients kept with a field that could not be read, and the note
    counts               rows per table: which phases have filled the database so far

Build the database first with ``python tools/build_db.py --input data/pack/data``. Opened
read-only.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import NamedTuple

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "medsafe.db"


class Query(NamedTuple):
    """A canned query, and what an empty result means."""

    sql: str
    empty: str


QUERIES: dict[str, Query] = {
    "most-alerts": Query("""
        SELECT p.patient_id, COUNT(*) AS alerts,
               SUM(a.severity IN ('contraindicated', 'major')) AS serious,
               p.medication_count AS medications, p.egfr
        FROM alerts a JOIN patients p ON p.patient_id = a.patient_id
        GROUP BY p.patient_id
        ORDER BY alerts DESC, p.patient_id
        LIMIT :limit""",
        "no alerts yet: the alerts table is filled from Phase 6"),
    "abstained": Query("""
        SELECT patient_id, med_index, raw, normalised, abstain_reason,
               ROUND(confidence, 3) AS confidence
        FROM medications
        WHERE abstained = 1
        ORDER BY patient_id, med_index
        LIMIT :limit""",
        "no abstentions: every line resolved or was recognised as not a medicine"),
    "severity": Query("""
        WITH detected AS (SELECT severity, COUNT(*) AS n FROM findings GROUP BY severity),
             submitted AS (SELECT severity, COUNT(*) AS n FROM alerts GROUP BY severity),
             levels AS (SELECT severity FROM detected UNION SELECT severity FROM submitted),
             cohort AS (SELECT MAX(COUNT(*), 1) AS patients FROM patients)
        SELECT l.severity,
               COALESCE(d.n, 0) AS detected,
               COALESCE(s.n, 0) AS submitted,
               ROUND(COALESCE(d.n, 0) * 1.0 / cohort.patients, 2) AS detected_per_patient,
               ROUND(COALESCE(s.n, 0) * 1.0 / cohort.patients, 2) AS submitted_per_patient
        FROM levels l
        LEFT JOIN detected d ON d.severity IS l.severity
        LEFT JOIN submitted s ON s.severity IS l.severity
        CROSS JOIN cohort
        ORDER BY CASE l.severity WHEN 'contraindicated' THEN 0 WHEN 'major' THEN 1
                                 WHEN 'moderate' THEN 2 WHEN 'minor' THEN 3 ELSE 4 END""",
        "no findings or alerts yet: findings fill from Phase 3, alerts from Phase 6"),
    "missed-near-misses": Query("""
        SELECT json_extract(miss.value, '$.patient_id') AS patient_id,
               json_extract(miss.value, '$.rule_id') AS rule_id,
               json_extract(miss.value, '$.drugs') AS drugs,
               json_extract(miss.value, '$.reason') AS reason
        FROM metrics, json_each(metrics.detail, '$.missed') AS miss
        WHERE metrics.name = 'near_miss_recall'
        ORDER BY patient_id, rule_id
        LIMIT :limit""",
        "no near-miss results recorded: the Phase 7 evaluation harness writes them"),
    "degraded": Query("""
        SELECT patient_id, unreadable_fields, data_notes
        FROM patients
        WHERE unreadable_fields != '[]'
        ORDER BY patient_id
        LIMIT :limit""",
        "no degraded patients: every value was read as written"),
    "counts": Query("""
        SELECT 'patients' AS table_name, COUNT(*) AS n_rows FROM patients
        UNION ALL SELECT 'medications', COUNT(*) FROM medications
        UNION ALL SELECT 'medications resolved', COUNT(resolved_generic) FROM medications
        UNION ALL SELECT 'findings', COUNT(*) FROM findings
        UNION ALL SELECT 'alerts', COUNT(*) FROM alerts
        UNION ALL SELECT 'collapse_results', COUNT(*) FROM collapse_results
        UNION ALL SELECT 'metrics', COUNT(*) FROM metrics""",
        "database is empty"),
}


def run_query(db_path: Path, name: str, limit: int = 20) -> tuple[list[str], list[tuple]]:
    """Run one canned query read-only.

    Args:
        db_path: The SQLite database built by ``tools/build_db.py``.
        name: A key of ``QUERIES``.
        limit: Row cap for the queries that list rows.

    Returns:
        Column names and result rows.
    """
    uri = db_path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        cursor = conn.execute(QUERIES[name].sql, {"limit": limit})
        columns = [column[0] for column in cursor.description]
        return columns, cursor.fetchall()


def format_table(columns: list[str], rows: list[tuple]) -> str:
    """Render rows as a left-aligned plain-text table. NULL shows as a dash."""
    cells = [[("-" if value is None else str(value)) for value in row] for row in rows]
    widths = [max(len(column), *(len(row[i]) for row in cells)) for i, column in enumerate(columns)]
    lines = ["  ".join(column.ljust(width) for column, width in zip(columns, widths)),
             "  ".join("-" * width for width in widths)]
    lines += ["  ".join(cell.ljust(width) for cell, width in zip(row, widths)) for row in cells]
    return "\n".join(line.rstrip() for line in lines)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point. Returns the exit code: 0 ok, 1 no database."""
    parser = argparse.ArgumentParser(
        description="Canned queries over the medsafe SQLite cache.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(line for line in __doc__.splitlines()[3:10]))
    parser.add_argument("name", choices=QUERIES)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"default {DEFAULT_DB}")
    parser.add_argument("--limit", type=int, default=20, help="row cap for listing queries")
    args = parser.parse_args(argv)

    if not args.db.is_file():
        print(f"no database at {args.db}. Build it with: "
              f"python tools/build_db.py --input <dir>", file=sys.stderr)
        return 1
    columns, rows = run_query(args.db, args.name, args.limit)
    if rows:
        print(format_table(columns, rows))
    else:
        print(f"(no rows) {QUERIES[args.name].empty}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
