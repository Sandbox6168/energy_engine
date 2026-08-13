"""HA Data Source: entity-only, reads grid import/export energy from HA's own
recorder statistics (ADR-0002) rather than polling a device or API directly."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from homeassistant.core import HomeAssistant

from .core import EnergyProfile, SettlementValue
from .recorder_utils import (
    MissingStatisticsError,
    StatKind,
    async_fetch_settlement_values,
    clamp_to_completed_period,
)
from .run_report import Issue


class HassDataSource:
    """A pre-fetched Energy Profile, satisfying the core's synchronous DataSource protocol.

    The recorder I/O is inherently async, so it happens up front in `async_build`;
    this class just hands back the result the core's plugin contract expects.
    """

    def __init__(self, profile: EnergyProfile) -> None:
        self._profile = profile

    def get_energy_profile(self, start: date, end: date) -> EnergyProfile:
        return self._profile


async def async_build_data_source(
    hass: HomeAssistant,
    import_entity_id: str,
    export_entity_id: str,
    start: date,
    end: date,
) -> tuple[HassDataSource | None, list[Issue], list[Issue]]:
    """Returns (data_source, errors, warnings). `data_source` is None if `errors` is
    non-empty - per ADR-0003, a missing-data entity is never silently worked around
    for the Data Source's own usage figures."""
    start_dt = datetime.combine(start, time.min, tzinfo=UTC)
    end_dt = clamp_to_completed_period(
        datetime.combine(end, time.min, tzinfo=UTC) + timedelta(days=1)
    )

    errors: list[Issue] = []
    warnings: list[Issue] = []

    import_values = export_values = None
    try:
        import_values, import_degraded = await async_fetch_settlement_values(
            hass, import_entity_id, start_dt, end_dt, StatKind.CUMULATIVE
        )
    except MissingStatisticsError as err:
        errors.append(Issue(import_entity_id, "import", str(err)))
    try:
        export_values, export_degraded = await async_fetch_settlement_values(
            hass, export_entity_id, start_dt, end_dt, StatKind.CUMULATIVE
        )
    except MissingStatisticsError as err:
        errors.append(Issue(export_entity_id, "export", str(err)))

    if errors:
        return None, errors, warnings

    if import_degraded:
        warnings.append(
            Issue(
                import_entity_id,
                "import",
                "Usage priced from hourly-averaged data for Settlement Periods older than "
                "HA's short-term statistics retention window, not true half-hourly readings.",
            )
        )
    if export_degraded:
        warnings.append(
            Issue(
                export_entity_id,
                "export",
                "Usage priced from hourly-averaged data for Settlement Periods older than "
                "HA's short-term statistics retention window, not true half-hourly readings.",
            )
        )

    values = {
        period: SettlementValue(import_kwh=import_values[period], export_kwh=export_values[period])
        for period in import_values
    }
    return HassDataSource(EnergyProfile(values)), errors, warnings
