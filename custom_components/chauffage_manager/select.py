"""Sélecteurs : programmation par pièce/groupe et réglages d'absence."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import CONTROL_AUTO, CONTROL_MANUAL, DOMAIN, MODES, SIGNAL_UPDATE
from .entity import ChauffageEntity


async def async_setup_entry(hass, entry, async_add_entities):
    mgr = entry.runtime_data
    async_add_entities([AbsenceModeSelect(mgr), AbsenceControlSelect(mgr)])
    known: set[str] = set()

    @callback
    def _sync() -> None:
        current = set(mgr.target_ids())
        new = [TargetControlSelect(mgr, t) for t in current - known]
        if new:
            async_add_entities(new)
        registry = er.async_get(hass)
        for gone in known - current:
            entity_id = registry.async_get_entity_id(
                "select", DOMAIN, f"{entry.entry_id}_control_{gone}"
            )
            if entity_id:
                registry.async_remove(entity_id)
        known.clear()
        known.update(current)

    _sync()
    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_UPDATE, _sync))


class TargetControlSelect(ChauffageEntity, SelectEntity):
    """Automatique / Manuel pour un chauffage ou un groupe."""

    _attr_options = [CONTROL_AUTO, CONTROL_MANUAL]
    _attr_translation_key = "control"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, mgr, target_id: str) -> None:
        super().__init__(mgr)
        self._target = target_id
        self._attr_unique_id = f"{mgr.entry.entry_id}_control_{target_id}"

    @property
    def name(self) -> str:
        return f"Chauffage {self.mgr.target_name(self._target)} programmation"

    @property
    def current_option(self) -> str:
        return self.mgr.control_of(self._target)

    async def async_select_option(self, option: str) -> None:
        await self.mgr.async_set_control(self._target, option)


class AbsenceModeSelect(ChauffageEntity, SelectEntity):
    _attr_name = "Chauffage mode absence"
    _attr_options = MODES
    _attr_translation_key = "absence_mode"
    _attr_icon = "mdi:airplane"

    def __init__(self, mgr) -> None:
        super().__init__(mgr)
        self._attr_unique_id = f"{mgr.entry.entry_id}_absence_mode"

    @property
    def current_option(self) -> str:
        return self.mgr.data["absence"]["mode"]

    async def async_select_option(self, option: str) -> None:
        await self.mgr.async_update_absence(mode=option)


class AbsenceControlSelect(ChauffageEntity, SelectEntity):
    _attr_name = "Chauffage programmation en absence"
    _attr_options = [CONTROL_AUTO, CONTROL_MANUAL]
    _attr_translation_key = "control"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, mgr) -> None:
        super().__init__(mgr)
        self._attr_unique_id = f"{mgr.entry.entry_id}_absence_control"

    @property
    def current_option(self) -> str:
        return self.mgr.data["absence"]["control"]

    async def async_select_option(self, option: str) -> None:
        await self.mgr.async_update_absence(control=option)
