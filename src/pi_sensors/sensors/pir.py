"""
Qwiic PIR motion sensor wrapper.

Hardware: SparkFun Qwiic PIR (EKMB1107112) — 1 µA standby, I2C
Address:  0x12 (default)
Library:  sparkfun-qwiic-pir
"""

from __future__ import annotations

from dataclasses import dataclass

import qwiic_pir
import smbus2


@dataclass(frozen=True)
class PIRReading:
    """A single snapshot from the PIR sensor."""

    motion_detected: bool
    """True if an object was detected since the last read."""

    raw_object_moved: bool
    """True while the object is actively moving."""


class PIRSensor:
    """
    Wrapper around the SparkFun Qwiic PIR library.

    The sensor uses an ultra-low-power EKMB1107112 PIR element and
    communicates via I2C at 0x12 by default.
    """

    def __init__(self, address: int = 0x12, bus: int = 1) -> None:
        self._pir = qwiic_pir.QwiicPIR(address=address)
        # qwiic_i2c.isDeviceConnected (used by begin()) probes via write_quick,
        # which this sensor silently ignores. Verify presence by reading ID directly.
        try:
            with smbus2.SMBus(bus) as b:
                dev_id = b.read_byte_data(address, self._pir.ID)
        except OSError:
            dev_id = -1
        if dev_id != self._pir.DEV_ID:
            msg = f"PIR sensor not found at I2C address 0x{address:02X}"
            raise OSError(msg)

    def read(self) -> PIRReading:
        """Return a fresh reading. The detected flag auto-clears after being read."""
        detected = bool(self._pir.object_detected())
        moved = bool(self._pir.raw_reading())
        return PIRReading(motion_detected=detected, raw_object_moved=moved)

    def clear_events(self) -> None:
        """Explicitly clear any queued detection events."""
        self._pir.clear_event_bits()
