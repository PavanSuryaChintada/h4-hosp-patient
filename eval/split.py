"""A fixed dev / holdout split of the 1,500 training patients.

Every threshold is tuned on ``dev`` (1,200 patients). ``holdout`` (300 patients) is scored only
to report how the tuned pipeline does on patients it was not tuned on. Seeded and computed from
the sorted patient ids, so the split never changes between runs or machines.
"""

from __future__ import annotations

import random
from collections.abc import Iterable

SEED = 2026
HOLDOUT_SIZE = 300
SPLITS = ("dev", "holdout", "train")


def split_ids(patient_ids: Iterable[str], split: str) -> frozenset[str]:
    """The patient ids in one split.

    Args:
        patient_ids: Every training patient id.
        split: ``dev``, ``holdout``, or ``train`` (all of them).

    Returns:
        The ids in that split.
    """
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}; expected one of {SPLITS}")
    ordered = sorted(set(patient_ids))
    if split == "train":
        return frozenset(ordered)
    random.Random(SEED).shuffle(ordered)
    holdout = frozenset(ordered[:HOLDOUT_SIZE])
    return holdout if split == "holdout" else frozenset(ordered) - holdout
