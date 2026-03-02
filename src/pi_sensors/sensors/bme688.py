"""
BME688 environmental sensor wrapper.

Hardware: Adafruit BME688 breakout (I2C, address 0x77)
Measures: temperature, humidity, barometric pressure, gas resistance (VOC proxy)
Library:  bme680 (pimoroni) via smbus2 — no Blinka / lgpio dependency.
"""

from __future__ import annotations

import math
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
    Wrapper around the pimoroni bme680 library using smbus2 directly.

    Uses smbus2 as the I2C backend so it works inside Docker on Pi 5 without
    needing Blinka, digitalio, or lgpio (which requires /dev/gpiochip0).
    """

    def __init__(
        self,
        bus: int = 1,
        address: int = 0x77,
        sea_level_pressure_hpa: float = 1013.25,
    ) -> None:
        import bme680
        import smbus2

        i2c = smbus2.SMBus(bus)
        self._sensor = bme680.BME680(i2c_addr=address, i2c_device=i2c)
        self._sea_level_pressure = sea_level_pressure_hpa

        self._sensor.set_humidity_oversample(bme680.OS_2X)
        self._sensor.set_pressure_oversample(bme680.OS_4X)
        self._sensor.set_temperature_oversample(bme680.OS_8X)
        self._sensor.set_filter(bme680.FILTER_SIZE_3)
        self._sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)
        self._sensor.set_gas_heater_temperature(320)
        self._sensor.set_gas_heater_duration(150)
        self._sensor.select_gas_heater_profile(0)

    def read(self) -> BME688Reading:
        """Return a fresh reading from the sensor."""
        if not self._sensor.get_sensor_data():
            raise RuntimeError("BME688 data not ready")

        pressure = float(self._sensor.data.pressure)
        gas = float(self._sensor.data.gas_resistance) if self._sensor.data.heat_stable else 0.0
        altitude = 44330.0 * (1.0 - (pressure / self._sea_level_pressure) ** (1.0 / 5.255))

        return BME688Reading(
            temperature_c=round(float(self._sensor.data.temperature), 2),
            humidity_rh=round(float(self._sensor.data.humidity), 2),
            pressure_hpa=round(pressure, 2),
            gas_resistance_ohm=round(gas, 0),
            altitude_m=round(altitude, 1),
        )
