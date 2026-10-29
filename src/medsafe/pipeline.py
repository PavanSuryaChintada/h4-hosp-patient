"""The pipeline in one call. What run.py ships and what eval/ measures are the same code.

Stages land phase by phase. A stage that is not built yet is ``None`` on every patient result,
so the evaluation harness can tell "not built" apart from "built and found nothing".

    load      Phase 1    adapter + validation               (built)
    resolve   Phase 2    brand/misspelling -> generic       resolutions
    rules     Phase 3    interaction, duplicate, renal, ... findings
    severity  Phase 4    patient-context re-scoring         findings.final_severity
    collapse  Phase 5    alert graph, minimal drug set      alerts
    budget    Phase 6    rank and cap                       alerts, alerts_suppressed
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from medsafe.data.adapter import Dataset
from medsafe.data.schema import Patient
from medsafe.explain.data_quality import data_quality_notes

STAGES = ("load", "resolve", "rules", "severity", "collapse", "budget")
BUILT_STAGES = ("load",)


@dataclass(frozen=True)
class Settings:
    """Every tunable threshold, in one place. ``eval/sweep.py`` sweeps these.

    The defaults are the phase docs' starting guesses. When Phases 2 and 6 land, the defaults
    move to ``resolve/thresholds.py`` and ``budget/rank.py`` and are read from there.
    """

    alert_cap: int = 5             # Phase 6 ALERT_CAP: alerts shipped per patient, highs exempt
    min_confidence: float = 0.72   # Phase 2 MIN_CONFIDENCE: below this, resolution abstains
    min_margin: float = 0.05       # Phase 2 MIN_MARGIN: top-two gap below this, abstains


@dataclass(frozen=True)
class PatientResult:
    """Everything the pipeline produced for one patient. Unbuilt stages are None."""

    patient: Patient
    notes: tuple[str, ...]                     # data-quality notes, never silently incomplete
    resolutions: tuple[Any, ...] | None = None # Phase 2: one per medication, same order
    findings: tuple[Any, ...] | None = None    # Phases 3-4: every finding, before collapse
    alerts: tuple[Any, ...] | None = None      # Phases 5-6: what ships
    alerts_suppressed: int | None = None       # Phase 6


@dataclass(frozen=True)
class PipelineResult:
    """The whole run: settings used, stages built, and one result per loaded patient."""

    settings: Settings
    stages_built: tuple[str, ...]
    patients: tuple[PatientResult, ...]


def run_pipeline(dataset: Dataset, settings: Settings = Settings()) -> PipelineResult:
    """Run every built stage over a loaded dataset.

    Args:
        dataset: Output of ``medsafe.data.adapter.load_dataset``.
        settings: Thresholds for the stages that read them.

    Returns:
        One ``PatientResult`` per loaded patient, in input order. Deterministic: the same
        dataset and settings always give the same result.
    """
    results = tuple(PatientResult(patient=patient, notes=data_quality_notes(patient))
                    for patient in dataset.patients)
    return PipelineResult(settings=settings, stages_built=BUILT_STAGES, patients=results)
