"""verify_entities: pre-flight check that every entity a config entry's Data Source
and Scenarios rely on can actually supply what run_scenario/run_comparison need for a
given date range, without running a Simulation.

NOTE: written against the documented recorder/entity_registry APIs but not yet
exercised against a running Home Assistant instance - verify against a live HA
before relying on this in production (see recorder_utils.py's equivalent caveat).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta

from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_EXPORT_ENTITY,
    CONF_EXPORT_RATE_ENTITY,
    CONF_IMPORT_ENTITY,
    CONF_IMPORT_RATE_ENTITY,
    CONF_SCENARIO_NAME,
    CONF_STANDING_CHARGE_ENTITY,
)
from .recorder_utils import (
    MissingHistoryError,
    MissingStatisticsError,
    StatKind,
    async_entity_supports_statistics,
    async_fetch_daily_value_from_history,
    async_fetch_settlement_values,
)


@dataclass
class EntityVerification:
    entity_id: str
    role: str
    status: str  # "ok" | "warning" | "error"
    message: str
    suggested_entity: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


async def async_verify_entities(
    hass: HomeAssistant,
    entry_data: dict,
    scenarios: list[dict],
    start: date,
    end: date,
) -> ServiceResponse:
    """Check every entity `entry_data`'s Data Source and `scenarios`' Tariff Providers
    rely on for [start, end), reusing the same recorder logic run_scenario/run_comparison
    would use - but reporting every entity's result instead of raising on the first one."""
    checks: list[tuple[str, str, StatKind]] = [
        (entry_data[CONF_IMPORT_ENTITY], "data_source.import", StatKind.CUMULATIVE),
        (entry_data[CONF_EXPORT_ENTITY], "data_source.export", StatKind.CUMULATIVE),
    ]
    for scenario in scenarios:
        name = scenario[CONF_SCENARIO_NAME]
        checks.append(
            (
                scenario[CONF_IMPORT_RATE_ENTITY],
                f"scenario.{name}.import_rate",
                StatKind.INSTANTANEOUS,
            )
        )
        checks.append(
            (
                scenario[CONF_EXPORT_RATE_ENTITY],
                f"scenario.{name}.export_rate",
                StatKind.INSTANTANEOUS,
            )
        )
        checks.append(
            (
                scenario[CONF_STANDING_CHARGE_ENTITY],
                f"scenario.{name}.standing_charge",
                StatKind.HISTORY,
            )
        )

    results = [
        await _verify_one(hass, entity_id, role, kind, start, end)
        for entity_id, role, kind in checks
    ]

    return {
        "ok": all(result.status == "ok" for result in results),
        "entities": [result.as_dict() for result in results],
    }


async def _verify_one(
    hass: HomeAssistant,
    entity_id: str,
    role: str,
    kind: StatKind,
    start: date,
    end: date,
) -> EntityVerification:
    if kind is StatKind.HISTORY:
        try:
            _, degraded = await async_fetch_daily_value_from_history(hass, entity_id, start, end)
        except MissingHistoryError as err:
            return EntityVerification(entity_id, role, "error", str(err))

        if degraded:
            return EntityVerification(
                entity_id,
                role,
                "warning",
                f"{entity_id}'s history doesn't reach back to the start of this range; "
                "earlier days fall back to its earliest known state.",
            )

        return EntityVerification(
            entity_id, role, "ok", f"{entity_id} has the data this range needs."
        )

    if not await async_entity_supports_statistics(hass, entity_id, kind):
        suggestion = await _suggest_alternative(hass, entity_id, kind)
        message = f"{entity_id} does not record the long-term statistics this integration needs."
        message += (
            f" {suggestion} is on the same device and does."
            if suggestion
            else " No alternative entity found on the same device."
        )
        return EntityVerification(entity_id, role, "error", message, suggestion)

    start_dt = datetime.combine(start, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end, time.min, tzinfo=UTC) + timedelta(days=1)
    try:
        _, degraded = await async_fetch_settlement_values(hass, entity_id, start_dt, end_dt, kind)
    except MissingStatisticsError as err:
        return EntityVerification(entity_id, role, "error", str(err))

    if degraded:
        return EntityVerification(
            entity_id,
            role,
            "warning",
            f"{entity_id} only has hourly-averaged data for part of this range "
            "(older than HA's short-term statistics retention window).",
        )

    return EntityVerification(entity_id, role, "ok", f"{entity_id} has the data this range needs.")


async def _suggest_alternative(hass: HomeAssistant, entity_id: str, kind: StatKind) -> str | None:
    """Look for a sibling entity on the same HA Device that does support statistics.

    Deliberately device-scoped, not registry-wide: integrations like Octopus Energy
    group related sensors (current/previous rate, standing charge, ...) on one device,
    so a sibling is far more likely to be the intended fix than an unrelated entity
    elsewhere in the registry - and this stays integration-agnostic (see CONTEXT.md's
    "entity-only, provenance-agnostic" HA notes).
    """
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    if entry is None or entry.device_id is None:
        return None

    for sibling in er.async_entries_for_device(registry, entry.device_id):
        if sibling.entity_id == entity_id or sibling.domain != "sensor":
            continue
        if await async_entity_supports_statistics(hass, sibling.entity_id, kind):
            return sibling.entity_id

    return None
