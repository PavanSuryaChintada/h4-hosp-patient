"""What a rule produces: a finding, with the evidence that triggered it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from medsafe.data.schema import SEVERITIES

SEVERITY_RANK = {severity: rank for rank, severity in enumerate(reversed(SEVERITIES))}
# minor 0 < moderate 1 < major 2 < contraindicated 3


@dataclass(frozen=True)
class Finding:
    """One safety issue for one patient. Severity and action are the table's, word for word.

    ``evidence`` holds the values that triggered it, for example ``{"egfr": 28, "threshold":
    30}``, so every alert can be traced to a table row and a patient value. A finding without
    evidence is a bug.
    """

    issue_type: str                      # interaction | duplicate_therapy | renal_dose | contraindication
    drugs: tuple[str, ...]               # generics, sorted
    severity: str                        # the table's severity, unchanged
    action: str                          # the table's recommended action, unchanged
    rule_id: str
    evidence: dict[str, Any] = field(default_factory=dict)
    raw_drugs: tuple[str, ...] = ()      # the lines as written, for the reader
    confidence: float = 1.0              # resolution confidence of the least certain line
