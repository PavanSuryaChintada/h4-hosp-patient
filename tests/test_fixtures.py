"""The committed fixtures are exactly what the seeded generator writes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
FIXTURE_FILES = ("patients.csv", "drugs.csv", "interactions.csv", "ground_truth.csv",
                 "expected_issues.csv")


def test_committed_fixtures_regenerate_byte_for_byte(tmp_path: Path) -> None:
    subprocess.run([sys.executable, str(REPO_ROOT / "tools" / "make_fixtures.py"),
                    "--out", str(tmp_path)], check=True, capture_output=True)
    for name in FIXTURE_FILES:
        assert (tmp_path / name).read_bytes() == (FIXTURES_DIR / name).read_bytes(), name
