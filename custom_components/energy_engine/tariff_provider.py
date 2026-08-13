"""HA Tariff Provider: entity-only (ADR-0001), reads import rate, export rate, and
standing charge from HA's own recorder statistics rather than calling Octopus's API."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from homeassistant.core import HomeAssistant

from .core import SettlementPeriod
from .recorder_utils import (
    StatKind,
    async_fetch_daily_value_from_history,
    async_fetch_settlement_values,
)


class HassTariffProvider:
    """Rates pre-fetched from HA entities; satisfies the core's TariffProvider Protocol."""

    def __init__(
        self,
        import_rates: dict[SettlementPeriod, Decimal],
        export_rates: dict[SettlementPeriod, Decimal],
        standing_charges: dict[date, Decimal],
        precision_caveat: str | None,
    ) -> None:
        self._import_rates = import_rates
        self._export_rates = export_rates
        self._standing_charges = standing_charges
        self.precision_caveat = precision_caveat

    def import_rate(self, period: SettlementPeriod) -> Decimal:
        return self._import_rates[period]

    def export_rate(self, period: SettlementPeriod) -> Decimal:
        return self._export_rates[period]

    def standing_charge(self, day: date) -> Decimal:
        return self._standing_charges[day]


async def async_build_tariff_provider(
    hass: HomeAssistant,
    import_rate_entity_id: str,
    export_rate_entity_id: str,
    standing_charge_entity_id: str,
    start: date,
    end: date,
) -> HassTariffProvider:
    start_dt = datetime.combine(start, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end, time.min, tzinfo=UTC) + timedelta(days=1)

    import_values, import_degraded = await async_fetch_settlement_values(
        hass, import_rate_entity_id, start_dt, end_dt, StatKind.INSTANTANEOUS
    )
    export_values, export_degraded = await async_fetch_settlement_values(
        hass, export_rate_entity_id, start_dt, end_dt, StatKind.INSTANTANEOUS
    )
    standing_values, standing_degraded = await async_fetch_daily_value_from_history(
        hass, standing_charge_entity_id, start, end
    )

    caveats = []
    if import_degraded or export_degraded:
        caveats.append(
            "Rates priced from hourly-averaged data for Settlement Periods older than "
            "HA's short-term statistics retention window, not true half-hourly rates."
        )
    if standing_degraded:
        caveats.append(
            f"Standing charge for some days fell back to {standing_charge_entity_id}'s "
            "earliest known state because its history doesn't reach that far back."
        )

    return HassTariffProvider(
        _to_decimal(import_values),
        _to_decimal(export_values),
        standing_values,
        " ".join(caveats) or None,
    )


def _to_decimal(values: dict[SettlementPeriod, float]) -> dict[SettlementPeriod, Decimal]:
    return {period: Decimal(str(value)) for period, value in values.items()}
