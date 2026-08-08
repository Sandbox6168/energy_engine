from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .plugins import TariffProvider, Transform
from .profile import EnergyProfile
from .simulation import SimulationResult, run_simulation


@dataclass(frozen=True, slots=True)
class Scenario:
    """A named, reusable configuration of inputs to a Simulation."""

    name: str
    energy_profile: EnergyProfile
    tariff_provider: TariffProvider
    transforms: Sequence[Transform] = field(default_factory=tuple)

    def run(self) -> SimulationResult:
        return run_simulation(self.energy_profile, self.transforms, self.tariff_provider)


@dataclass(frozen=True, slots=True)
class Comparison:
    """Runs two or more independent Scenarios and presents their Simulation Results side by side."""

    scenarios: Sequence[Scenario]

    def run(self) -> dict[str, SimulationResult]:
        return {scenario.name: scenario.run() for scenario in self.scenarios}
