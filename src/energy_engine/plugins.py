from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol

from .profile import EnergyProfile
from .settlement import SettlementPeriod


class DataSource(Protocol):
    """Produces an initial Energy Profile for a date range."""

    def get_energy_profile(self, start: date, end: date) -> EnergyProfile: ...


class TariffProvider(Protocol):
    """Supplies the import rate, export rate, and standing charge for a Settlement Period."""

    def import_rate(self, period: SettlementPeriod) -> Decimal: ...

    def export_rate(self, period: SettlementPeriod) -> Decimal: ...

    def standing_charge(self, period: SettlementPeriod) -> Decimal: ...


class Transform(Protocol):
    """Takes an Energy Profile and returns a new one; never mutates the profile it's given."""

    def apply(self, profile: EnergyProfile, tariff_provider: TariffProvider) -> EnergyProfile: ...
