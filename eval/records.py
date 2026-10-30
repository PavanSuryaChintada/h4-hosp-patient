"""Plain records the harness scores.

Ground truth is read into these (``eval/truth.py``) and pipeline output is converted into them
(``eval/trace.py``), so the metrics never depend on pipeline internals. Severities and issue
types use the pack's published vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass

from medsafe.data.schema import SERIOUS, SEVERITIES  # noqa: F401  (re-exported for eval/)


@dataclass(frozen=True)
class Issue:
    """One true issue for one patient, as train_labels.csv states it."""

    patient_id: str
    issue_type: str                       # interaction | duplicate_therapy | renal_dose | contraindication
    drugs: frozenset[str]                 # generics
    severity: str                         # contraindicated | major | moderate | minor
    near_miss: bool = False
    action: str = ""

    @property
    def serious(self) -> bool:
        """True for contraindicated and major: the issues serious recall counts."""
        return self.severity in SERIOUS


@dataclass(frozen=True)
class Alert:
    """One alert or finding the pipeline raised for one patient."""

    patient_id: str
    issue_type: str
    drugs: frozenset[str]
    severity: str


@dataclass(frozen=True)
class TruthToken:
    """One written medication line and the generics it really is (empty: not a medicine)."""

    patient_id: str
    written_token: str
    generics: frozenset[str]
    token_kind: str                       # exact_brand, misspelled_brand, non_drug, ...


@dataclass(frozen=True)
class Resolution:
    """What the pipeline resolved one written line to. Empty generics: none."""

    patient_id: str
    written_token: str
    generics: frozenset[str]
    method: str                           # exact | synonym | parts | prefix | fuzzy | non_drug | abstained


@dataclass(frozen=True)
class PatientTrace:
    """Everything the harness needs from the pipeline for one loaded patient.

    A stage that is not built yet is None, which the harness reports as "not built" rather than
    "found nothing".
    """

    patient_id: str
    resolutions: tuple[Resolution, ...] | None
    findings: tuple[Alert, ...] | None
    shipped: tuple[Alert, ...] | None     # what the predictions file holds
