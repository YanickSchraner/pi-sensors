"""
Qwiic Dynamic NFC/RFID Tag wrapper.

Hardware: SparkFun Qwiic Dynamic NFC/RFID Tag (ST25DV16K)
Addresses: 0x53 (user memory / RF), 0x57 (system config)
Protocol:  I2C via smbus2

The ST25DV16K is a dual-interface EEPROM: an NFC/RFID reader can access it
wirelessly while the Pi reads/writes over I2C.  This module lets you:
  - Read & write text payloads to the user memory
  - Detect whether an NFC reader is currently in the field
"""

from __future__ import annotations

from dataclasses import dataclass

import smbus2

# ---------------------------------------------------------------------------
# Register / address constants  (ST25DV16K datasheet, rev 6)
# ---------------------------------------------------------------------------
_I2C_ADDR_USER = 0x53  # E2=0, E1=1, E0=1  — user memory area
_I2C_ADDR_SYS = 0x57  # system area

_REG_GPO_CTRL_DYN = 0x2000  # 16-bit address for dynamic config registers
_REG_IT_STS_DYN = 0x2005  # interrupt status (bit0 = RF field detected)
_REG_EH_CTRL_DYN = 0x2002
_REG_MB_CTRL_DYN = 0x2006  # fast-transfer (mailbox) control

# NDEF type-2 tag structure starts at byte offset 0 of user memory
_NDEF_HEADER_LEN = 2  # capability container lives in first 4 bytes (I2C accessible from 0)


@dataclass
class NFCReading:
    """Data read from the NFC tag's user memory."""

    raw_bytes: bytes
    """Raw user-memory bytes (up to max_length)."""

    rf_field_present: bool
    """True when an NFC reader is actively communicating with the tag."""

    @property
    def text(self) -> str:
        """Attempt to decode raw bytes as UTF-8, replacing invalid chars."""
        return self.raw_bytes.decode("utf-8", errors="replace").rstrip("\x00")


class NFCTag:
    """
    I2C driver for the SparkFun Qwiic Dynamic NFC/RFID Tag (ST25DV16K).

    The ST25DV uses 16-bit register addresses transmitted MSB-first.
    """

    def __init__(self, bus: int = 1, i2c_address: int = _I2C_ADDR_USER) -> None:
        self._bus_num = bus
        self._addr_user = i2c_address
        self._addr_sys = _I2C_ADDR_SYS
        self._bus: smbus2.SMBus | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Open the I2C bus."""
        self._bus = smbus2.SMBus(self._bus_num)

    def close(self) -> None:
        """Close the I2C bus."""
        if self._bus is not None:
            self._bus.close()
            self._bus = None

    def __enter__(self) -> NFCTag:
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read(self, length: int = 64) -> NFCReading:
        """Read *length* bytes from user memory starting at address 0."""
        assert self._bus is not None, "Call open() first"
        raw = self._read_user(0x0000, length)
        rf_present = self._rf_field_detected()
        return NFCReading(raw_bytes=bytes(raw), rf_field_present=rf_present)

    def write_text(self, text: str, memory_address: int = 0x0000) -> None:
        """Write a plain-text payload to user memory (max 2048 bytes for ST25DV16K)."""
        assert self._bus is not None, "Call open() first"
        payload = text.encode("utf-8")
        self._write_user(memory_address, list(payload))

    def write_ndef_uri(self, uri: str) -> None:
        """
        Write a minimal NDEF URI record to user memory so a smartphone can open it.

        The payload is written as an NDEF Type 2 Tag message starting at byte 0.
        """
        assert self._bus is not None, "Call open() first"
        ndef = _encode_ndef_uri(uri)
        self._write_user(0x0000, list(ndef))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_user(self, address: int, length: int) -> list[int]:
        """Read *length* bytes from user memory at 16-bit *address*."""
        assert self._bus is not None
        addr_high = (address >> 8) & 0xFF
        addr_low = address & 0xFF
        write_msg = smbus2.i2c_msg.write(self._addr_user, [addr_high, addr_low])
        read_msg = smbus2.i2c_msg.read(self._addr_user, length)
        self._bus.i2c_rdwr(write_msg, read_msg)
        return list(read_msg)  # type: ignore[arg-type]  # smbus2 i2c_msg is iterable

    def _write_user(self, address: int, data: list[int]) -> None:
        """Write *data* bytes to user memory at 16-bit *address* (5 ms write delay per page)."""
        assert self._bus is not None
        import time

        chunk_size = 4  # ST25DV page size
        for i in range(0, len(data), chunk_size):
            chunk = data[i : i + chunk_size]
            addr = address + i
            payload = [(addr >> 8) & 0xFF, addr & 0xFF, *chunk]
            write_msg = smbus2.i2c_msg.write(self._addr_user, payload)
            self._bus.i2c_rdwr(write_msg)
            time.sleep(0.005)

    def _rf_field_detected(self) -> bool:
        """Return True if the NFC field-detection bit is set."""
        assert self._bus is not None
        addr_high = (_REG_IT_STS_DYN >> 8) & 0xFF
        addr_low = _REG_IT_STS_DYN & 0xFF
        write_msg = smbus2.i2c_msg.write(self._addr_user, [addr_high, addr_low])
        read_msg = smbus2.i2c_msg.read(self._addr_user, 1)
        self._bus.i2c_rdwr(write_msg, read_msg)
        status = list(read_msg)[0]  # type: ignore[arg-type]  # smbus2 i2c_msg is iterable
        return bool(status & 0x01)


def _encode_ndef_uri(uri: str) -> bytes:
    """Encode a URI as a minimal NDEF Type 2 message."""
    uri_bytes = uri.encode("utf-8")
    # NDEF URI record: TNF=0x01 (Well-Known), type="U", payload=[0x00]+uri
    payload = bytes([0x00]) + uri_bytes
    record = bytes([
        0xD1,  # MB=1, ME=1, SR=1, TNF=0x01 (Well-Known)
        0x01,  # Type length = 1
        len(payload),  # Payload length
        0x55,  # Type "U" (URI)
        *payload,
    ])
    # Wrap in TLV: T=0x03 (NDEF), L=length, V=record, T=0xFE (terminator)
    return bytes([0x03, len(record)]) + record + bytes([0xFE])
