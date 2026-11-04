"""Constantes Chauffage Manager."""
DOMAIN = "chauffage_manager"
VERSION = "1.0.0"
SIGNAL_UPDATE = f"{DOMAIN}_update"
EVENT_UPDATED = f"{DOMAIN}_updated"
STORAGE_VERSION = 1
CARD_URL = f"/{DOMAIN}/chauffage-manager-card.js"

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
DEFAULT_ABSENCE = {
    "persons": [],
    "mode": "frost_protection",
    "control": CONTROL_MANUAL,
    "restore": True,
}
