"""Interrupteur de restauration au retour."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity

from .entity import ChauffageEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([RestoreSwitch(entry.runtime_data)])


class RestoreSwitch(ChauffageEntity, SwitchEntity):
    _attr_name = "Chauffage restauration au retour"
    _attr_icon = "mdi:backup-restore"

    def __init__(self, mgr) -> None:
        super().__init__(mgr)
        self._attr_unique_id = f"{mgr.entry.entry_id}_restore"

    @property
    def is_on(self) -> bool:
        return bool(self.mgr.data["absence"]["restore"])

    async def async_turn_on(self, **kwargs) -> None:
        await self.mgr.async_update_absence(restore=True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.mgr.async_update_absence(restore=False)
