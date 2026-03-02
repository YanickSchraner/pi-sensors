"""
BME688 environmental sensor wrapper.

Hardware: Adafruit BME688 breakout (I2C, address 0x77)
Measures: temperature, humidity, barometric pressure, gas resistance (VOC proxy)
Library:  adafruit-circuitpython-bme680
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BME688Reading:
    """A single snapshot from the BME688."""

    temperature_c: float
    """Ambient temperature in degrees Celsius."""

    humidity_rh: float
    """Relative humidity in percent (0-100)."""

    pressure_hpa: float
    """Barometric pressure in hecto-Pascals."""

    gas_resistance_ohm: float
    """Gas resistance in Ohms — higher values indicate cleaner air."""

    altitude_m: float
    """Estimated altitude in metres above sea level (based on sea-level pressure)."""

    @property
    def temperature_f(self) -> float:
        """Temperature in degrees Fahrenheit."""
        return self.temperature_c * 9 / 5 + 32

    @property
    def air_quality_label(self) -> str:
        """Rough air-quality label derived from gas resistance."""
        r = self.gas_resistance_ohm
        if r > 300_000:
            return "Excellent"
        elif r > 100_000:
            return "Good"
        elif r > 50_000:
            return "Fair"
        else:
            return "Poor"


class BME688Sensor:
    """
    Wrapper around the Adafruit BME680/BME688 CircuitPython driver.

    The sensor is addressed at 0x77 by default (SD0 pin pulled high).
    Use address=0x76 if the breakout's SDO pin is pulled low.
    """

    def __init__(
        self,
        address: int = 0x77,
        sea_level_pressure_hpa: float = 1013.25,
    ) -> None:
        import adafruit_bme680
        import board

        i2c = board.I2C()
        self._sensor = adafruit_bme680.Adafruit_BME680_I2C(i2c, address=address)
        self._sensor.sea_level_pressure = sea_level_pressure_hpa

    def read(self) -> BME688Reading:
        """Return a fresh reading from the sensor."""
        return BME688Reading(
            temperature_c=round(float(self._sensor.temperature), 2),
            humidity_rh=round(float(self._sensor.relative_humidity), 2),
            pressure_hpa=round(float(self._sensor.pressure), 2),
            gas_resistance_ohm=round(float(self._sensor.gas), 0),
            altitude_m=round(float(self._sensor.altitude), 1),
        )
