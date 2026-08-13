"""Per-Scenario 'last result' sensor, and the run_scenario / run_comparison services.

Both services are entity-scoped: targeting one Scenario's sensor runs that Scenario,
targeting several runs them all and returns a per-entity response - an ad hoc
Comparison, per CONTEXT.md (Comparison is on-demand, never a standing config)."""

from __future__ import annotations

from decimal import Decimal

import voluptuous as vol
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import device_info
from .const import (
    ATTR_END_DATE,
    ATTR_PERIOD,
    ATTR_START_DATE,
    CONF_EXPORT_ENTITY,
    CONF_EXPORT_RATE_ENTITY,
    CONF_IMPORT_ENTITY,
    CONF_IMPORT_RATE_ENTITY,
    CONF_SCENARIO_NAME,
    CONF_SCENARIOS,
    CONF_STANDING_CHARGE_ENTITY,
    PERIOD_OPTIONS,
    SERVICE_RUN_COMPARISON,
    SERVICE_RUN_SCENARIO,
)
from .core import run_simulation
from .data_source import async_build_data_source
from .period import resolve_period
from .tariff_provider import async_build_tariff_provider

RUN_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Required(ATTR_PERIOD): vol.In(PERIOD_OPTIONS),
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    scenarios = entry.options.get(CONF_SCENARIOS, [])
    async_add_entities(ScenarioResultSensor(hass, entry, scenario) for scenario in scenarios)

    platform = entity_platform.async_get_current_platform()
    for service in (SERVICE_RUN_SCENARIO, SERVICE_RUN_COMPARISON):
        platform.async_register_entity_service(
            service, RUN_SCHEMA, "async_handle_run", supports_response=SupportsResponse.ONLY
        )


class ScenarioResultSensor(SensorEntity):
    """State = total cost of the Scenario's last run; attributes carry the rest."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.MONETARY

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, scenario: dict) -> None:
        self._hass = hass
        self._entry = entry
        self._scenario = scenario
        self._attr_name = scenario[CONF_SCENARIO_NAME]
        self._attr_unique_id = f"{entry.entry_id}_{scenario[CONF_SCENARIO_NAME]}"
        self._attr_device_info = device_info(entry)
        self._attr_native_unit_of_measurement = hass.config.currency
        self._attr_native_value: Decimal | None = None
        self._attr_extra_state_attributes: dict = {}

    async def async_handle_run(self, period: str) -> ServiceResponse:
        start_date, end_date = resolve_period(period)
        data_source = await async_build_data_source(
            self._hass,
            self._entry.data[CONF_IMPORT_ENTITY],
            self._entry.data[CONF_EXPORT_ENTITY],
            start_date,
            end_date,
        )
        tariff_provider = await async_build_tariff_provider(
            self._hass,
            self._scenario[CONF_IMPORT_RATE_ENTITY],
            self._scenario[CONF_EXPORT_RATE_ENTITY],
            self._scenario[CONF_STANDING_CHARGE_ENTITY],
            start_date,
            end_date,
        )

        profile = data_source.get_energy_profile(start_date, end_date)
        caveats = [c for c in (data_source.precision_caveat, tariff_provider.precision_caveat) if c]

        result = run_simulation(
            profile,
            transforms=(),
            tariff_provider=tariff_provider,
            precision_caveat=" ".join(caveats) or None,
        )

        import_kwh = sum(value.import_kwh for value in result.profile.values.values())
        export_kwh = sum(value.export_kwh for value in result.profile.values.values())

        self._attr_native_value = result.total_cost
        self._attr_extra_state_attributes = {
            ATTR_PERIOD: period,
            ATTR_START_DATE: start_date.isoformat(),
            ATTR_END_DATE: end_date.isoformat(),
            "precision_caveat": result.precision_caveat,
            "import_kwh": import_kwh,
            "export_kwh": export_kwh,
        }
        self.async_write_ha_state()

        return {
            "total_cost": str(result.total_cost),
            "precision_caveat": result.precision_caveat,
            "import_kwh": import_kwh,
            "export_kwh": export_kwh,
        }
