"""Guards on what the scoring path may touch.

The pipeline (run.py and src/medsafe/) must never read the training labels or resolutions
(E2: the detector and the labels share the published rules, so letting it see the answers would
make every number meaningless), never import the harness or the tools, never touch the SQLite
cache, and never open a network connection.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import REPO_ROOT

SCORING_PATH = [REPO_ROOT / "run.py", *sorted((REPO_ROOT / "src").rglob("*.py"))]
FORBIDDEN = {
    "reads the labels": re.compile(r"train_labels|train_resolution|test_truth|test_resolution"),
    "imports the harness or tools": re.compile(r"^\s*(from|import)\s+(eval|tools)\b", re.MULTILINE),
    "imports sqlite3": re.compile(r"^\s*(import sqlite3|from sqlite3\b)", re.MULTILINE),
    "imports a network or LLM client": re.compile(
        r"^\s*(import|from)\s+(urllib|http|requests|httpx|socket|anthropic|openai)\b", re.MULTILINE),
}


@pytest.mark.parametrize("rule", sorted(FORBIDDEN))
def test_scoring_path_never(rule: str) -> None:
    offenders = [p.relative_to(REPO_ROOT).as_posix() for p in SCORING_PATH
                 if FORBIDDEN[rule].search(p.read_text(encoding="utf-8"))]
    assert not offenders, f"{rule}: {offenders}"


def test_guard_covers_the_whole_package() -> None:
    assert any(p.name == "resolver.py" for p in SCORING_PATH)
    assert all(isinstance(p, Path) and p.is_file() for p in SCORING_PATH)
