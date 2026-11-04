"""Logique principale de Chauffage Manager."""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONTROL_AUTO,
    CONTROL_MANUAL,
    DEFAULT_ABSENCE,
    DEFAULT_ABSENCE_TEMPERATURE,
    DEFAULT_TEMPERATURE,
    DOMAIN,
    EVENT_UPDATED,
    PILOT_OPTIONS,
    PILOT_REVERSE,
    SIGNAL_UPDATE,
    STORAGE_VERSION,
    TYPE_PILOT,
)
from .schedule import current_slot, to_min

_LOGGER = logging.getLogger(__name__)
_COLLECTIONS = {"heater": "heaters", "group": "groups", "schedule": "schedules"}


class ChauffageManager:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store = Store(hass, STORAGE_VERSION, DOMAIN)
        self.data: dict[str, Any] = {}
        self._applied: dict[str, tuple] = {}
        self._unsubs: list = []
        self._presence_unsub = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------ cycle de vie
    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        absence = {**DEFAULT_ABSENCE, **stored.get("absence", {})}
        if "absence" not in stored:
            absence["persons"] = list(self.entry.data.get("persons", []))
        self.data = {
            "heaters": stored.get("heaters", {}),
            "groups": stored.get("groups", {}),
            "schedules": stored.get("schedules", {}),
            "control": stored.get("control", {}),
            "absence": absence,
            "absent": stored.get("absent", False),
            "snapshot": stored.get("snapshot"),
        }

    @callback
    def async_start(self) -> None:
        self._unsubs.append(async_track_time_change(self.hass, self._tick, second=0))
        self._unsubs.append(async_at_started(self.hass, self._started))
        self._track_persons()

    @callback
    def _started(self, _hass=None) -> None:
        self.hass.async_create_task(self._startup())

    async def _startup(self) -> None:
        await self._evaluate_presence()
        await self._tick()

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._presence_unsub:
            self._presence_unsub()
            self._presence_unsub = None

    # ---------------------------------------------------------------- modèle
    def grouped_ids(self) -> set[str]:
        return {m for g in self.data["groups"].values() for m in g.get("members", [])}

    def target_ids(self) -> list[str]:
        grouped = self.grouped_ids()
        return list(self.data["groups"]) + [h for h in self.data["heaters"] if h not in grouped]

    def members(self, target: str) -> list[str]:
        if target in self.data["groups"]:
            return [m for m in self.data["groups"][target]["members"] if m in self.data["heaters"]]
        return [target] if target in self.data["heaters"] else []

    def _item(self, target: str) -> dict:
        return self.data["groups"].get(target) or self.data["heaters"].get(target) or {}

    def target_name(self, target: str) -> str:
        return self._item(target).get("name", target)

    def schedule_of(self, target: str) -> str | None:
        return self._item(target).get("schedule_id")

    def control_of(self, target: str) -> str:
        return self.data["control"].get(target, CONTROL_MANUAL)

    def resolve_target(self, value: str) -> str:
        ids = self.target_ids()
        if value in ids:
            return value
        for t in ids:
            if self.target_name(t).lower() == str(value).lower():
                return t
        raise ServiceValidationError(f"Chauffage ou groupe inconnu : {value}")

    def payload(self) -> dict[str, Any]:
        d = self.data
        return {
            "heaters": [{"id": k, **v} for k, v in d["heaters"].items()],
            "groups": [{"id": k, **v} for k, v in d["groups"].items()],
            "schedules": [{"id": k, **v} for k, v in d["schedules"].items()],
            "targets": [
                {
                    "id": t,
                    "kind": "group" if t in d["groups"] else "heater",
                    "name": self.target_name(t),
                    "control": self.control_of(t),
                    "schedule_id": self.schedule_of(t),
                    "members": self.members(t),
                }
                for t in self.target_ids()
            ],
            "absence": {**d["absence"], "active": d["absent"]},
        }

    # ------------------------------------------------------- lecture / écriture
    def read_heater(self, heater: dict) -> dict | None:
        state = self.hass.states.get(heater["entity"])
        if state is None or state.state in ("unavailable", "unknown"):
            return None
        if heater["type"] == TYPE_PILOT:
            return {"mode": PILOT_REVERSE.get(state.state), "temperature": None}
        return {
            "mode": "off" if state.state == "off" else "comfort",
            "temperature": state.attributes.get("temperature"),
        }

    async def _call(self, domain: str, service: str, data: dict) -> None:
        await self.hass.services.async_call(domain, service, data, blocking=True)

    async def _apply_heater(self, heater_id: str, mode: str, temperature=None) -> bool:
        """Applique un mode ; False si l'entité est indisponible (nouvel essai plus tard)."""
        heater = self.data["heaters"].get(heater_id)
        if not heater:
            return True
        entity = heater["entity"]
        state = self.hass.states.get(entity)
        if state is None or state.state == "unavailable":
            return False
        try:
            if heater["type"] == TYPE_PILOT:
                option = PILOT_OPTIONS[mode]
                if option not in (state.attributes.get("options") or []):
                    _LOGGER.warning("%s : option %s absente de %s", heater["name"], option, entity)
                    return True
                if state.state != option:
                    await self._call("select", "select_option", {"entity_id": entity, "option": option})
            elif mode == "off":
                if state.state != "off":
                    await self._call("climate", "set_hvac_mode", {"entity_id": entity, "hvac_mode": "off"})
            else:
                temp = float(temperature) if temperature is not None else DEFAULT_TEMPERATURE
                if state.state == "off":
                    await self._call("climate", "set_hvac_mode", {"entity_id": entity, "hvac_mode": "heat"})
                if state.attributes.get("temperature") != temp:
                    await self._call("climate", "set_temperature", {"entity_id": entity, "temperature": temp})
        except HomeAssistantError as err:
            _LOGGER.warning("%s : échec de la commande (%s)", heater["name"], err)
            return False
        return True

    def _absence_temp(self, heater_id: str) -> float:
        return float(
            self.data["heaters"][heater_id].get("absence_temperature", DEFAULT_ABSENCE_TEMPERATURE)
        )

    # -------------------------------------------------------------- planning
    async def _tick(self, _now=None) -> None:
        now = dt_util.now()
        minute = now.hour * 60 + now.minute
        for target in self.target_ids():
            if self.control_of(target) != CONTROL_AUTO:
                continue
            sched_id = self.schedule_of(target)
            sched = self.data["schedules"].get(sched_id)
            if not sched:
                continue
            found = current_slot(sched["slots"], now.weekday(), minute)
            if not found:
                continue
            slot, day = found
            key = (sched_id, day, slot["time"], slot["mode"], slot.get("temperature"))
            if self._applied.get(target) == key:
                continue
            results = [
                await self._apply_heater(h, slot["mode"], slot.get("temperature"))
                for h in self.members(target)
            ]
            if all(results):
                self._applied[target] = key

    # ----------------------------------------------------------------- actions
    async def async_set_control(self, target: str, control: str) -> None:
        target = self.resolve_target(target)
        self.data["control"][target] = control
        self._applied.pop(target, None)
        await self._save_notify()
        if control == CONTROL_AUTO:
            await self._tick()

    async def async_set_manual(self, target: str, mode: str, temperature=None) -> None:
        target = self.resolve_target(target)
        self.data["control"][target] = CONTROL_MANUAL
        self._applied.pop(target, None)
        for heater_id in self.members(target):
            await self._apply_heater(heater_id, mode, temperature)
        await self._save_notify()

    async def async_update_absence(self, **kwargs) -> None:
        old = list(self.data["absence"]["persons"])
        self.data["absence"].update(kwargs)
        if old != self.data["absence"]["persons"]:
            self._track_persons()
        await self._save_notify()
        if old != self.data["absence"]["persons"]:
            await self._evaluate_presence()

    async def async_upsert(self, kind: str, item_id: str | None, value: dict) -> str | None:
        if kind == "absence":
            await self.async_update_absence(**value)
            return None
        collection = self.data[_COLLECTIONS[kind]]
        item_id = item_id or f"{kind[0]}_{uuid.uuid4().hex[:6]}"
        if kind == "group":
            value["members"] = [m for m in value["members"] if m in self.data["heaters"]]
            for gid, group in self.data["groups"].items():
                if gid != item_id:
                    group["members"] = [m for m in group["members"] if m not in value["members"]]
            self.data["control"].setdefault(item_id, CONTROL_MANUAL)
        elif kind == "heater":
            self.data["control"].setdefault(item_id, CONTROL_MANUAL)
        collection[item_id] = value
        self._applied.clear()
        await self._save_notify()
        await self._tick()
        return item_id

    async def async_delete(self, kind: str, item_id: str) -> None:
        self.data[_COLLECTIONS[kind]].pop(item_id, None)
        if kind == "heater":
            for group in self.data["groups"].values():
                group["members"] = [m for m in group["members"] if m != item_id]
        elif kind == "schedule":
            for coll in ("heaters", "groups"):
                for item in self.data[coll].values():
                    if item.get("schedule_id") == item_id:
                        item["schedule_id"] = None
        self.data["control"].pop(item_id, None)
        self._applied.clear()
        await self._save_notify()

    async def _save_notify(self) -> None:
        await self._store.async_save(self.data)
        self.hass.bus.async_fire(EVENT_UPDATED)
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    # ---------------------------------------------------------------- absence
    def _track_persons(self) -> None:
        if self._presence_unsub:
            self._presence_unsub()
            self._presence_unsub = None
        persons = self.data["absence"]["persons"]
        if persons:
            self._presence_unsub = async_track_state_change_event(
                self.hass, persons, self._presence_changed
            )

    @callback
    def _presence_changed(self, _event: Event) -> None:
        self.hass.async_create_task(self._evaluate_presence())

    def _absent_now(self) -> bool | None:
        """True si tout le monde est parti, None si indéterminé."""
        states = [self.hass.states.get(p) for p in self.data["absence"]["persons"]]
        known = [s for s in states if s and s.state not in ("unavailable", "unknown")]
        if not known:
            return None
        return not any(s.state == "home" for s in known)

    async def _evaluate_presence(self) -> None:
        async with self._lock:
            absent = self._absent_now()
            if absent is None:
                return
            if absent and not self.data["absent"]:
                await self._enter_absence()
            elif not absent and self.data["absent"]:
                await self._exit_absence()

    async def _enter_absence(self) -> None:
        cfg = self.data["absence"]
        snapshot: dict[str, Any] = {"control": {}, "values": {}}
        for target in self.target_ids():
            snapshot["control"][target] = self.control_of(target)
            for hid in self.members(target):
                value = self.read_heater(self.data["heaters"][hid])
                if value and value["mode"]:
                    snapshot["values"][hid] = value
        self.data["snapshot"] = snapshot
        self.data["absent"] = True
        for target in self.target_ids():
            self.data["control"][target] = cfg["control"]
            self._applied.pop(target, None)
            if cfg["control"] == CONTROL_MANUAL:
                for hid in self.members(target):
                    await self._apply_heater(hid, cfg["mode"], self._absence_temp(hid))
        await self._save_notify()
        if cfg["control"] == CONTROL_AUTO:
            await self._tick()

    async def _exit_absence(self) -> None:
        snapshot = self.data.get("snapshot")
        self.data["absent"] = False
        self.data["snapshot"] = None
        if self.data["absence"]["restore"] and snapshot:
            for target in self.target_ids():
                control = snapshot["control"].get(target)
                if control is None:
                    continue
                self.data["control"][target] = control
                self._applied.pop(target, None)
                if control == CONTROL_MANUAL:
                    for hid in self.members(target):
                        value = snapshot["values"].get(hid)
                        if value:
                            await self._apply_heater(hid, value["mode"], value["temperature"])
        await self._save_notify()
        await self._tick()
