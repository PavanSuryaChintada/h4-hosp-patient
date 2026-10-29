"""Evaluation harness: our mirror of the scoring, plus near-miss tracking (Phase 7).

    python -m eval.run      headline numbers, missed near-misses, timestamped report
    python -m eval.sweep    threshold sweep, written to docs/sweep.md
"""

import sys
from pathlib import Path

# Run from a checkout without installing: make src/medsafe importable.
_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
