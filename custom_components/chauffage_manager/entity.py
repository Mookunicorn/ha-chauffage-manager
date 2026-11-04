"""Entité de base."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_UPDATE


class ChauffageEntity(Entity):
    _attr_should_poll = False

    def __init__(self, mgr) -> None:
        self.mgr = mgr
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mgr.entry.entry_id)},
            name="Chauffage Manager",
            manufacturer="Chauffage Manager",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATE, self.async_write_ha_state)
        )
