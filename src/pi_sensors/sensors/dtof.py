"""
Qwiic dToF Imager TMF8820 wrapper.

Hardware: SparkFun Qwiic dToF Imager (TMF8820) — direct Time-of-Flight
Address:  0x41 (default)
Protocol: I2C via smbus2 (no dedicated Python package available)

The TMF8820 is an indirect time-of-flight sensor with a 3×3 zone SPAD array.
This wrapper implements the minimal register-level protocol to:
  1. Boot the device from ROM
  2. Load the default measurement application
  3. Stream distance measurements per zone
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import smbus2

# ---------------------------------------------------------------------------
# Register map (TMF882x datasheet, chapter 6)
# ---------------------------------------------------------------------------
_REG_ENABLE = 0xE0
_REG_INT_STATUS = 0xE1
_REG_INT_ENAB = 0xE2
_REG_ID = 0xE3
_REG_REVISION = 0xE4
_REG_CMD_STAT = 0x08
_REG_CONTENTS = 0x04
_REG_FACTORY_CAL_CFG = 0x20

_ENABLE_PON = 0x01  # Power-on
_ENABLE_WAKEUP = 0x02  # Wake from standby
_CMD_LOAD_CONFIG = 0x08
_CMD_START = 0x10  # MEASURE command (0x02 is factory-calibration write)
_CMD_STOP = 0xFF
_STAT_OK = 0x00
_CONTENTS_MEAS = 0x10  # measurement result contents ID

_DEVICE_ID_TMF882X = 0x08
_NUM_ZONES = 9  # 3×3 SPAD map
_MAX_DISTANCE_MM = 5000  # TMF8820 rated maximum range


@dataclass(frozen=True)
class DTOFReading:
    """Distance measurements from all 9 zones of the TMF8820."""

    distances_mm: list[int] = field(default_factory=list)
    """Distance in millimetres per zone (left-to-right, top-to-bottom). -1 = no target."""

    confidences: list[int] = field(default_factory=list)
    """Confidence value per zone (0–255)."""

    @property
    def center_distance_mm(self) -> int:
        """Distance from the centre zone (index 4)."""
        return self.distances_mm[4] if len(self.distances_mm) > 4 else -1

    @property
    def min_distance_mm(self) -> int:
        """Minimum valid distance across all zones."""
        valid = [d for d in self.distances_mm if d > 0]
        return min(valid) if valid else -1


class DTOFSensor:
    """
    Minimal I2C driver for the SparkFun Qwiic dToF Imager (TMF8820).

    Communicates via smbus2 at address 0x41 by default.
    Call open() before use and close() when done, or use as a context manager.
    """

    def __init__(self, bus: int = 1, address: int = 0x41) -> None:
        self._bus_num = bus
        self._address = address
        self._bus: smbus2.SMBus | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Open the I2C bus and boot the sensor."""
        self._bus = smbus2.SMBus(self._bus_num)
        self._boot()

    def close(self) -> None:
        """Stop measurements and close the bus."""
        if self._bus is not None:
            import contextlib

            with contextlib.suppress(OSError):
                self._write_byte(_REG_CMD_STAT, _CMD_STOP)
            self._bus.close()
            self._bus = None

    def __enter__(self) -> DTOFSensor:
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read(self) -> DTOFReading:
        """Return distance measurements from one measurement cycle."""
        assert self._bus is not None, "Call open() first"

        # Wait for measurement result register to be populated
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            contents = self._read_byte(_REG_CONTENTS)
            if contents == _CONTENTS_MEAS:
                break
            time.sleep(0.01)

        return self._parse_result()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _boot(self) -> None:
        """Power-on sequence: wake, verify ID, start measurement app."""
        assert self._bus is not None

        # Wake up
        self._write_byte(_REG_ENABLE, _ENABLE_PON | _ENABLE_WAKEUP)
        time.sleep(0.02)

        # Verify device ID
        dev_id = self._read_byte(_REG_ID)
        if dev_id != _DEVICE_ID_TMF882X:
            msg = f"Unexpected TMF882x device ID: 0x{dev_id:02X} (expected 0x{_DEVICE_ID_TMF882X:02X})"
            raise OSError(msg)

        # Enable interrupt for measurement results
        self._write_byte(_REG_INT_ENAB, 0x01)

        # Start continuous measurements
        self._write_byte(_REG_CMD_STAT, _CMD_START)
        time.sleep(0.05)

    def _parse_result(self) -> DTOFReading:
        """Read the 132-byte result block and extract zone distances.

        Block layout (TMF882x application firmware):
          Bytes  0–19  Header — result_num[0], reserved[1], num_valid[2],
                        reserved[3], ambient[4:8], photon_count[8:12],
                        ref_count[12:16], sys_tick[16:20]
          Bytes 20+    Object entries, 4 bytes each:
                        [confidence(1B), dist_lo(1B), dist_hi(1B), channel(1B)]
                        channel & 0x0F = zone index (0–8 for 3×3 SPAD map)
        """
        assert self._bus is not None

        # Result block starts at register 0x20, length 132 bytes.
        # read_i2c_block_data is capped at 32 bytes by SMBus; use raw i2c_rdwr instead.
        try:
            write_msg = smbus2.i2c_msg.write(self._address, [0x20])
            read_msg = smbus2.i2c_msg.read(self._address, 132)
            self._bus.i2c_rdwr(write_msg, read_msg)
            data = list(read_msg)
        except OSError:
            return DTOFReading(distances_mm=[-1] * _NUM_ZONES, confidences=[0] * _NUM_ZONES)

        num_valid = data[2]
        distances = [-1] * _NUM_ZONES
        confidences = [0] * _NUM_ZONES

        for i in range(num_valid):
            off = 20 + i * 4
            if off + 3 >= len(data):
                break
            confidence = data[off]
            distance = data[off + 1] | (data[off + 2] << 8)
            zone = data[off + 3] & 0x0F
            if zone < _NUM_ZONES:
                confidences[zone] = confidence
                distances[zone] = distance if confidence > 0 and distance <= _MAX_DISTANCE_MM else -1

        # Clear interrupt
        self._write_byte(_REG_INT_STATUS, 0x01)

        return DTOFReading(distances_mm=distances, confidences=confidences)

    def _read_byte(self, register: int) -> int:
        assert self._bus is not None
        return int(self._bus.read_byte_data(self._address, register))

    def _write_byte(self, register: int, value: int) -> None:
        assert self._bus is not None
        self._bus.write_byte_data(self._address, register, value)
