"""The submission files, in exactly the format the official scorer reads."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from conftest import MINI_DIR, requires_scorer
from eval import official
from medsafe.data.adapter import Dataset
from medsafe.output import policy
from medsafe.output.writer import (PREDICTION_COLUMNS, RESOLUTION_COLUMNS, token_key,
                                   write_predictions, write_resolution)
from medsafe.pipeline import Settings, run_pipeline


@pytest.fixture
def written(mini: Dataset, tmp_path: Path) -> Path:
    """The mini training patients' submission files, written to tmp_path."""
    result = run_pipeline(mini, Settings())
    write_resolution(result, tmp_path / "H4_resolution.csv")
    write_predictions([], tmp_path / "H4_predictions.csv")
    return tmp_path


def rows(path: Path) -> list[dict[str, str]]:
    """A CSV file's rows."""
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_resolution_file_has_one_row_per_distinct_line(written: Path) -> None:
    resolution = rows(written / "H4_resolution.csv")
    keys = [(r["patient_id"], token_key(r["written_token"])) for r in resolution]
    assert len(keys) == len(set(keys)) == 18          # 19 lines; one repeated with extra spaces
    assert list(resolution[0])[:3] == list(RESOLUTION_COLUMNS)
    assert all("," not in r["resolved_generic"] for r in resolution)


def test_resolution_file_says_how_each_line_was_resolved(written: Path) -> None:
    by_token = {r["written_token"]: r for r in rows(written / "H4_resolution.csv")}
    assert by_token["Physiotherapy"]["resolved_generic"] == ""
    assert by_token["Physiotherapy"]["method"] == "non_drug"
    assert by_token["Shelcal 500 BD"]["resolved_generic"] == "calcium carbonate;cholecalciferol"
    assert {r["verify_manually"] for r in by_token.values()} == {"N"}


def test_predictions_file_with_no_alerts_is_header_only(written: Path) -> None:
    lines = (written / "H4_predictions.csv").read_text(encoding="utf-8").splitlines()
    assert lines == [",".join(PREDICTION_COLUMNS)]


def test_minor_alerts_are_detected_but_not_submitted() -> None:
    alerts = [{"severity": s} for s in ("contraindicated", "major", "moderate", "minor")]
    assert policy.EMIT_MINOR is False
    assert [a["severity"] for a in policy.submitted(alerts)] == ["contraindicated", "major", "moderate"]
    assert len(policy.submitted(alerts, emit_minor=True)) == 4


@requires_scorer
def test_official_scorer_accepts_our_files(written: Path, tmp_path: Path) -> None:
    """The organisers' evaluate.py reads our files, extra columns included, and scores the
    mini fixtures' resolution as fully correct."""
    report = official.score(written / "H4_predictions.csv", written / "H4_resolution.csv",
                            MINI_DIR / "train_labels.csv", MINI_DIR / "train_resolution.csv",
                            tmp_path / "score.json")
    assert report["components"]["resolution_accuracy"] == 1.0
    assert report["counts"]["tokens_without_prediction"] == 0
    assert report["primary_score"] == pytest.approx(0.15)
