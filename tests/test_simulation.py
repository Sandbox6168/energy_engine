from __future__ import annotations

from datetime import date
from decimal import Decimal

from core import EnergyProfile, SettlementValue, run_simulation


def test_no_transforms_is_a_straight_replay(two_period_profile, flat_tariff_provider):
    result = run_simulation(two_period_profile, transforms=[], tariff_provider=flat_tariff_provider)

    assert result.profile is two_period_profile


def test_prices_import_and_export_at_their_own_rates(two_period_profile, flat_tariff_provider):
    result = run_simulation(two_period_profile, transforms=[], tariff_provider=flat_tariff_provider)

    # 1.0 kWh import @ 0.25 - 2.0 kWh export @ 0.10
    assert result.total_cost == Decimal("0.25") - Decimal("0.20")


def test_transform_output_feeds_into_pricing(make_period, flat_tariff_provider):
    class DoubleImport:
        def apply(self, profile, tariff_provider):
            return EnergyProfile(
                {
                    period: SettlementValue(value.import_kwh * 2, value.export_kwh)
                    for period, value in profile.values.items()
                }
            )

    profile = EnergyProfile({make_period(0): SettlementValue(import_kwh=1.0, export_kwh=0.0)})

    result = run_simulation(profile, transforms=[DoubleImport()], tariff_provider=flat_tariff_provider)

    assert result.total_cost == Decimal("0.50")


def test_standing_charge_is_applied_once_per_day_not_per_period(make_period):
    class StandingChargeProvider:
        def import_rate(self, period):
            return Decimal("0")

        def export_rate(self, period):
            return Decimal("0")

        def standing_charge(self, day: date) -> Decimal:
            return Decimal("0.50")

    profile = EnergyProfile(
        {
            make_period(0, day=1): SettlementValue(import_kwh=0.0, export_kwh=0.0),
            make_period(0, 30, day=1): SettlementValue(import_kwh=0.0, export_kwh=0.0),
            make_period(0, day=2): SettlementValue(import_kwh=0.0, export_kwh=0.0),
        }
    )

    result = run_simulation(profile, transforms=[], tariff_provider=StandingChargeProvider())

    # Two distinct days at 0.50/day, not three periods at 0.50/period.
    assert result.total_cost == Decimal("1.00")
