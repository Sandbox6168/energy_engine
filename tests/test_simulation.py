from __future__ import annotations

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
