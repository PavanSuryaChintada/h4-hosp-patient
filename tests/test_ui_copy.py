"""Guards on the demo UI's text and on what the UI is allowed to compute.

1. The word "safe" never appears in any UI string or in the data file the UI reads
   (00-MASTER rule 4: never claim a patient is safe; say no issue was found in what was seen).
2. The UI holds no clinical thresholds (09-ui.md R1). An eGFR compared to a number in the
   browser is a second renal rule that can drift from the pipeline's.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import REPO_ROOT

UI = REPO_ROOT / "ui"
UI_TEXT = sorted([*(UI / "src").rglob("*.ts"), *(UI / "src").rglob("*.tsx"), *(UI / "src").rglob("*.css"),
                  *(UI / "src").rglob("*.json"), *(UI / "public").rglob("*.json"), UI / "index.html"])
SAFE = re.compile(r"\bsafe\b", re.IGNORECASE)
EGFR_THRESHOLD = re.compile(r"egfr\w*\s*[<>]=?\s*\d|\d\s*[<>]=?\s*\w*egfr", re.IGNORECASE)
CODE = [p for p in UI_TEXT if p.suffix in (".ts", ".tsx")]


def test_ui_sources_found() -> None:
    assert any(p.name == "main.tsx" for p in UI_TEXT)


@pytest.mark.parametrize("path", UI_TEXT, ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_no_ui_string_says_safe(path: Path) -> None:
    hits = [m.group(0) for m in SAFE.finditer(path.read_text(encoding="utf-8"))]
    assert not hits, f"'safe' appears {len(hits)} time(s)"


@pytest.mark.parametrize("path", CODE, ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_ui_code_holds_no_egfr_threshold(path: Path) -> None:
    hits = [m.group(0) for m in EGFR_THRESHOLD.finditer(path.read_text(encoding="utf-8"))]
    assert not hits, f"eGFR compared to a number in the UI: {hits}"
