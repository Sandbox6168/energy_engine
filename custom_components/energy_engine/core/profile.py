from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .settlement import SettlementPeriod


@dataclass(frozen=True, slots=True)
class SettlementValue:
    """Import/export kWh for a single Settlement Period."""

    import_kwh: float
    export_kwh: float


@dataclass(frozen=True, slots=True)
class EnergyProfile:
    """A timeline of import/export kWh, one value per Settlement Period."""

    values: Mapping[SettlementPeriod, SettlementValue]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", dict(self.values))

    @property
    def settlement_periods(self) -> list[SettlementPeriod]:
        return sorted(self.values, key=lambda period: period.start)
