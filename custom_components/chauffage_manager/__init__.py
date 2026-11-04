"""Chauffage Manager : gestion de chauffages (fil pilote / thermostat), plannings, groupes, absence."""
from __future__ import annotations

from pathlib import Path

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import CARD_URL, CONTROL_AUTO, CONTROL_MANUAL, DOMAIN, MODES, VERSION
from .manager import ChauffageManager
from .websocket import ws_delete, ws_get, ws_save

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SELECT, Platform.SWITCH]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SET_CONTROL = vol.Schema(
    {vol.Required("target"): cv.string, vol.Required("control"): vol.In([CONTROL_AUTO, CONTROL_MANUAL])}
)
SET_MANUAL = vol.Schema(
    {
        vol.Required("target"): cv.string,
        vol.Required("mode"): vol.In(MODES),
        vol.Optional("temperature"): vol.Coerce(float),
    }
)


async def async_setup(hass: HomeAssistant, config) -> bool:
    for command in (ws_get, ws_save, ws_delete):
        websocket_api.async_register_command(hass, command)
    path = Path(__file__).parent / "www" / "chauffage-manager-card.js"
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(path), False)])
    add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    mgr = ChauffageManager(hass, entry)
    await mgr.async_load()
    entry.runtime_data = mgr
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def set_control(call: ServiceCall) -> None:
        await mgr.async_set_control(call.data["target"], call.data["control"])

    async def set_manual(call: ServiceCall) -> None:
        await mgr.async_set_manual(call.data["target"], call.data["mode"], call.data.get("temperature"))

    hass.services.async_register(DOMAIN, "set_control", set_control, SET_CONTROL)
    hass.services.async_register(DOMAIN, "set_manual", set_manual, SET_MANUAL)
    mgr.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry.runtime_data.async_stop()
        hass.services.async_remove(DOMAIN, "set_control")
        hass.services.async_remove(DOMAIN, "set_manual")
    return unload
