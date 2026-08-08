"""Config flow: initial setup configures the single shared Data Source (Energy
Profile); the options flow manages the named Scenarios layered on top of it."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_EXPORT_ENTITY,
    CONF_EXPORT_RATE_ENTITY,
    CONF_IMPORT_ENTITY,
    CONF_IMPORT_RATE_ENTITY,
    CONF_SCENARIO_NAME,
    CONF_SCENARIOS,
    CONF_STANDING_CHARGE_ENTITY,
    DOMAIN,
)


def _entity_selector(device_class: str | None = None) -> selector.EntitySelector:
    config: dict = {"domain": "sensor"}
    if device_class:
        config["device_class"] = device_class
    return selector.EntitySelector(selector.EntitySelectorConfig(**config))


DATA_SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IMPORT_ENTITY): _entity_selector("energy"),
        vol.Required(CONF_EXPORT_ENTITY): _entity_selector("energy"),
    }
)

SCENARIO_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCENARIO_NAME): str,
        vol.Required(CONF_IMPORT_RATE_ENTITY): _entity_selector(),
        vol.Required(CONF_EXPORT_RATE_ENTITY): _entity_selector(),
        vol.Required(CONF_STANDING_CHARGE_ENTITY): _entity_selector(),
    }
)


class EnergyEngineConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """One config entry = one shared Data Source (Energy Profile) for the installation."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="Energy Engine", data=user_input, options={CONF_SCENARIOS: []}
            )

        return self.async_show_form(step_id="user", data_schema=DATA_SOURCE_SCHEMA)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EnergyEngineOptionsFlow:
        return EnergyEngineOptionsFlow(config_entry)


class EnergyEngineOptionsFlow(config_entries.OptionsFlow):
    """Add/remove named Scenarios, each supplying its own Tariff Provider entity mapping."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_show_menu(
            step_id="init", menu_options=["add_scenario", "remove_scenario"]
        )

    async def async_step_add_scenario(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            scenarios = list(self._config_entry.options.get(CONF_SCENARIOS, []))
            if any(s[CONF_SCENARIO_NAME] == user_input[CONF_SCENARIO_NAME] for s in scenarios):
                errors["base"] = "name_exists"
            else:
                scenarios.append(user_input)
                return self.async_create_entry(title="", data={CONF_SCENARIOS: scenarios})

        return self.async_show_form(
            step_id="add_scenario", data_schema=SCENARIO_SCHEMA, errors=errors
        )

    async def async_step_remove_scenario(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        scenarios = list(self._config_entry.options.get(CONF_SCENARIOS, []))

        if user_input is not None:
            remaining_name = user_input[CONF_SCENARIO_NAME]
            remaining = [s for s in scenarios if s[CONF_SCENARIO_NAME] != remaining_name]
            return self.async_create_entry(title="", data={CONF_SCENARIOS: remaining})

        names = [s[CONF_SCENARIO_NAME] for s in scenarios]
        schema = vol.Schema({vol.Required(CONF_SCENARIO_NAME): vol.In(names)})
        return self.async_show_form(step_id="remove_scenario", data_schema=schema)
