"""Type coercion, range checks and the structured load report.

The adapter hands each source cell to the coercers here. A cell that cannot be coerced, or falls
outside its sane range, raises ``RowError``; the adapter skips that row and records it in the
``LoadReport`` with its index and reason. A file that does not match ``COLUMN_MAP`` at all raises
``SchemaError`` and stops the load. Nothing is dropped silently.

Missing stays ``None`` through every coercer. ``0`` is a value, never a stand-in for missing.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, TypeVar

Number = TypeVar("Number", int, float)

# Inclusive sane ranges. A value outside these is a data error, not a clinical finding.
RANGES: dict[str, tuple[float, float]] = {
    "age": (0, 120),
    "weight_kg": (0, 300),
    "egfr": (0, 200),
}

# Internal fields that must be mapped to a source column. Every other field may be mapped to
# None in COLUMN_MAP when the source has no such column, and then loads as None.
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "patients": ("patient_id", "medications"),
    "drugs": ("generic", "drug_class", "renal_adjust"),
    "interactions": ("drug_a", "drug_b", "severity"),
}

TRUE_TOKENS = frozenset({"true", "t", "yes", "y", "1"})
FALSE_TOKENS = frozenset({"false", "f", "no", "n", "0"})


class SchemaError(ValueError):
    """The file as a whole does not match COLUMN_MAP. Raised, never skipped: fix the map."""


class RowError(ValueError):
    """One row cannot be loaded. The adapter catches it, skips the row and records why."""

    def __init__(self, reason: str, field: str | None, detail: str) -> None:
        """Build a row error.

        Args:
            reason: Machine-readable cause: ``bad_type``, ``out_of_range``, ``missing_value``,
                ``duplicate``, ``self_pair`` or ``malformed_row``.
            field: Internal field at fault, or ``None`` when the whole row is malformed.
            detail: Human-readable message including the offending value.
        """
        super().__init__(detail)
        self.reason = reason
        self.field = field
        self.detail = detail

    @property
    def code(self) -> str:
        """Reason key used in the report breakdown, for example ``out_of_range:egfr``."""
        return f"{self.reason}:{self.field}" if self.field else self.reason


@dataclass(frozen=True)
class SkippedRow:
    """One row the loader refused: where it was and why."""

    index: int               # 0-based position of the record in the file, header excluded
    code: str                # reason key, for example "bad_type:age"
    detail: str              # human-readable, includes the offending value


@dataclass
class LoadReport:
    """What one loader did with one file: rows read, loaded, skipped, and why."""

    kind: str = ""
    source: str = ""
    rows_read: int = 0
    loaded: int = 0
    skipped_rows: list[SkippedRow] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def skipped(self) -> int:
        """Number of rows refused."""
        return len(self.skipped_rows)

    @property
    def reasons(self) -> dict[str, int]:
        """Skipped-row count per reason key, sorted by key."""
        return dict(sorted(Counter(row.code for row in self.skipped_rows).items()))

    def record_skip(self, index: int, error: RowError) -> SkippedRow:
        """Record that the row at ``index`` was refused for ``error``. Returns the record."""
        row = SkippedRow(index=index, code=error.code, detail=error.detail)
        self.skipped_rows.append(row)
        return row

    def summary(self) -> str:
        """Multi-line plain-text summary: counts, then the reason breakdown, then notes."""
        lines = [f"{self.kind:<12} {self.source}: {self.rows_read} read, "
                 f"{self.loaded} loaded, {self.skipped} skipped"]
        lines += [f"  skipped {code}: {count}" for code, count in self.reasons.items()]
        lines += [f"  note: {note}" for note in self.notes]
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form of the report, including every skipped row."""
        return {
            "kind": self.kind,
            "source": self.source,
            "rows_read": self.rows_read,
            "loaded": self.loaded,
            "skipped": self.skipped,
            "reasons": self.reasons,
            "skipped_rows": [vars(row) for row in self.skipped_rows],
            "notes": list(self.notes),
        }


def require_columns(columns: Iterable[str], column_map: Mapping[str, str | None],
                    kind: str, source: str) -> list[str]:
    """Check a file's columns against its COLUMN_MAP entry before any row is read.

    Args:
        columns: Column names present in the file.
        column_map: Internal field to source column name, or ``None`` if the source lacks it.
        kind: Table kind: ``patients``, ``drugs`` or ``interactions``.
        source: File path, for the error message.

    Returns:
        One note per optional field mapped to ``None``, saying it loads as ``None``.

    Raises:
        SchemaError: A required field is unmapped, or a mapped column is not in the file.
    """
    available = set(columns)
    unmapped = [name for name in REQUIRED_FIELDS[kind] if column_map.get(name) is None]
    if unmapped:
        raise SchemaError(f"{source}: required field(s) {unmapped} have no source column "
                          f"in COLUMN_MAP['{kind}']")
    missing = [f"{name} -> {column!r}" for name, column in column_map.items()
               if column is not None and column not in available]
    if missing:
        raise SchemaError(f"{source}: column(s) not found: {', '.join(missing)}. "
                          f"File has: {sorted(available)}. "
                          f"Edit COLUMN_MAP['{kind}'] in medsafe/data/adapter.py.")
    return [f"{name}: no source column mapped, loaded as None"
            for name, column in column_map.items() if column is None]


def _missing(value: Any, name: str, required: bool) -> None:
    """Return None for a missing value, or raise if the field is required."""
    if required:
        raise RowError("missing_value", name, f"{name} is required but missing")
    return None


def coerce_text(value: Any, name: str, *, required: bool = False) -> str | None:
    """Coerce a cell to stripped text. Blank text is missing and becomes ``None``.

    Raises:
        RowError: The value is a JSON list or object, or the field is required and missing.
    """
    if value is None:
        return _missing(value, name, required)
    if isinstance(value, (dict, list)):
        raise RowError("bad_type", name, f"{name}={value!r} is not text")
    text = str(value).strip()
    return text if text else _missing(value, name, required)


def coerce_int(value: Any, name: str, *, required: bool = False) -> int | None:
    """Coerce a cell to an int. Accepts ``72``, ``"72"`` and ``"72.0"``; refuses ``"72.5"``.

    Raises:
        RowError: Not a whole number, or required and missing.
    """
    if value is None:
        return _missing(value, name, required)
    if isinstance(value, bool):
        raise RowError("bad_type", name, f"{name}={value!r} is not a whole number")
    if isinstance(value, int):
        return value
    number = _to_float(value, name, "a whole number")
    if not number.is_integer():
        raise RowError("bad_type", name, f"{name}={value!r} is not a whole number")
    return int(number)


def coerce_float(value: Any, name: str, *, required: bool = False) -> float | None:
    """Coerce a cell to a finite float.

    Raises:
        RowError: Not a finite number, or required and missing.
    """
    if value is None:
        return _missing(value, name, required)
    if isinstance(value, bool):
        raise RowError("bad_type", name, f"{name}={value!r} is not a number")
    return _to_float(value, name, "a number")


def _to_float(value: Any, name: str, expected: str) -> float:
    """Parse a finite float or raise a ``bad_type`` RowError."""
    try:
        number = float(str(value).strip())
    except ValueError:
        raise RowError("bad_type", name, f"{name}={value!r} is not {expected}") from None
    if not math.isfinite(number):
        raise RowError("bad_type", name, f"{name}={value!r} is not {expected}")
    return number


def coerce_bool(value: Any, name: str, *, required: bool = False) -> bool | None:
    """Coerce a cell to a bool from ``true/false``, ``yes/no``, ``y/n``, ``t/f`` or ``1/0``.

    Raises:
        RowError: Not a recognised boolean token, or required and missing.
    """
    if value is None:
        return _missing(value, name, required)
    if isinstance(value, bool):
        return value
    token = str(value).strip().lower()
    if token in TRUE_TOKENS:
        return True
    if token in FALSE_TOKENS:
        return False
    raise RowError("bad_type", name, f"{name}={value!r} is not a yes/no value")


def check_range(value: Number | None, name: str) -> Number | None:
    """Return ``value`` unchanged if it is ``None`` or inside ``RANGES[name]``.

    Raises:
        RowError: The value falls outside the inclusive sane range for ``name``.
    """
    if value is None or name not in RANGES:
        return value
    low, high = RANGES[name]
    if not low <= value <= high:
        raise RowError("out_of_range", name, f"{name}={value} is outside {low:g}-{high:g}")
    return value
