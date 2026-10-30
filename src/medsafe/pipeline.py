"""The pipeline in one call. What run.py ships and what eval/ measures are the same code.

    load      Phase 1    adapter + validation
    resolve   Phase 2    written line -> generic(s), or abstain
    rules     Phase 3    regimen, conditions, and the four checks -> findings (minor included)
    output    Phase 6    findings -> predictions rows: table severity, no minor (D-015, D-018)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from medsafe.data.adapter import Dataset
from medsafe.data.schema import Patient
from medsafe.explain.data_quality import data_quality_notes
from medsafe.output.policy import alert_rows, submitted
from medsafe.resolve import thresholds
from medsafe.resolve.resolver import NameIndex, Resolution, Resolver
from medsafe.rules.engine import RuleResult, run_rules
from medsafe.rules.tables import RuleTables
from medsafe.rules.types import Finding

STAGES = ("load", "resolve", "rules", "output")
BUILT_STAGES = STAGES


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
    resolutions: tuple[Resolution, ...] | None = None   # one per medication, same order
    findings: tuple[Finding, ...] | None = None     # every finding, minor included
    alerts: tuple[dict[str, Any], ...] | None = None    # what the predictions file holds
    rules: RuleResult | None = None                 # regimen and conditions, for explanations


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
    """Run every stage over a loaded dataset.

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
    tables = RuleTables.build(dataset)
    results = []
    for patient in dataset.patients:
        resolutions = tuple(resolver.resolve(m.raw) for m in patient.medications)
        rules = run_rules(patient, resolutions, tables)
        results.append(PatientResult(
            patient=patient, notes=data_quality_notes(patient), resolutions=resolutions,
            findings=rules.findings,
            alerts=tuple(submitted(alert_rows(patient.patient_id, rules.findings))),
            rules=rules))
    return PipelineResult(settings=settings, stages_built=BUILT_STAGES, patients=tuple(results))
