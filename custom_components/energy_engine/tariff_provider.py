"""HA Tariff Provider: entity-only (ADR-0001), reads import rate, export rate, and
standing charge from HA's own recorder statistics rather than calling Octopus's API."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from homeassistant.core import HomeAssistant

from .core import SettlementPeriod
from .recorder_utils import (
    MissingHistoryError,
    MissingStatisticsError,
    StatKind,
    async_fetch_daily_value_from_history,
    async_fetch_settlement_values,
    clamp_to_completed_period,
    local_day_start,
)
from .run_report import Issue


class HassTariffProvider:
    """Rates pre-fetched from HA entities; satisfies the core's TariffProvider Protocol."""

    def __init__(
        self,
        import_rates: dict[SettlementPeriod, Decimal],
        export_rates: dict[SettlementPeriod, Decimal],
        standing_charges: dict[date, Decimal],
    ) -> None:
        self._import_rates = import_rates
        self._export_rates = export_rates
        self._standing_charges = standing_charges

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
) -> tuple[HassTariffProvider | None, list[Issue], list[Issue]]:
    """Returns (tariff_provider, errors, warnings). `tariff_provider` is None if
    `errors` is non-empty (ADR-0003) - except the standing charge, which falls back
    to the entity's current live state (and a warning) rather than erroring, since a
    single flat value is an acceptable stand-in for "no history at all"."""
    start_dt = local_day_start(start)
    end_dt = clamp_to_completed_period(local_day_start(end + timedelta(days=1)))

    errors: list[Issue] = []
    warnings: list[Issue] = []

    import_values = export_values = standing_values = None
    try:
        import_values, import_degraded = await async_fetch_settlement_values(
            hass, import_rate_entity_id, start_dt, end_dt, StatKind.INSTANTANEOUS
        )
    except MissingStatisticsError as err:
        errors.append(Issue(import_rate_entity_id, "import_rate", str(err)))
    try:
        export_values, export_degraded = await async_fetch_settlement_values(
            hass, export_rate_entity_id, start_dt, end_dt, StatKind.INSTANTANEOUS
        )
    except MissingStatisticsError as err:
        errors.append(Issue(export_rate_entity_id, "export_rate", str(err)))

    try:
        standing_values, standing_degraded = await async_fetch_daily_value_from_history(
            hass, standing_charge_entity_id, start, end
        )
    except MissingHistoryError:
        standing_values, fallback_issue = _fallback_standing_charge(
            hass, standing_charge_entity_id, start, end
        )
        (warnings if standing_values else errors).append(fallback_issue)
    else:
        if standing_degraded:
            warnings.append(
                Issue(
                    standing_charge_entity_id,
                    "standing_charge",
                    f"Standing charge for some days fell back to {standing_charge_entity_id}'s "
                    "earliest known state because its history doesn't reach that far back.",
                )
            )

    if errors:
        return None, errors, warnings

    if import_degraded:
        warnings.append(
            Issue(
                import_rate_entity_id,
                "import_rate",
                "Rates priced from hourly-averaged data for Settlement Periods older than "
                "HA's short-term statistics retention window, not true half-hourly rates.",
            )
        )
    if export_degraded:
        warnings.append(
            Issue(
                export_rate_entity_id,
                "export_rate",
                "Rates priced from hourly-averaged data for Settlement Periods older than "
                "HA's short-term statistics retention window, not true half-hourly rates.",
            )
        )

    return (
        HassTariffProvider(_to_decimal(import_values), _to_decimal(export_values), standing_values),
        errors,
        warnings,
    )


def _fallback_standing_charge(
    hass: HomeAssistant, entity_id: str, start: date, end: date
) -> tuple[dict[date, Decimal] | None, Issue]:
    """No recorded history at all for the standing-charge entity: fall back to its
    current live state as a flat value across the whole range (ADR-0003), rather than
    erroring outright - a single value is an acceptable stand-in for a standing charge,
    which rarely changes.
    """
    state = hass.states.get(entity_id)
    value = _as_decimal(state.state) if state is not None else None
    if value is None:
        return None, Issue(
            entity_id,
            "standing_charge",
            f"No recorded state history at all for {entity_id}, and its current state "
            "isn't a usable value either.",
        )

    values = {}
    day = start
    while day < end:
        values[day] = value
        day += timedelta(days=1)

    return values, Issue(
        entity_id,
        "standing_charge",
        f"No recorded state history at all for {entity_id}; using its current value "
        f"({value}) for the whole range.",
    )


def _as_decimal(state: str) -> Decimal | None:
    try:
        return Decimal(state)
    except (InvalidOperation, TypeError):
        return None


def _to_decimal(values: dict[SettlementPeriod, float]) -> dict[SettlementPeriod, Decimal]:
    return {period: Decimal(str(value)) for period, value in values.items()}
