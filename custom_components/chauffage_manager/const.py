"""Constantes Chauffage Manager."""
DOMAIN = "chauffage_manager"
SIGNAL_UPDATE = f"{DOMAIN}_update"
EVENT_UPDATED = f"{DOMAIN}_updated"
STORAGE_VERSION = 1

MODES = ["off", "frost_protection", "eco", "comfort_minus_2", "comfort_minus_1", "comfort"]
PILOT_OPTIONS = {
    "off": "Off",
    "frost_protection": "FrostProtection",
    "eco": "Eco",
    "comfort_minus_2": "ComfortMinus2",
    "comfort_minus_1": "ComfortMinus1",
    "comfort": "Comfort",
}
PILOT_REVERSE = {v: k for k, v in PILOT_OPTIONS.items()}

TYPE_PILOT = "pilot_wire"
TYPE_THERMOSTAT = "thermostat"
CONTROL_AUTO = "auto"
CONTROL_MANUAL = "manual"

DEFAULT_TEMPERATURE = 19.0
DEFAULT_ABSENCE_TEMPERATURE = 12.0
DEFAULT_OPENINGS = {"delay": 2, "resume_delay": 0, "mode": "frost_protection"}
DEFAULT_ABSENCE = {
    "persons": [],
    "mode": "frost_protection",
    "control": CONTROL_MANUAL,
    "restore": True,
}
