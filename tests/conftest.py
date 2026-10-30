"""Shared paths, markers and fixtures.

Two kinds of test data:
  * tests/fixtures/mini/ - a hand-written miniature of the pack, committed, always available.
  * the H4 pack itself at data/pack/ (or MEDSAFE_DATA_DIR) - not committed. Tests that need it
    are marked ``requires_pack`` and skip with a clear reason when it is absent. The day-to-day
    slice is the first 100 training patients, read from the pack at test time.
"""

from __future__ import annotations

import importlib.util
from dataclasses import replace
from pathlib import Path

import pytest

from eval.pack import data_dir, pack_present
from medsafe.data.adapter import Dataset, load_dataset

REPO_ROOT = Path(__file__).resolve().parents[1]
MINI_DIR = REPO_ROOT / "tests" / "fixtures" / "mini"
SLICE_SIZE = 100

requires_pack = pytest.mark.skipif(
    not pack_present(), reason="H4 data pack not found at data/pack (set MEDSAFE_DATA_DIR)")
requires_scorer = pytest.mark.skipif(
    not (pack_present() and importlib.util.find_spec("pandas")
         and importlib.util.find_spec("numpy")),
    reason="needs the H4 pack and pandas + numpy (pip install -r requirements-dev.txt)")


@pytest.fixture(scope="session")
def mini() -> Dataset:
    """The mini fixtures' training patients and tables."""
    return load_dataset(MINI_DIR, "train")


@pytest.fixture(scope="session")
def pack_train() -> Dataset:
    """All 1,500 training patients and the real reference tables."""
    return load_dataset(data_dir(), "train")


@pytest.fixture(scope="session")
def train_slice(pack_train: Dataset) -> Dataset:
    """The first 100 training patients, for fast day-to-day checks on real data."""
    return replace(pack_train, patients=pack_train.patients[:SLICE_SIZE])
