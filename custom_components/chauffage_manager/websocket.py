"""API websocket utilisée par la carte."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import CONTROL_AUTO, CONTROL_MANUAL, DOMAIN, MODES, TYPE_PILOT, TYPE_THERMOSTAT

_NUM = vol.Any(None, vol.Coerce(float))
_SLOT = vol.Schema(
    {
        vol.Required("days"): [vol.All(int, vol.Range(min=0, max=6))],
        vol.Required("time"): vol.Match(r"^([01]\d|2[0-3]):[0-5]\d$"),
        vol.Required("mode"): vol.In(MODES),
        vol.Optional("temperature"): _NUM,
    }
)
SCHEMAS = {
    "heater": vol.Schema(
        {
            vol.Required("name"): str,
            vol.Required("type"): vol.In([TYPE_PILOT, TYPE_THERMOSTAT]),
            vol.Required("entity"): str,
            vol.Optional("climate"): vol.Any(None, str),
            vol.Optional("schedule_id"): vol.Any(None, str),
            vol.Optional("floor"): vol.Any(None, str),
            vol.Optional("absence_temperature"): vol.Coerce(float),
        }
    ),
    "group": vol.Schema(
        {
            vol.Required("name"): str,
            vol.Required("members"): [str],
            vol.Optional("schedule_id"): vol.Any(None, str),
            vol.Optional("floor"): vol.Any(None, str),
        }
    ),
    "schedule": vol.Schema({vol.Required("name"): str, vol.Required("slots"): [_SLOT]}),
    "absence": vol.Schema(
        {
            vol.Required("persons"): [str],
            vol.Required("mode"): vol.In(MODES),
            vol.Required("control"): vol.In([CONTROL_AUTO, CONTROL_MANUAL]),
            vol.Required("restore"): bool,
        }
    ),
}


def _mgr(hass: HomeAssistant):
    for entry in hass.config_entries.async_entries(DOMAIN):
        if getattr(entry, "runtime_data", None):
            return entry.runtime_data
    return None


@websocket_api.websocket_command({vol.Required("type"): "chauffage_manager/get"})
@callback
def ws_get(hass, connection, msg):
    mgr = _mgr(hass)
    if mgr is None:
        connection.send_error(msg["id"], "not_loaded", "Intégration non chargée")
        return
    connection.send_result(msg["id"], mgr.payload())


@websocket_api.websocket_command(
    {
        vol.Required("type"): "chauffage_manager/save",
        vol.Required("kind"): vol.In(list(SCHEMAS)),
        vol.Optional("item_id"): str,
        vol.Required("value"): dict,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_save(hass, connection, msg):
    mgr = _mgr(hass)
    try:
        value = SCHEMAS[msg["kind"]](msg["value"])
    except vol.Invalid as err:
        connection.send_error(msg["id"], "invalid", str(err))
        return
    item_id = await mgr.async_upsert(msg["kind"], msg.get("item_id"), value)
    connection.send_result(msg["id"], {"id": item_id})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "chauffage_manager/delete",
        vol.Required("kind"): vol.In(["heater", "group", "schedule"]),
        vol.Required("item_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_delete(hass, connection, msg):
    await _mgr(hass).async_delete(msg["kind"], msg["item_id"])
    connection.send_result(msg["id"], {})
