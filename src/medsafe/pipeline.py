"""The pipeline in one call. What run.py ships and what eval/ measures are the same code.

    load      Phase 1    adapter + validation
    resolve   Phase 2    written line -> generic(s), or abstain
    rules     Phase 3    regimen, conditions, and the four checks -> findings (minor included)
    output    Phase 6    findings -> predictions rows: table severity, no minor (D-015, D-018)

One malformed patient never stops the run (D-028). A line the resolver cannot process is
abstained, so it is still written for a person to check; a patient whose rules cannot run gets
no alerts, keeps every resolution row, and is listed in ``PipelineResult.failures`` and the log.
"""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)


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
class Failure:
    """Something the pipeline could not process for one patient, and what went wrong."""

    patient_id: str
    stage: str                  # resolve (one line), notes, or rules (the whole patient)
    error: str                  # exception type and message
    line: str | None = None     # the written line, for a resolve failure


@dataclass(frozen=True)
class PipelineResult:
    """The whole run: settings used, stages built, one result per loaded patient, and every
    failure that was contained rather than allowed to stop the run."""

    settings: Settings
    stages_built: tuple[str, ...]
    patients: tuple[PatientResult, ...]
    failures: tuple[Failure, ...] = ()


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
        One ``PatientResult`` per loaded patient, in input order, and the failures contained on
        the way. A patient whose rules failed has empty findings and alerts and ``rules=None``.
        Deterministic: the same dataset and settings always give the same result.
    """
    resolver = resolver if resolver is not None else build_resolver(dataset, settings)
    tables = RuleTables.build(dataset)
    results, failures = [], []

    def contain(patient_id: str, stage: str, error: Exception, line: str | None = None) -> None:
        """Record and log a failure; the run goes on."""
        failures.append(Failure(patient_id, stage, f"{type(error).__name__}: {error}", line))
        logger.warning("patient %s: %s failed (%s: %s)%s; continuing", patient_id, stage,
                       type(error).__name__, error, f" on line {line!r}" if line else "")

    def resolve(patient_id: str, raw: str) -> Resolution:
        """Resolve one line; a line that cannot be processed is abstained, never dropped."""
        try:
            return resolver.resolve(raw)
        except Exception as error:      # noqa: BLE001 - contained, logged, and listed
            contain(patient_id, "resolve", error, raw)
            return Resolution(raw, "", (), "abstained", 0.0, abstain_reason="error")

    for patient in dataset.patients:
        resolutions = tuple(resolve(patient.patient_id, m.raw) for m in patient.medications)
        try:
            notes = data_quality_notes(patient)
        except Exception as error:      # noqa: BLE001
            contain(patient.patient_id, "notes", error)
            notes = ("Data-quality check could not run for this patient; its values are unchecked.",)
        try:
            rules = run_rules(patient, resolutions, tables)
            alerts = tuple(submitted(alert_rows(patient, rules)))
        except Exception as error:      # noqa: BLE001
            contain(patient.patient_id, "rules", error)
            results.append(PatientResult(patient=patient, notes=notes, resolutions=resolutions,
                                         findings=(), alerts=(), rules=None))
            continue
        results.append(PatientResult(
            patient=patient, notes=notes, resolutions=resolutions,
            findings=rules.findings, alerts=alerts, rules=rules))
    return PipelineResult(settings=settings, stages_built=BUILT_STAGES, patients=tuple(results),
                          failures=tuple(failures))
