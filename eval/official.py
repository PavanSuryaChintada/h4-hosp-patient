"""Runs the organisers' ``evaluate.py``, unmodified, and returns its score report.

The official scorer needs pandas and numpy (``requirements-dev.txt``); the pipeline itself does
not. It runs in a separate process with ``-I``, exactly as shipped, so our numbers are the
organisers' numbers.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from eval.pack import official_scorer, require_pack


class OfficialScorerError(RuntimeError):
    """The official scorer rejected the files, or could not run."""


def scorer_available() -> bool:
    """True if the pack is present and this interpreter has pandas and numpy."""
    from eval.pack import pack_present
    return (pack_present() and importlib.util.find_spec("pandas") is not None
            and importlib.util.find_spec("numpy") is not None)


def score(predictions: Path, resolution: Path, labels: Path, truth_resolution: Path,
          out_json: Path) -> dict[str, Any]:
    """Score one submission against one truth set with the official scorer.

    Args:
        predictions: Our H4_predictions.csv.
        resolution: Our H4_resolution.csv.
        labels: Truth issues, in the train_labels.csv schema.
        truth_resolution: Truth resolutions, in the train_resolution.csv schema.
        out_json: Where the scorer writes its JSON report.

    Returns:
        The scorer's report: primary_score, components, counts, per-issue-type figures and
        resolution accuracy by token kind.

    Raises:
        OfficialScorerError: The scorer exited non-zero (it exits 2 on any format error).
    """
    require_pack()
    for module in ("pandas", "numpy"):
        if importlib.util.find_spec(module) is None:
            raise OfficialScorerError(f"the official scorer needs {module}: "
                                      f"pip install -r requirements-dev.txt")
    command = [sys.executable, "-I", str(official_scorer()),
               "--submission", str(predictions), "--submission-resolution", str(resolution),
               "--truth", str(labels), "--truth-resolution", str(truth_resolution),
               "--out", str(out_json)]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise OfficialScorerError(completed.stderr.strip() or completed.stdout.strip())
    return json.loads(out_json.read_text(encoding="utf-8"))
