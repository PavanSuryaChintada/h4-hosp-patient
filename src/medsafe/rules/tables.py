"""The reference tables, indexed once for the rules. The tables are authoritative."""

from __future__ import annotations

from dataclasses import dataclass

from medsafe.data.adapter import Dataset
from medsafe.data.schema import Contraindication, DuplicateGroup, InteractionPair, RenalRule


@dataclass(frozen=True)
class RuleTables:
    """Lookups the four rules need, built from a loaded dataset."""

    interactions: dict[frozenset[str], InteractionPair]
    renal: dict[str, tuple[RenalRule, ...]]            # per generic, lowest threshold first
    drug_group: dict[str, str | None]                  # generic -> duplicate group id
    groups: dict[str, DuplicateGroup]
    contraindications: dict[str, tuple[Contraindication, ...]]
    pregnancy_letter: dict[str, str | None]            # generic -> A, B, C, D, X, N

    @classmethod
    def build(cls, dataset: Dataset) -> RuleTables:
        """Index a dataset's reference tables."""
        renal: dict[str, list[RenalRule]] = {}
        for rule in dataset.renal_rules:
            if rule.egfr_below is not None and rule.severity is not None:
                renal.setdefault(rule.generic, []).append(rule)
        contra: dict[str, list[Contraindication]] = {}
        for row in dataset.contraindications:
            if row.severity is not None:
                contra.setdefault(row.generic, []).append(row)
        return cls(
            interactions={frozenset((i.drug_a, i.drug_b)): i for i in dataset.interactions
                          if i.severity is not None},
            renal={g: tuple(sorted(rules, key=lambda r: r.egfr_below)) for g, rules in renal.items()},
            drug_group={g: d.duplicate_group for g, d in dataset.drugs.items()},
            groups=dict(dataset.duplicate_groups),
            contraindications={g: tuple(rows) for g, rows in contra.items()},
            pregnancy_letter={g: d.pregnancy_category for g, d in dataset.drugs.items()},
        )
