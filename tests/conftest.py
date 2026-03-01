"""
pytest configuration for pi-sensors.

Hardware libraries (adafruit_bme680, board, qwiic_pir, smbus2, sounddevice)
are stubbed when not installed so that API tests and pure unit tests can run
on any machine (CI, dev laptop, etc.).

When running on the Pi with all packages installed the real libraries are used
and the hardware integration tests become active.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock


def _maybe_stub(name: str) -> bool:
    """
    Stub *name* in sys.modules if the real package cannot be imported.

    Returns True  when the real package was found and usable.
    Returns False when the stub was installed.

    Catches all exceptions (not just ImportError) because some Pi-only
    libraries raise NameError or AttributeError on non-Pi platforms when
    they reference CircuitPython types that don't exist on desktop Python.
    """
    if name in sys.modules:
        # Already imported — trust it only if it's a real module, not one of
        # our own stubs (MagicMock won't have a real __spec__).
        existing = sys.modules[name]
        return not isinstance(existing, MagicMock)
    try:
        __import__(name)
        return True
    except Exception:  # noqa: BLE001
        mod = MagicMock()
        mod.__name__ = name
        sys.modules[name] = mod
        return False


# ── Hardware library stubs (no-op when already installed) ─────────────────
# These must be registered *before* any pi_sensors module is imported so
# that sensor modules that do `import adafruit_bme680` at the top level
# find the stub in sys.modules instead of raising ImportError.
_HW_AVAILABLE: dict[str, bool] = {
    "adafruit_bme680": _maybe_stub("adafruit_bme680"),
    "board":           _maybe_stub("board"),
    "qwiic_pir":       _maybe_stub("qwiic_pir"),
    "smbus2":          _maybe_stub("smbus2"),
    "sounddevice":     _maybe_stub("sounddevice"),
}

# Convenience flag: True only when *all* sensor libraries are present.
HW_PRESENT = all(_HW_AVAILABLE.values())
