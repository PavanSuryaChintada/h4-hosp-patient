"""The seam between the pipeline and the harness, and the diagnosis of every miss.

``trace_patient`` converts one ``PatientResult`` into a ``PatientTrace``. A stage the pipeline
has not built is None and stays None. When a phase lands, replace its ``NotImplementedError``
below with a converter from that phase's records; nothing else in ``eval/`` changes.
"""

from __future__ import annotations

from collections.abc import Sequence

from eval.metrics import covers
from eval.records import Issue, PatientTrace, TruthMedication
from medsafe.pipeline import PatientResult, PipelineResult


def _unconverted(stage: str, phase: int) -> NotImplementedError:
    """The error raised when a stage has landed but this seam was not updated for it."""
    return NotImplementedError(f"Phase {phase} now produces {stage}; add its converter to "
                               f"eval/trace.py so the harness can score it")


def trace_patient(result: PatientResult) -> PatientTrace:
    """Convert one patient's pipeline output into the records the harness scores."""
    if result.resolutions is not None:
        raise _unconverted("resolutions", 2)
    if result.findings is not None:
        raise _unconverted("findings", 3)
    if result.alerts is not None:
        raise _unconverted("alerts", 6)
    return PatientTrace(patient_id=result.patient.patient_id, resolutions=None, findings=None,
                        shipped=None)


def traces_from(result: PipelineResult) -> dict[str, PatientTrace]:
    """One trace per loaded patient, keyed by patient id, in input order."""
    return {r.patient.patient_id: trace_patient(r) for r in result.patients}


def diagnose(issue: Issue, trace: PatientTrace | None,
             medications: Sequence[TruthMedication]) -> str:
    """Why a true issue was missed, walking the pipeline stage by stage.

    Args:
        issue: A true issue that no shipped alert covers.
        trace: The patient's trace, or None if the adapter did not load the patient.
        medications: Ground truth for this patient's medication lines.

    Returns:
        The first stage where the issue was lost, in plain English.
    """
    if trace is None:
        return "patient not loaded: dropped by the adapter (see the load report)"
    if trace.resolutions is None:
        return "name resolution not built yet (Phase 2): no drug on this list was checked"
    resolved = {r.med_index: r.resolved for r in trace.resolutions}
    for generic in sorted(issue.drugs):
        lines = [m for m in medications if m.generic == generic]
        if lines and not any(resolved.get(m.med_index) == generic for m in lines):
            line = lines[0]
            got = resolved.get(line.med_index)
            if got is None:
                return f"'{line.raw}' abstained, so {generic} was never checked"
            return f"'{line.raw}' resolved to {got} instead of {generic}"
    if trace.findings is None:
        return "rule engine not built yet (Phase 3)"
    found = [f for f in trace.findings if covers(f, issue)]
    if not found:
        return f"no {issue.issue_type} finding for {' + '.join(sorted(issue.drugs))}"
    if trace.shipped is None:
        return "alert budget and output not built yet (Phase 6)"
    severities = ", ".join(sorted({f.severity for f in found}))
    return f"found at {severities} but not shipped: collapsed away or capped out"
