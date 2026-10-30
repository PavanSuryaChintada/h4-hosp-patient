"""Where the H4 data pack lives. The pack is not committed (it sits under the ignored data/).

Default location: ``data/pack/`` inside the repo, holding the pack's README.md, evaluate.py,
baseline/ and data/. Point ``MEDSAFE_DATA_DIR`` at another copy of the pack to override.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK = ROOT / "data" / "pack"


class PackMissing(FileNotFoundError):
    """The data pack is not where the harness looks for it."""


def pack_dir() -> Path:
    """The pack folder: ``MEDSAFE_DATA_DIR`` if set, else ``data/pack``."""
    return Path(os.environ.get("MEDSAFE_DATA_DIR", DEFAULT_PACK))


def data_dir() -> Path:
    """The pack's ``data/`` folder: patients, reference tables and training labels."""
    return pack_dir() / "data"


def official_scorer() -> Path:
    """The organisers' ``evaluate.py``."""
    return pack_dir() / "evaluate.py"


def pack_baseline() -> Path:
    """The organisers' ``baseline/baseline.py``."""
    return pack_dir() / "baseline" / "baseline.py"


def pack_present() -> bool:
    """True if the pack's data folder and official scorer are both there."""
    return (data_dir() / "train_labels.csv").is_file() and official_scorer().is_file()


def require_pack() -> None:
    """Raise ``PackMissing`` with setup instructions if the pack is not there."""
    if not pack_present():
        raise PackMissing(f"H4 data pack not found at {pack_dir()}. Unzip "
                          f"H4_Medication_Safety_Checker so that {data_dir() / 'train_labels.csv'}"
                          f" exists, or set MEDSAFE_DATA_DIR to the pack folder.")
