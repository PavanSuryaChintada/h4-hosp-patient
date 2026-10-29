"""Medsafe entry point.

    python run.py --input <dir> --output <file>

Stub until the pipeline phases land: parses arguments and fails cleanly.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


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


def main(argv: list[str] | None = None) -> int:
    """Run the pipeline. Returns the process exit code."""
    args = parse_args(argv)
    print(f"medsafe: input={args.input} output={args.output}")
    print("pipeline not built yet")
    return 1


if __name__ == "__main__":
    sys.exit(main())
