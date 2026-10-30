"""The pipeline in one call. What run.py ships and what eval/ measures are the same code.

Stages land phase by phase. A stage that is not built yet is ``None`` on every patient result,
so the evaluation harness can tell "not built" apart from "built and found nothing".

    load      Phase 1    adapter + validation                          (built)
    resolve   Phase 2    written line -> generic(s), or abstain        (built)
    rules     Phase 3    interaction, duplicate, renal, contraindication -> findings
    output    Phase 6    findings -> alerts at the table severity (docs/DECISIONS.md D-015)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from medsafe.data.adapter import Dataset
from medsafe.data.schema import Patient
from medsafe.explain.data_quality import data_quality_notes
from medsafe.resolve import thresholds
from medsafe.resolve.resolver import NameIndex, Resolution, Resolver

STAGES = ("load", "resolve", "rules", "output")
BUILT_STAGES = ("load", "resolve")


@dataclass(frozen=True)
class Settings:
    """Every tunable threshold, in one place. ``eval/sweep.py`` sweeps these on the dev split.

    Defaults come from ``resolve/thresholds.py``, where the swept values are recorded.
    """

    min_confidence: float = thresholds.MIN_CONFIDENCE
    min_margin: float = thresholds.MIN_MARGIN
    min_prefix_length: int = thresholds.MIN_PREFIX_LENGTH


@dataclass(frozen=True)
class PatientResult:
    """Everything the pipeline produced for one patient. Unbuilt stages are None."""

    patient: Patient
    notes: tuple[str, ...]                          # data-quality notes, never silently incomplete
    resolutions: tuple[Resolution, ...] | None = None   # Phase 2: one per medication, same order
    findings: tuple[Any, ...] | None = None         # Phase 3: every finding
    alerts: tuple[Any, ...] | None = None           # Phase 6: what the predictions file holds


@dataclass(frozen=True)
class PipelineResult:
    """The whole run: settings used, stages built, and one result per loaded patient."""

    settings: Settings
    stages_built: tuple[str, ...]
    patients: tuple[PatientResult, ...]


def build_resolver(dataset: Dataset, settings: Settings = Settings(),
                   rank_cache: dict | None = None) -> Resolver:
    """A resolver over the dataset's drug and combination tables at ``settings``' thresholds."""
    index = NameIndex.build(dataset.drugs, dataset.combinations)
    return Resolver(index, settings.min_confidence, settings.min_margin,
                    settings.min_prefix_length, rank_cache=rank_cache)


def run_pipeline(dataset: Dataset, settings: Settings = Settings(),
                 resolver: Resolver | None = None) -> PipelineResult:
    """Run every built stage over a loaded dataset.

    Args:
        dataset: Output of ``medsafe.data.adapter.load_dataset``.
        settings: Thresholds for the stages that read them.
        resolver: A prepared resolver to reuse (the sweep passes one per setting); built from
            ``dataset`` and ``settings`` when None.

    Returns:
        One ``PatientResult`` per loaded patient, in input order. Deterministic: the same
        dataset and settings always give the same result.
    """
    resolver = resolver if resolver is not None else build_resolver(dataset, settings)
    results = tuple(
        PatientResult(patient=patient, notes=data_quality_notes(patient),
                      resolutions=tuple(resolver.resolve(m.raw) for m in patient.medications))
        for patient in dataset.patients)
    return PipelineResult(settings=settings, stages_built=BUILT_STAGES, patients=results)
