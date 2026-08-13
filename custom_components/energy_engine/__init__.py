"""Energy Engine: prices energy usage against UK electricity tariffs.

This integration is a thin HA-facing shell around the core engine in ./core,
which lives here (not a separate package) because HACS only ever checks out
custom_components/energy_engine/ into a user's Home Assistant config.
"""

from __future__ import annotations

import functools

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import ATTR_END_DATE, ATTR_START_DATE, CONF_SCENARIOS, DOMAIN, SERVICE_VERIFY_ENTITIES
from .verification import async_verify_entities

PLATFORMS = ["sensor"]

VERIFY_ENTITIES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Required(ATTR_START_DATE): cv.date,
        vol.Required(ATTR_END_DATE): cv.date,
    }
)


def device_info(entry: ConfigEntry) -> dict:
    """Shared DeviceInfo-shaped dict for this config entry's single Device.

    Every Scenario sensor sets its device_info to this so they group under the same
    Device page that `verify_entities` targets, rather than the Device existing only
    as a disconnected service-call target.
    """
    return {"identifiers": {(DOMAIN, entry.entry_id)}, "name": "Energy Engine"}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        entry_type=dr.DeviceEntryType.SERVICE,
        **device_info(entry),
    )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, SERVICE_VERIFY_ENTITIES):
        hass.services.async_register(
            DOMAIN,
            SERVICE_VERIFY_ENTITIES,
            functools.partial(_async_handle_verify_entities, hass),
            schema=VERIFY_ENTITIES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_handle_verify_entities(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    entry_ids = await async_extract_config_entry_ids(hass, call)
    entry = next(
        (e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id in entry_ids), None
    )
    if entry is None:
        raise vol.Invalid("No Energy Engine device found for this target")

    scenarios = entry.options.get(CONF_SCENARIOS, [])
    return await async_verify_entities(
        hass, entry.data, scenarios, call.data[ATTR_START_DATE], call.data[ATTR_END_DATE]
    )
