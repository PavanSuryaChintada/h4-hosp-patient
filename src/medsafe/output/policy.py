"""Which alerts go into the predictions file. One policy, measured, in one place.

Minor issues are still detected and shown in the UI; they are left out of H4_predictions.csv.
An alert on a true minor issue earns nothing in serious, near-miss or graded recall (graded
recall counts non-minor issues only) and costs 0.25 noise units, so once precision is high it
only lowers the score. Measured both ways in docs/DECISIONS.md D-018 (``python -m eval.floor``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

EMIT_MINOR = False


def submitted(alerts: Iterable[Mapping[str, Any]], emit_minor: bool = EMIT_MINOR) -> list[Mapping[str, Any]]:
    """The alerts that go into the predictions file: all of them, or all but the minor ones."""
    return [alert for alert in alerts if emit_minor or alert["severity"] != "minor"]
