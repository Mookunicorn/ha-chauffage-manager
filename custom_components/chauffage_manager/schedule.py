"""Évaluation des plannings (sans dépendance Home Assistant)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def to_min(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def slots_for_day(slots: list[dict[str, Any]], weekday: int, is_holiday: bool) -> list[dict[str, Any]]:
    """Créneaux applicables un jour donné.

    Un jour férié utilise ses créneaux « fériés » pour ce jour de la semaine s'il y en a,
    sinon le planning normal.
    """
    if is_holiday:
        holiday = [s for s in slots if s.get("holiday") and weekday in s["days"]]
        if holiday:
            return holiday
    return [s for s in slots if not s.get("holiday") and weekday in s["days"]]


def current_slot(
    slots: list[dict[str, Any]], today: date, minute: int, holidays: set[str] | frozenset = frozenset()
):
    """Retourne (créneau actif, date ISO du créneau) ou None.

    Le créneau actif est le dernier démarré, en remontant jusqu'à 7 jours.
    """
    for back in range(8):
        day = today - timedelta(days=back)
        candidates = slots_for_day(slots, day.weekday(), day.isoformat() in holidays)
        if back == 0:
            candidates = [s for s in candidates if to_min(s["time"]) <= minute]
        if candidates:
            return max(candidates, key=lambda s: to_min(s["time"])), day.isoformat()
    return None
