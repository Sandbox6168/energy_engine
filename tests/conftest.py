from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from core import EnergyProfile, SettlementPeriod, SettlementValue, TariffProvider


@pytest.fixture
def make_period():
    def _make(hour: int, minute: int = 0, day: int = 1) -> SettlementPeriod:
        return SettlementPeriod(datetime(2026, 1, day, hour, minute, tzinfo=timezone.utc))

    return _make


@pytest.fixture
def flat_tariff_provider() -> TariffProvider:
    class FlatTariffProvider:
        def import_rate(self, period: SettlementPeriod) -> Decimal:
            return Decimal("0.25")

        def export_rate(self, period: SettlementPeriod) -> Decimal:
            return Decimal("0.10")

        def standing_charge(self, period: SettlementPeriod) -> Decimal:
            return Decimal("0")

    return FlatTariffProvider()


@pytest.fixture
def two_period_profile(make_period) -> EnergyProfile:
    return EnergyProfile(
        {
            make_period(0): SettlementValue(import_kwh=1.0, export_kwh=0.0),
            make_period(0, 30): SettlementValue(import_kwh=0.0, export_kwh=2.0),
        }
    )
