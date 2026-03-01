"""
Integration tests for the BME688 environmental sensor.

Requires the sensor physically connected at I2C 0x77.
Tests are automatically skipped when the hardware libraries are not installed
or the device is not reachable.

Plausibility bounds for a standard apartment room:
  - Temperature: 15°C – 35°C
  - Humidity:    20% – 80%
  - Pressure:    870 hPa – 1085 hPa  (covers all realistic altitudes / weather)
  - Gas:         > 0 Ω               (any valid resistance reading)
  - Altitude:   –500 m – 3 000 m
"""

import pytest

from pi_sensors.sensors.bme688 import BME688Reading, BME688Sensor

_TEMP_MIN_C = 15.0
_TEMP_MAX_C = 35.0
_HUM_MIN = 20.0
_HUM_MAX = 80.0
_PRES_MIN_HPA = 870.0
_PRES_MAX_HPA = 1085.0
_ALT_MIN_M = -500.0
_ALT_MAX_M = 3_000.0


@pytest.fixture(scope="module")
def sensor() -> BME688Sensor:
    import sys
    from unittest.mock import MagicMock

    # The conftest stubs the library when it cannot be imported cleanly (e.g.
    # missing adafruit-blinka on this platform).  In that case the "sensor"
    # would silently return MagicMock values — skip instead.
    for lib in ("adafruit_bme680", "board"):
        if isinstance(sys.modules.get(lib), MagicMock):
            pytest.skip(f"{lib} is stubbed (not fully installed) — skipping hardware test")

    try:
        return BME688Sensor()
    except Exception as exc:
        pytest.skip(f"BME688 not reachable: {exc}")


@pytest.fixture(scope="module")
def reading(sensor: BME688Sensor) -> BME688Reading:
    return sensor.read()


def test_sensor_connects(sensor: BME688Sensor) -> None:
    """BME688Sensor() raises OSError if the device is not found at 0x77."""
    assert sensor is not None


def test_temperature_in_room_range(reading: BME688Reading) -> None:
    assert _TEMP_MIN_C <= reading.temperature_c <= _TEMP_MAX_C, (
        f"Temperature {reading.temperature_c:.1f}°C outside plausible room range "
        f"({_TEMP_MIN_C}–{_TEMP_MAX_C}°C)"
    )


def test_temperature_f_matches_c(reading: BME688Reading) -> None:
    expected_f = reading.temperature_c * 9 / 5 + 32
    assert reading.temperature_f == pytest.approx(expected_f, abs=0.01)


def test_humidity_in_room_range(reading: BME688Reading) -> None:
    assert _HUM_MIN <= reading.humidity_rh <= _HUM_MAX, (
        f"Humidity {reading.humidity_rh:.1f}% outside plausible apartment range "
        f"({_HUM_MIN}–{_HUM_MAX}%)"
    )


def test_pressure_in_range(reading: BME688Reading) -> None:
    assert _PRES_MIN_HPA <= reading.pressure_hpa <= _PRES_MAX_HPA, (
        f"Pressure {reading.pressure_hpa:.1f} hPa outside plausible range "
        f"({_PRES_MIN_HPA}–{_PRES_MAX_HPA} hPa)"
    )


def test_gas_resistance_positive(reading: BME688Reading) -> None:
    assert reading.gas_resistance_ohm > 0, (
        f"Gas resistance {reading.gas_resistance_ohm:.0f} Ω is not positive "
        "— sensor may not have warmed up yet"
    )


def test_altitude_plausible(reading: BME688Reading) -> None:
    assert _ALT_MIN_M <= reading.altitude_m <= _ALT_MAX_M, (
        f"Altitude {reading.altitude_m:.1f} m outside plausible range "
        f"({_ALT_MIN_M}–{_ALT_MAX_M} m)"
    )


def test_air_quality_label_valid(reading: BME688Reading) -> None:
    assert reading.air_quality_label in {"Excellent", "Good", "Fair", "Poor"}


def test_reading_is_frozen(reading: BME688Reading) -> None:
    with pytest.raises(Exception):
        reading.temperature_c = 99.0  # type: ignore[misc]
