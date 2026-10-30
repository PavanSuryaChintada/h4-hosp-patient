"""The seam between the pipeline and the harness, and the diagnosis of every miss.

``trace_patient`` converts one ``PatientResult`` into a ``PatientTrace``. A stage the pipeline
has not built is None and stays None. When a phase lands, replace its ``NotImplementedError``
below with a converter from that phase's records; nothing else in ``eval/`` changes.
"""

from __future__ import annotations

from collections.abc import Sequence

from eval.metrics import covers
from eval.records import Issue, PatientTrace, Resolution, TruthToken
from medsafe.output.writer import token_key
from medsafe.pipeline import PatientResult, PipelineResult


def _unconverted(stage: str, phase: int) -> NotImplementedError:
    """The error raised when a stage has landed but this seam was not updated for it."""
    return NotImplementedError(f"Phase {phase} now produces {stage}; add its converter to "
                               f"eval/trace.py so the harness can score it")


def trace_patient(result: PatientResult) -> PatientTrace:
    """Convert one patient's pipeline output into the records the harness scores."""
    if result.findings is not None:
        raise _unconverted("findings", 3)
    if result.alerts is not None:
        raise _unconverted("alerts", 6)
    patient_id = result.patient.patient_id
    resolutions = None if result.resolutions is None else tuple(
        Resolution(patient_id, entry.raw, frozenset(r.generics), r.method)
        for entry, r in zip(result.patient.medications, result.resolutions))
    return PatientTrace(patient_id=patient_id, resolutions=resolutions, findings=None,
                        shipped=None)


def traces_from(result: PipelineResult) -> dict[str, PatientTrace]:
    """One trace per loaded patient, keyed by patient id, in input order."""
    return {r.patient.patient_id: trace_patient(r) for r in result.patients}


def diagnose(issue: Issue, trace: PatientTrace | None, tokens: Sequence[TruthToken]) -> str:
    """Why a true issue was missed, walking the pipeline stage by stage.

    Args:
        issue: A true issue that no shipped alert covers.
        trace: The patient's trace, or None if the adapter did not load the patient.
        tokens: True resolutions of this patient's written lines.

    Returns:
        The first stage where the issue was lost, in plain English.
    """
    if trace is None:
        return "patient not loaded: dropped by the adapter (see the load report)"
    if trace.resolutions is None:
        return "name resolution not built yet (Phase 2): no drug on this list was checked"
    ours = {token_key(r.written_token): r for r in trace.resolutions}
    for drug in sorted(issue.drugs):
        lines = [t for t in tokens if drug in t.generics]
        if lines and not any(drug in ours[token_key(t.written_token)].generics
                             for t in lines if token_key(t.written_token) in ours):
            line = lines[0]
            got = ours.get(token_key(line.written_token))
            if got is None or not got.generics:
                return f"'{line.written_token}' was not resolved, so {drug} was never checked"
            return (f"'{line.written_token}' resolved to {';'.join(sorted(got.generics))} "
                    f"instead of {';'.join(sorted(line.generics))}")
    if trace.findings is None:
        return "every drug resolved; rule engine not built yet (Phase 3)"
    found = [f for f in trace.findings if covers(f, issue)]
    if not found:
        return f"no {issue.issue_type} finding for {' + '.join(sorted(issue.drugs))}"
    if trace.shipped is None:
        return "output not built yet (Phase 6)"
    return "found but not written to the predictions file"
