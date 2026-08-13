"""HA Data Source: entity-only, reads grid import/export energy from HA's own
recorder statistics (ADR-0002) rather than polling a device or API directly."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from homeassistant.core import HomeAssistant

from .core import EnergyProfile, SettlementValue
from .recorder_utils import StatKind, async_fetch_settlement_values, clamp_to_completed_period


class HassDataSource:
    """A pre-fetched Energy Profile, satisfying the core's synchronous DataSource protocol.

    The recorder I/O is inherently async, so it happens up front in `async_build`;
    this class just hands back the result the core's plugin contract expects.
    """

    def __init__(self, profile: EnergyProfile, precision_caveat: str | None) -> None:
        self._profile = profile
        self.precision_caveat = precision_caveat

    def get_energy_profile(self, start: date, end: date) -> EnergyProfile:
        return self._profile


async def async_build_data_source(
    hass: HomeAssistant,
    import_entity_id: str,
    export_entity_id: str,
    start: date,
    end: date,
) -> HassDataSource:
    start_dt = datetime.combine(start, time.min, tzinfo=UTC)
    end_dt = clamp_to_completed_period(
        datetime.combine(end, time.min, tzinfo=UTC) + timedelta(days=1)
    )

    import_values, import_degraded = await async_fetch_settlement_values(
        hass, import_entity_id, start_dt, end_dt, StatKind.CUMULATIVE
    )
    export_values, export_degraded = await async_fetch_settlement_values(
        hass, export_entity_id, start_dt, end_dt, StatKind.CUMULATIVE
    )

    values = {
        period: SettlementValue(import_kwh=import_values[period], export_kwh=export_values[period])
        for period in import_values
    }

    caveat = None
    if import_degraded or export_degraded:
        caveat = (
            "Usage priced from hourly-averaged data for Settlement Periods older than "
            "HA's short-term statistics retention window, not true half-hourly readings."
        )

    return HassDataSource(EnergyProfile(values), caveat)
