"""Our reading of the scoring function, isolated in one function: ``score``.

The brief: recall on serious issues, with a penalty for low-severity alert volume. A system that
flags everything scores near zero; a system that flags nothing scores zero.

When the real ``evaluate.py`` arrives, replace ``score`` wholesale with its logic and keep this
version alongside it, so the two can be compared on the same run.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# One low-value alert per patient costs five points of serious recall. Our guess, not the
# brief's number: replace when the real penalty shape is known.
LOW_VALUE_ALERT_PENALTY = 0.05


def score(metrics: Mapping[str, Any]) -> float:
    """Serious-issue recall minus a penalty per low-value alert per patient, floored at zero.

    A low-value alert is one that covers no serious true issue: a false alarm, or a true issue
    the ground truth rates low. Judging "low" by the ground truth rather than by the alert's
    own label means a system cannot dodge the penalty by calling everything high.

    Args:
        metrics: Output of ``eval.metrics.compute_metrics``; reads ``serious_recall`` and
            ``low_value_alerts_per_patient``.

    Returns:
        A score in [0, 1]. Flagging nothing gives 0; flagging every pair gives 0 after the floor.
    """
    recall = metrics["serious_recall"] or 0.0
    return max(0.0, recall - LOW_VALUE_ALERT_PENALTY * metrics["low_value_alerts_per_patient"])
