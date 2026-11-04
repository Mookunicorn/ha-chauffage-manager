"""Évaluation des plannings (sans dépendance Home Assistant)."""
from __future__ import annotations

from typing import Any


def to_min(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def current_slot(slots: list[dict[str, Any]], weekday: int, minute: int):
    """Retourne (créneau actif, jour du créneau) ou None.

    weekday : 0 = lundi ... 6 = dimanche ; minute : minutes depuis minuit.
    Le créneau actif est le dernier démarré, en remontant jusqu'à 7 jours.
    """
    for back in range(8):
        day = (weekday - back) % 7
        best = None
        for slot in slots:
            if day not in slot["days"]:
                continue
            start = to_min(slot["time"])
            if back == 0 and start > minute:
                continue
            if best is None or start > to_min(best["time"]):
                best = slot
        if best is not None:
            return best, day
    return None
