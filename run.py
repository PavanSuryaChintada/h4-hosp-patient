"""Medsafe entry point.

    python run.py --input <dir> --output <file>

Reads the supplied input files directly through ``medsafe.data.adapter``. Never reads
``data/medsafe.db``: that database is a convenience cache built afterwards by
``tools/build_db.py``, and the pipeline gives identical output with it deleted.

Phase 1 stage: loads and validates the input, prints the load report, and writes one row per
medication as written (patient_id, med_index, raw). The Phase 6 alert writer replaces this.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from medsafe.data.adapter import load_dataset  # noqa: E402
from medsafe.data.schema import Patient  # noqa: E402
from medsafe.data.validate import SchemaError  # noqa: E402

LOAD_STAGE_COLUMNS = ("patient_id", "med_index", "raw")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line.

    Args:
        argv: Arguments to parse; defaults to ``sys.argv[1:]``.

    Returns:
        Namespace with ``input`` (directory of supplied files) and ``output`` (file to write).
    """
    parser = argparse.ArgumentParser(description="Flag drug safety risks in patient medication lists.")
    parser.add_argument("--input", required=True, type=Path, help="directory holding the supplied input files")
    parser.add_argument("--output", required=True, type=Path, help="file to write the results to")
    return parser.parse_args(argv)


def write_load_stage(patients: list[Patient], path: Path) -> int:
    """Write one row per medication as loaded, in input order. Returns the row count.

    Phase 1 placeholder output; the Phase 6 writer in ``medsafe.output`` replaces it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [(p.patient_id, m.index, m.raw) for p in patients for m in p.medications]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(LOAD_STAGE_COLUMNS)
        writer.writerows(rows)
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    """Run the pipeline and return the process exit code: 0 ok, 2 input does not match the schema."""
    args = parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    started = time.perf_counter()
    try:
        dataset = load_dataset(args.input)
    except SchemaError as error:
        print(f"input error: {error}", file=sys.stderr)
        return 2

    for report in dataset.reports:
        print(report.summary())
    rows = write_load_stage(dataset.patients, args.output)
    print(f"patients processed: {len(dataset.patients)}")
    print(f"medications written: {rows} -> {args.output}")
    print(f"runtime: {time.perf_counter() - started:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
