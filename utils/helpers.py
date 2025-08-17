import logging
from datetime import datetime, timezone

log = logging.getLogger("app")

def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def persona_from_color(color: str) -> dict:
    color = (color or "").strip().lower()
    mapping = {
        "white": {"name": "White Bambi", "power": "Slutty angel, sandals menace"},
        "pink":  {"name": "Pink Bambi",  "power": "Sweet trouble, soft disarm"},
        "red":   {"name": "Red Bambi",   "power": "Dior 999 femme fatale"},
    }
    return mapping.get(color, {"name": "Bambi", "power": "Undefined mystique"})
