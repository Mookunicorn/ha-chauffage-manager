"""Logique principale de Chauffage Manager."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, timedelta
from functools import partial
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
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
    DEFAULT_OPENINGS,
    DEFAULT_TEMPERATURE,
    DEFAULT_TEMPERATURES,
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
        self._open_unsub = None
        self._timers: dict[tuple, Any] = {}
        self._timer_due: dict[tuple, Any] = {}
        self._holiday_dates: set[str] = set()
        self._overridden: set[str] = set()
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
            "openings": {**DEFAULT_OPENINGS, **stored.get("openings", {})},
            "pauses": stored.get("pauses", {}),
            "holidays": {"entity": None, **stored.get("holidays", {})},
            "temperatures": {**DEFAULT_TEMPERATURES, **stored.get("temperatures", {})},
            "absent": stored.get("absent", False),
            "snapshot": stored.get("snapshot"),
        }

    @callback
    def async_start(self) -> None:
        self._unsubs.append(async_track_time_change(self.hass, self._tick, second=0))
        self._unsubs.append(async_at_started(self.hass, self._started))
        self._unsubs.append(async_track_time_change(self.hass, self._midnight, hour=0, minute=0, second=30))
        self._track_persons()
        self._track_openings()

    @callback
    def _started(self, _hass=None) -> None:
        self.hass.async_create_task(self._startup())

    async def _midnight(self, _now=None) -> None:
        await self._refresh_holidays()
        await self._tick()

    async def _startup(self) -> None:
        await self._refresh_holidays()
        await self._evaluate_presence()
        self._evaluate_openings()
        await self._tick()

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        for key in list(self._timers):
            self._cancel_timer(key)
        if self._open_unsub:
            self._open_unsub()
            self._open_unsub = None
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
                    "paused": t in d["pauses"],
                    **dict(zip(("pause_state", "pause_in"), self.pause_info(t))),
                }
                for t in self.target_ids()
            ],
            "absence": {**d["absence"], "active": d["absent"]},
            "openings": d["openings"],
            "temperatures": d["temperatures"],
            "holidays": {**d["holidays"], "today": dt_util.now().date().isoformat() in self._holiday_dates},
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
                temp = (
                    float(temperature)
                    if temperature is not None
                    else float(self.data["temperatures"].get(mode, DEFAULT_TEMPERATURE))
                )
                if state.state == "off":
                    await self._call("climate", "set_hvac_mode", {"entity_id": entity, "hvac_mode": "heat"})
                if state.attributes.get("temperature") != temp:
                    await self._call("climate", "set_temperature", {"entity_id": entity, "temperature": temp})
        except HomeAssistantError as err:
            _LOGGER.warning("%s : échec de la commande (%s)", heater["name"], err)
            return False
        return True

    # -------------------------------------------------------------- planning
    async def _tick(self, _now=None) -> None:
        now = dt_util.now()
        minute = now.hour * 60 + now.minute
        for target in self.target_ids():
            if self.control_of(target) != CONTROL_AUTO or target in self.data["pauses"]:
                continue
            sched_id = self.schedule_of(target)
            sched = self.data["schedules"].get(sched_id)
            if not sched:
                continue
            found = current_slot(sched["slots"], now.date(), minute, self._holiday_dates)
            if not found:
                continue
            slot, day = found
            key = (sched_id, day, slot["time"], slot["mode"])
            if self._applied.get(target) == key:
                continue
            results = [
                await self._apply_heater(h, slot["mode"])
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
        if self.data["pauses"].pop(target, None) is not None:
            self._overridden.add(target)
        for heater_id in self.members(target):
            await self._apply_heater(heater_id, mode, temperature)
        await self._save_notify()

    async def async_update_absence(self, **kwargs) -> None:
        old = dict(self.data["absence"])
        self.data["absence"].update(kwargs)
        new = self.data["absence"]
        if old["persons"] != new["persons"]:
            self._track_persons()
        await self._save_notify()
        if self.data["absent"] and (old["mode"] != new["mode"] or old["control"] != new["control"]):
            await self._reapply_absence()
        if old["persons"] != new["persons"]:
            await self._evaluate_presence()

    async def _reapply_absence(self) -> None:
        """Absence en cours : applique tout de suite les nouveaux réglages (sans refaire de sauvegarde)."""
        cfg = self.data["absence"]
        for target in self.target_ids():
            self.data["control"][target] = cfg["control"]
            self._applied.pop(target, None)
            if cfg["control"] == CONTROL_MANUAL and target not in self.data["pauses"]:
                for hid in self.members(target):
                    await self._apply_heater(hid, cfg["mode"], None)
        await self._save_notify()
        if cfg["control"] == CONTROL_AUTO:
            await self._tick()

    async def async_upsert(self, kind: str, item_id: str | None, value: dict) -> str | None:
        if kind == "absence":
            await self.async_update_absence(**value)
            return None
        if kind == "temperatures":
            self.data["temperatures"] = {**DEFAULT_TEMPERATURES, **value}
            self._applied.clear()
            await self._save_notify()
            await self._tick()
            return None
        if kind == "holidays":
            self.data["holidays"] = {"entity": value.get("entity")}
            await self._refresh_holidays()
            self._applied.clear()
            await self._save_notify()
            await self._tick()
            return None
        if kind == "openings":
            self.data["openings"] = {**DEFAULT_OPENINGS, **value}
            await self._save_notify()
            self._evaluate_openings()
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
        self._track_openings()
        await self._save_notify()
        self._evaluate_openings()
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
        self.data["pauses"].pop(item_id, None)
        self._applied.clear()
        self._track_openings()
        await self._save_notify()
        self._evaluate_openings()

    @callback
    def _notify(self) -> None:
        self.hass.bus.async_fire(EVENT_UPDATED)
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    async def _save_notify(self) -> None:
        await self._store.async_save(self.data)
        self._notify()

    async def _refresh_holidays(self) -> None:
        """Lit les jours fériés dans le calendrier choisi (de J-8 à J+2)."""
        entity = self.data["holidays"].get("entity")
        if not entity:
            self._holiday_dates = set()
            return
        today = dt_util.now().date()
        try:
            response = await self.hass.services.async_call(
                "calendar",
                "get_events",
                {
                    "entity_id": entity,
                    "start_date_time": dt_util.start_of_local_day(today - timedelta(days=8)),
                    "end_date_time": dt_util.start_of_local_day(today + timedelta(days=3)),
                },
                blocking=True,
                return_response=True,
            )
        except HomeAssistantError as err:
            _LOGGER.warning("Jours fériés : lecture impossible (%s)", err)
            return
        dates: set[str] = set()
        for event in (response or {}).get(entity, {}).get("events", []):
            start, end = str(event.get("start", "")), str(event.get("end", ""))
            try:
                first = date.fromisoformat(start[:10])
            except ValueError:
                continue
            if "T" in start:
                dates.add(first.isoformat())
                continue
            try:
                last = date.fromisoformat(end[:10])
            except ValueError:
                last = first + timedelta(days=1)
            day = first
            while day < max(last, first + timedelta(days=1)):
                dates.add(day.isoformat())
                day += timedelta(days=1)
        self._holiday_dates = dates

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
            paused = self.data["pauses"].get(target, {}).get("values", {})
            for hid in self.members(target):
                value = paused.get(hid) or self.read_heater(self.data["heaters"][hid])
                if value and value["mode"]:
                    snapshot["values"][hid] = value
        self.data["snapshot"] = snapshot
        self.data["absent"] = True
        for target in self.target_ids():
            self.data["control"][target] = cfg["control"]
            self._applied.pop(target, None)
            if cfg["control"] == CONTROL_MANUAL and target not in self.data["pauses"]:
                for hid in self.members(target):
                    await self._apply_heater(hid, cfg["mode"], None)
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
                        if not value:
                            continue
                        if target in self.data["pauses"]:
                            self.data["pauses"][target]["values"][hid] = value
                        else:
                            await self._apply_heater(hid, value["mode"], value["temperature"])
        await self._save_notify()
        await self._tick()

    # --------------------------------------------------------------- ouvertures
    def _openings_of(self, target: str) -> list[str]:
        return list(self._item(target).get("openings") or [])

    def _track_openings(self) -> None:
        if self._open_unsub:
            self._open_unsub()
            self._open_unsub = None
        entities = sorted({e for t in self.target_ids() for e in self._openings_of(t)})
        if entities:
            self._open_unsub = async_track_state_change_event(
                self.hass, entities, self._opening_changed
            )

    @callback
    def _opening_changed(self, event: Event) -> None:
        entity = event.data["entity_id"]
        for target in self.target_ids():
            if entity in self._openings_of(target):
                self._evaluate_opening(target)

    def _is_open(self, target: str) -> bool:
        for entity in self._openings_of(target):
            state = self.hass.states.get(entity)
            if state is not None and state.state == "on":
                return True
        return False

    def _cancel_timer(self, key: tuple) -> None:
        unsub = self._timers.pop(key, None)
        self._timer_due.pop(key, None)
        if unsub:
            unsub()
            self._notify()

    def _start_timer(self, target: str, kind: str, delay: float) -> None:
        self._timers[(target, kind)] = async_call_later(
            self.hass, delay, partial(self._timer_fired, target, kind)
        )
        self._timer_due[(target, kind)] = dt_util.utcnow() + timedelta(seconds=delay)
        self._notify()

    def pause_info(self, target: str) -> tuple[str | None, int | None]:
        """État de pause : (None | pausing | paused | resuming, secondes restantes)."""
        def left(kind: str) -> int | None:
            due = self._timer_due.get((target, kind))
            return max(0, int((due - dt_util.utcnow()).total_seconds())) if due else None

        if target in self.data["pauses"]:
            if (target, "resume") in self._timers:
                return "resuming", left("resume")
            return "paused", None
        if (target, "pause") in self._timers:
            return "pausing", left("pause")
        return None, None

    @callback
    def _evaluate_openings(self) -> None:
        for target in list(self.data["pauses"]):
            if target not in self.target_ids():
                self.data["pauses"].pop(target)
        for target in self.target_ids():
            self._evaluate_opening(target)

    @callback
    def _evaluate_opening(self, target: str) -> None:
        cfg = self.data["openings"]
        paused = target in self.data["pauses"]
        if self._is_open(target):
            self._cancel_timer((target, "resume"))
            if paused or target in self._overridden or (target, "pause") in self._timers:
                return
            delay = float(cfg["delay"]) * 60
            if delay <= 0:
                self.hass.async_create_task(self._pause(target))
            else:
                self._start_timer(target, "pause", delay)
        else:
            self._cancel_timer((target, "pause"))
            self._overridden.discard(target)
            if not paused or (target, "resume") in self._timers:
                return
            delay = float(cfg["resume_delay"]) * 60
            if delay <= 0:
                self.hass.async_create_task(self._resume(target))
            else:
                self._start_timer(target, "resume", delay)

    @callback
    def _timer_fired(self, target: str, kind: str, _now=None) -> None:
        self._timers.pop((target, kind), None)
        self._timer_due.pop((target, kind), None)
        self._notify()
        is_open = self._is_open(target)
        if kind == "pause" and is_open:
            self.hass.async_create_task(self._pause(target))
        elif kind == "resume" and not is_open:
            self.hass.async_create_task(self._resume(target))

    async def _pause(self, target: str) -> None:
        if target in self.data["pauses"] or target not in self.target_ids():
            return
        snapshot: dict[str, Any] = {"values": {}}
        for hid in self.members(target):
            value = self.read_heater(self.data["heaters"][hid])
            if value and value["mode"]:
                snapshot["values"][hid] = value
        self.data["pauses"][target] = snapshot
        mode = self.data["openings"]["mode"]
        for hid in self.members(target):
            await self._apply_heater(hid, mode, None)
        await self._save_notify()

    async def _resume(self, target: str) -> None:
        snapshot = self.data["pauses"].pop(target, None)
        if snapshot is None:
            return
        if self.control_of(target) == CONTROL_MANUAL:
            absence = self.data["absence"]
            for hid in self.members(target):
                if self.data["absent"]:
                    await self._apply_heater(hid, absence["mode"], None)
                elif hid in snapshot["values"]:
                    value = snapshot["values"][hid]
                    await self._apply_heater(hid, value["mode"], value["temperature"])
        else:
            self._applied.pop(target, None)
        await self._save_notify()
        await self._tick()
