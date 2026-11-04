"""Capteur d'absence."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity

from .entity import ChauffageEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([AbsenceBinarySensor(entry.runtime_data)])


class AbsenceBinarySensor(ChauffageEntity, BinarySensorEntity):
    _attr_name = "Chauffage absence"
    _attr_icon = "mdi:home-export-outline"

    def __init__(self, mgr) -> None:
        super().__init__(mgr)
        self._attr_unique_id = f"{mgr.entry.entry_id}_absence"

    @property
    def is_on(self) -> bool:
        return bool(self.mgr.data["absent"])

    @property
    def extra_state_attributes(self):
        return {"persons": self.mgr.data["absence"]["persons"]}
