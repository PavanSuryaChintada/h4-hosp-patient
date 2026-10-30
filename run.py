"""Medsafe entry point: writes the two submission files from the H4 data pack.

    python run.py --input data/pack/data --split test --out submission

Reads the supplied files directly through ``medsafe.data.adapter``. Never reads
``data/medsafe.db``: that database is a convenience cache built afterwards by
``tools/build_db.py``, and the pipeline gives identical output with it deleted.

Writes ``<output>/H4_resolution.csv`` (every written medication line resolved to its generics,
or flagged for manual check) and ``<output>/H4_predictions.csv`` (one row per alert: the table's
severity and action, minor issues left out).
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from medsafe.data.adapter import SPLITS, load_dataset  # noqa: E402
from medsafe.data.validate import SchemaError  # noqa: E402
from medsafe.output.writer import (PREDICTIONS_FILE, RESOLUTION_FILE,  # noqa: E402
                                   write_predictions, write_resolution)
from medsafe.pipeline import Settings, run_pipeline  # noqa: E402

DEFAULT_INPUT = Path("data/pack/data")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line.

    Args:
        argv: Arguments to parse; defaults to ``sys.argv[1:]``.

    Returns:
        Namespace with ``input`` (the pack's data folder), ``split`` (train or test) and
        ``output`` (folder to write the two submission files into).
    """
    parser = argparse.ArgumentParser(description="Flag drug safety risks in patient medication lists.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help=f"the pack's data folder (default {DEFAULT_INPUT})")
    parser.add_argument("--split", choices=SPLITS, default="test", help="which patients to run")
    parser.add_argument("--output", "--out", dest="output", type=Path, default=Path("submission"),
                        help="folder for H4_predictions.csv and H4_resolution.csv")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the pipeline. Returns the exit code: 0 ok, 2 input does not match the schema."""
    import logging
    args = parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    started = time.perf_counter()
    try:
        dataset = load_dataset(args.input, args.split)
    except SchemaError as error:
        print(f"input error: {error}", file=sys.stderr)
        return 2

    for report in dataset.reports:
        print(report.summary())
    result = run_pipeline(dataset, Settings())
    rows = write_resolution(result, args.output / RESOLUTION_FILE)
    alerts = write_predictions([a for p in result.patients for a in p.alerts],
                               args.output / PREDICTIONS_FILE)
    findings = Counter(f.severity for p in result.patients for f in p.findings)

    methods = Counter(r.method for p in result.patients for r in p.resolutions)
    lines = sum(methods.values())
    print(f"patients processed: {len(result.patients)}")
    print(f"medication lines: {lines} ({rows} resolution rows) - "
          + ", ".join(f"{method} {count}" for method, count in sorted(methods.items())))
    print(f"lines to verify manually: {methods['abstained']}")
    print(f"findings: {sum(findings.values())} (" + ", ".join(f"{s} {n}" for s, n in sorted(findings.items())) + ")")
    print(f"alerts submitted: {alerts} (minor findings are shown, not submitted)")
    print(f"wrote {args.output / RESOLUTION_FILE} and {args.output / PREDICTIONS_FILE}")
    print(f"runtime: {time.perf_counter() - started:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
