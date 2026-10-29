"""The fixture labels are right. A wrong label is a wrong metric, so the label logic is tested
like the metrics: on cases worked out by hand from the Round 1 rules."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from fixture_labels import Context, Entry, interaction_severity, label_patient, near_miss_reason  # noqa: E402


def labels(ctx: Context, *drugs: str) -> dict[tuple[str, tuple[str, ...]], str]:
    """Label a patient on ``drugs`` (written as their generic names): {(type, drugs): severity}."""
    entries = [Entry(i, name, name, ("generic",)) for i, name in enumerate(drugs)]
    return {(i.issue_type, i.drugs): i.severity for i in label_patient("P1", ctx, entries)}


ADULT = Context(age=50, weight_kg=70.0, egfr=80, pregnant=False)


def test_renal_follows_thresholds() -> None:
    assert labels(Context(70, 70.0, 28, False), "metformin")[("renal", ("metformin",))] == "high"
    assert labels(Context(70, 70.0, 40, False), "metformin")[("renal", ("metformin",))] == "medium"
    assert ("renal", ("metformin",)) not in labels(ADULT, "metformin")


def test_major_interaction_is_high() -> None:
    assert labels(ADULT, "warfarin", "ibuprofen")[("interaction", ("ibuprofen", "warfarin"))] == "high"


def test_moderate_bleeding_interaction_rises_with_age_or_low_weight() -> None:
    assert interaction_severity("moderate", "bleed", ADULT) == ("medium", "table moderate")
    assert interaction_severity("moderate", "bleed", Context(80, 70.0, 80, False))[0] == "high"
    assert interaction_severity("moderate", "bleed", Context(50, 45.0, 80, False))[0] == "high"
    assert interaction_severity("minor", "bleed", Context(90, 40.0, 20, False))[0] == "low"


def test_pregnancy_contraindication_only_when_pregnant() -> None:
    pregnant = Context(30, 60.0, 100, True)
    assert labels(pregnant, "ramipril")[("contraindication", ("ramipril",))] == "high"
    assert labels(pregnant, "diclofenac")[("contraindication", ("diclofenac",))] == "medium"
    assert ("contraindication", ("ramipril",)) not in labels(ADULT, "ramipril")


def test_duplicates_same_drug_and_same_class() -> None:
    assert labels(ADULT, "omeprazole", "pantoprazole")[
        ("duplicate", ("omeprazole", "pantoprazole"))] == "medium"
    entries = [Entry(0, "Pan 40", "pantoprazole", ("brand",)),
               Entry(1, "pantoprazole", "pantoprazole", ("generic",))]
    found = {(i.issue_type, i.rule_id) for i in label_patient("P1", ADULT, entries)}
    assert ("duplicate", "DUP-SAME-PAN") in found


def test_near_miss_reasons() -> None:
    ctx = Context(70, 70.0, 43, False)
    entries = [Entry(0, "metformin 500", "metformin", ("generic", "strength"))]
    (renal,) = [i for i in label_patient("P1", ctx, entries) if i.issue_type == "renal"]
    assert near_miss_reason(renal, ctx, entries) == "eGFR 43 is just under the 45 threshold"

    hard = [Entry(0, "Glyycomet500", "metformin", ("brand", "misspelled", "squashed"))]
    (renal,) = [i for i in label_patient("P1", Context(70, 70.0, 20, False), hard)
                if i.issue_type == "renal"]
    assert near_miss_reason(renal, ctx, hard).startswith("hard-to-read name: 'Glyycomet500'")
