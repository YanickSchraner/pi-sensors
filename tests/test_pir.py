"""
Integration tests for the Qwiic PIR motion sensor.

Requires the sensor physically connected at I2C 0x12.
Tests are automatically skipped when the hardware libraries are not installed
or the device is not reachable.
"""

import pytest

from pi_sensors.sensors.pir import PIRReading, PIRSensor


@pytest.fixture(scope="module")
def sensor() -> PIRSensor:
    pytest.importorskip("qwiic_pir", reason="qwiic_pir not installed — skipping hardware test")
    pytest.importorskip("smbus2", reason="smbus2 not installed — skipping hardware test")
    try:
        return PIRSensor()
    except Exception as exc:
        pytest.skip(f"PIR not reachable: {exc}")


def test_sensor_connects(sensor: PIRSensor) -> None:
    """PIRSensor() raises OSError if the device is not found — fixture handles this."""
    assert sensor is not None


def test_read_returns_pir_reading(sensor: PIRSensor) -> None:
    reading = sensor.read()
    assert isinstance(reading, PIRReading)


def test_read_fields_are_bool(sensor: PIRSensor) -> None:
    reading = sensor.read()
    assert isinstance(reading.motion_detected, bool)
    assert isinstance(reading.raw_object_moved, bool)


def test_multiple_reads_stable(sensor: PIRSensor) -> None:
    """Ten consecutive reads must all succeed and return valid booleans."""
    for _ in range(10):
        reading = sensor.read()
        assert isinstance(reading.motion_detected, bool)
        assert isinstance(reading.raw_object_moved, bool)


def test_reading_is_immutable(sensor: PIRSensor) -> None:
    reading = sensor.read()
    with pytest.raises(Exception):
        reading.motion_detected = True  # type: ignore[misc]
