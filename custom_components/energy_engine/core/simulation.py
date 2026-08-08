from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from .plugins import TariffProvider, Transform
from .profile import EnergyProfile


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """The priced output of a Simulation: a transformed Energy Profile plus its total cost."""

    profile: EnergyProfile
    total_cost: Decimal
    precision_caveat: str | None = None


def run_simulation(
    profile: EnergyProfile,
    transforms: Sequence[Transform],
    tariff_provider: TariffProvider,
    *,
    precision_caveat: str | None = None,
) -> SimulationResult:
    """Run an Energy Profile through zero or more Transforms, then price it.

    A pure function: no I/O, deterministic given its inputs.
    """
    for transform in transforms:
        profile = transform.apply(profile, tariff_provider)

    total_cost = _price(profile, tariff_provider)
    return SimulationResult(profile=profile, total_cost=total_cost, precision_caveat=precision_caveat)


def _price(profile: EnergyProfile, tariff_provider: TariffProvider) -> Decimal:
    total = Decimal(0)
    for period, value in profile.values.items():
        total += Decimal(str(value.import_kwh)) * tariff_provider.import_rate(period)
        total -= Decimal(str(value.export_kwh)) * tariff_provider.export_rate(period)
        total += tariff_provider.standing_charge(period)
    return total
