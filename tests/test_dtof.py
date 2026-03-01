"""
Integration tests for the TMF8820 dToF distance sensor.

Requires the sensor physically connected at I2C 0x41.
Tests are automatically skipped when the hardware libraries are not installed
or the device is not reachable.

Plausibility bounds for a standard apartment room:
  - Distances: 100 mm – 6 000 mm  (10 cm to 6 m), or -1 for no target
  - Confidences: 0 – 255
  - At least one zone must see a surface (confidence > 0, distance > 0)
"""

import pytest

from pi_sensors.sensors.dtof import DTOFReading, DTOFSensor

_ROOM_MIN_MM = 100
_ROOM_MAX_MM = 6_000


@pytest.fixture(scope="module")
def sensor() -> DTOFSensor:
    pytest.importorskip("smbus2", reason="smbus2 not installed — skipping hardware test")
    s = DTOFSensor()
    try:
        s.open()
    except Exception as exc:
        pytest.skip(f"dToF not reachable: {exc}")
    yield s
    s.close()


@pytest.fixture(scope="module")
def reading(sensor: DTOFSensor) -> DTOFReading:
    return sensor.read()


def test_sensor_connects(sensor: DTOFSensor) -> None:
    """DTOFSensor.open() raises OSError if the device is not found or ID mismatches."""
    assert sensor is not None


def test_nine_zones(reading: DTOFReading) -> None:
    assert len(reading.distances_mm) == 9
    assert len(reading.confidences) == 9


def test_at_least_one_zone_has_target(reading: DTOFReading) -> None:
    """In any room, at least one zone must detect a surface."""
    assert any(d > 0 for d in reading.distances_mm), (
        f"All zones returned no-target (-1): {reading.distances_mm}"
    )


def test_distances_in_room_range(reading: DTOFReading) -> None:
    for i, d in enumerate(reading.distances_mm):
        assert d == -1 or _ROOM_MIN_MM <= d <= _ROOM_MAX_MM, (
            f"Zone {i}: distance {d} mm is outside plausible room range "
            f"({_ROOM_MIN_MM}–{_ROOM_MAX_MM} mm)"
        )


def test_confidences_in_range(reading: DTOFReading) -> None:
    for i, c in enumerate(reading.confidences):
        assert 0 <= c <= 255, f"Zone {i}: confidence {c} is out of 0–255 range"


def test_at_least_one_confident_zone(reading: DTOFReading) -> None:
    """At least one zone must have non-zero confidence."""
    assert any(c > 0 for c in reading.confidences), (
        f"All confidences are zero — sensor may not be delivering data: {reading.confidences}"
    )


def test_center_zone_property(reading: DTOFReading) -> None:
    """center_distance_mm must match distances_mm[4]."""
    assert reading.center_distance_mm == reading.distances_mm[4]


def test_min_distance_property(reading: DTOFReading) -> None:
    """min_distance_mm must equal the smallest positive distance across all zones."""
    valid = [d for d in reading.distances_mm if d > 0]
    expected = min(valid) if valid else -1
    assert reading.min_distance_mm == expected


def test_reading_is_immutable(reading: DTOFReading) -> None:
    with pytest.raises(Exception):
        reading.distances_mm = []  # type: ignore[misc]
