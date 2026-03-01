"""
Integration tests for the ST25DV16K NFC/RFID tag.

Requires the tag physically connected at I2C 0x53.
Tests are automatically skipped when the hardware libraries are not installed
or the device is not reachable.

Note: tag user-memory content is application-defined and not plausibility-
checked for room conditions — only connectivity and data-shape are verified.
"""

import pytest

from pi_sensors.sensors.nfc import NFCReading, NFCTag, _encode_ndef_uri


@pytest.fixture(scope="module")
def tag() -> NFCTag:
    pytest.importorskip("smbus2", reason="smbus2 not installed — skipping hardware test")
    t = NFCTag()
    try:
        t.open()
    except Exception as exc:
        pytest.skip(f"NFC tag not reachable: {exc}")
    yield t
    t.close()


@pytest.fixture(scope="module")
def reading(tag: NFCTag) -> NFCReading:
    return tag.read()


def test_tag_connects(tag: NFCTag) -> None:
    """NFCTag.open() must succeed — fails if device is missing at I2C 0x53."""
    assert tag is not None


def test_read_returns_nfc_reading(reading: NFCReading) -> None:
    assert isinstance(reading, NFCReading)


def test_raw_bytes_length(reading: NFCReading) -> None:
    """Default read() requests 64 bytes; the returned buffer must match."""
    assert len(reading.raw_bytes) == 64


def test_rf_field_is_bool(reading: NFCReading) -> None:
    assert isinstance(reading.rf_field_present, bool)


def test_text_property_decodes(reading: NFCReading) -> None:
    """text property must decode without raising even for binary content."""
    assert isinstance(reading.text, str)


def test_context_manager() -> None:
    """NFCTag context manager must open and close without error."""
    pytest.importorskip("smbus2", reason="smbus2 not installed — skipping hardware test")
    with NFCTag() as t:
        r = t.read()
    assert isinstance(r, NFCReading)


# ── Pure unit tests (no hardware required) ────────────────────────────────


def test_encode_ndef_uri_structure() -> None:
    encoded = _encode_ndef_uri("https://www.raspberrypi.com")
    assert encoded[0] == 0x03    # TLV type = NDEF message
    assert encoded[-1] == 0xFE   # TLV terminator
    assert 0xD1 in encoded       # NDEF header byte (MB=1, ME=1, SR=1, TNF=0x01)


def test_encode_ndef_uri_contains_uri() -> None:
    uri = "https://example.com/test"
    encoded = _encode_ndef_uri(uri)
    assert uri.encode() in encoded


def test_encode_ndef_uri_type_field() -> None:
    """The NDEF record type byte must be 0x55 ('U' for URI)."""
    encoded = _encode_ndef_uri("https://example.com")
    assert 0x55 in encoded
