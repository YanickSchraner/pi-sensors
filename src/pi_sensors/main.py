"""
Pi Sensors — FastAPI backend.

Polls all Raspberry Pi hardware sensors in background threads and exposes
the latest readings via REST endpoints and a Server-Sent Events stream.

Sensors:
  - BME688  — temperature, humidity, pressure, air quality (I2C 0x77)
  - PIR     — motion detection (I2C 0x12)
  - dToF    — 3×3 zone Time-of-Flight distance (I2C 0x41)
  - NFC     — RFID tag read / RF field detection (I2C 0x53)
  - Audio   — microphone RMS level via sounddevice
"""

from __future__ import annotations

import asyncio
import json
import math
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import lru_cache

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic_settings import BaseSettings, SettingsConfigDict

from pi_sensors.sensors.bme688 import BME688Reading, BME688Sensor
from pi_sensors.sensors.dtof import DTOFReading, DTOFSensor
from pi_sensors.sensors.nfc import NFCReading, NFCTag
from pi_sensors.sensors.pir import PIRReading, PIRSensor

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Polling intervals (seconds)
    bme_interval: float = 2.0
    pir_interval: float = 0.1
    dtof_interval: float = 0.1
    nfc_interval: float = 0.5
    audio_interval: float = 0.1

    # SSE push interval
    sse_interval: float = 0.5


@lru_cache
def get_settings() -> Settings:
    return Settings()


# ---------------------------------------------------------------------------
# Shared sensor state (updated by background threads)
# ---------------------------------------------------------------------------


@dataclass
class SensorState:
    bme: BME688Reading | None = None
    bme_error: str = ""

    pir: PIRReading | None = None
    pir_error: str = ""
    pir_events: int = 0

    dtof: DTOFReading | None = None
    dtof_error: str = ""

    nfc: NFCReading | None = None
    nfc_error: str = ""

    audio_db: float = -60.0
    audio_peak: float = -60.0

    lock: threading.Lock = field(default_factory=threading.Lock)


_state = SensorState()


# ---------------------------------------------------------------------------
# Background sensor threads
# ---------------------------------------------------------------------------


def _bme_thread(stop: threading.Event, interval: float) -> None:
    try:
        sensor = BME688Sensor()
        logger.info("BME688 sensor initialised")
    except Exception as exc:
        logger.warning(f"BME688 not available: {exc}")
        with _state.lock:
            _state.bme_error = str(exc)
        return

    while not stop.is_set():
        try:
            reading = sensor.read()
            with _state.lock:
                _state.bme = reading
                _state.bme_error = ""
        except Exception as exc:
            logger.warning(f"BME688 read error: {exc}")
            with _state.lock:
                _state.bme_error = str(exc)
        stop.wait(interval)


def _pir_thread(stop: threading.Event, interval: float) -> None:
    try:
        sensor = PIRSensor()
        logger.info("PIR sensor initialised")
    except Exception as exc:
        logger.warning(f"PIR not available: {exc}")
        with _state.lock:
            _state.pir_error = str(exc)
        return

    while not stop.is_set():
        try:
            reading = sensor.read()
            with _state.lock:
                _state.pir = reading
                if reading.motion_detected:
                    _state.pir_events += 1
                _state.pir_error = ""
        except Exception as exc:
            logger.warning(f"PIR read error: {exc}")
            with _state.lock:
                _state.pir_error = str(exc)
        stop.wait(interval)


def _dtof_thread(stop: threading.Event, interval: float) -> None:
    try:
        sensor = DTOFSensor()
        sensor.open()
        logger.info("dToF sensor initialised")
    except Exception as exc:
        logger.warning(f"dToF not available: {exc}")
        with _state.lock:
            _state.dtof_error = str(exc)
        return

    while not stop.is_set():
        try:
            reading = sensor.read()
            with _state.lock:
                _state.dtof = reading
                _state.dtof_error = ""
        except Exception as exc:
            logger.warning(f"dToF read error: {exc}")
            with _state.lock:
                _state.dtof_error = str(exc)
        stop.wait(interval)

    sensor.close()


def _nfc_thread(stop: threading.Event, interval: float) -> None:
    try:
        tag = NFCTag()
        tag.open()
        logger.info("NFC tag initialised")
    except Exception as exc:
        logger.warning(f"NFC not available: {exc}")
        with _state.lock:
            _state.nfc_error = str(exc)
        return

    while not stop.is_set():
        try:
            reading = tag.read(32)
            with _state.lock:
                _state.nfc = reading
                _state.nfc_error = ""
        except Exception as exc:
            logger.warning(f"NFC read error: {exc}")
            with _state.lock:
                _state.nfc_error = str(exc)
        stop.wait(interval)

    tag.close()


def _audio_thread(stop: threading.Event, _interval: float) -> None:  # noqa: ANN001
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError:
        logger.warning("sounddevice / numpy not available — audio disabled")
        return

    def _cb(indata: np.ndarray, _frames: int, _time: object, _status: object) -> None:
        rms = float(np.sqrt(np.mean(indata**2)))
        db = 20 * math.log10(rms) if rms > 0 else -60.0
        with _state.lock:
            _state.audio_db = db
            if db > _state.audio_peak:
                _state.audio_peak = db

    try:
        with sd.InputStream(samplerate=44100, channels=1, dtype="float32", callback=_cb):
            logger.info("Audio stream started")
            while not stop.is_set():
                stop.wait(0.1)
    except Exception as exc:
        logger.warning(f"Audio stream error: {exc}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DB_MIN = -60.0


def _snapshot() -> dict:  # type: ignore[type-arg]
    """Return a serialisable snapshot of the current sensor state."""
    with _state.lock:
        bme = _state.bme
        bme_err = _state.bme_error
        pir = _state.pir
        pir_err = _state.pir_error
        pir_events = _state.pir_events
        dtof = _state.dtof
        dtof_err = _state.dtof_error
        nfc = _state.nfc
        nfc_err = _state.nfc_error
        audio_db = _state.audio_db
        audio_peak = _state.audio_peak

    environment = None
    if bme is not None:
        environment = {
            "temperature_c": bme.temperature_c,
            "temperature_f": bme.temperature_f,
            "humidity_rh": bme.humidity_rh,
            "pressure_hpa": bme.pressure_hpa,
            "gas_resistance_ohm": bme.gas_resistance_ohm,
            "altitude_m": bme.altitude_m,
            "air_quality_label": bme.air_quality_label,
        }

    motion = {
        "detected": pir.motion_detected if pir else False,
        "raw_moving": pir.raw_object_moved if pir else False,
        "event_count": pir_events,
    }

    distance = None
    if dtof is not None:
        distance = {
            "distances_mm": dtof.distances_mm,
            "confidences": dtof.confidences,
            "center_mm": dtof.center_distance_mm,
            "min_mm": dtof.min_distance_mm,
        }

    nfc_data = None
    if nfc is not None:
        nfc_data = {
            "rf_field_present": nfc.rf_field_present,
            "text": nfc.text,
            "raw_hex": nfc.raw_bytes.hex(),
        }

    audio_level = max(0.0, (audio_db - _DB_MIN) / (0.0 - _DB_MIN))
    audio_peak_level = max(0.0, (audio_peak - _DB_MIN) / (0.0 - _DB_MIN))

    return {
        "environment": environment,
        "environment_error": bme_err,
        "motion": motion,
        "motion_error": pir_err,
        "distance": distance,
        "distance_error": dtof_err,
        "nfc": nfc_data,
        "nfc_error": nfc_err,
        "audio": {
            "db": round(audio_db, 1),
            "peak_db": round(audio_peak, 1),
            "level": round(audio_level, 3),
            "peak_level": round(audio_peak_level, 3),
        },
    }


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------

_stop_event = threading.Event()
_threads: list[threading.Thread] = []


@asynccontextmanager
async def lifespan(_app: FastAPI):  # type: ignore[type-arg]
    settings = get_settings()
    _stop_event.clear()

    thread_targets = [
        (_bme_thread, settings.bme_interval, "bme"),
        (_pir_thread, settings.pir_interval, "pir"),
        (_dtof_thread, settings.dtof_interval, "dtof"),
        (_nfc_thread, settings.nfc_interval, "nfc"),
        (_audio_thread, settings.audio_interval, "audio"),
    ]

    for target, interval, name in thread_targets:
        t = threading.Thread(target=target, args=(_stop_event, interval), daemon=True, name=name)
        _threads.append(t)
        t.start()

    logger.info("Sensor background threads started")
    yield

    logger.info("Shutting down sensor threads…")
    _stop_event.set()
    for t in _threads:
        t.join(timeout=2.0)
    _threads.clear()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Pi Sensors API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict:  # type: ignore[type-arg]
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Sensor endpoints
# ---------------------------------------------------------------------------

router_prefix = "/api"


@app.get(f"{router_prefix}/sensors/all")
async def get_all_sensors() -> dict:  # type: ignore[type-arg]
    """Return all sensor readings in a single response."""
    return _snapshot()


@app.get(f"{router_prefix}/sensors/environment")
async def get_environment() -> dict:  # type: ignore[type-arg]
    """BME688 environmental sensor reading."""
    with _state.lock:
        bme = _state.bme
        err = _state.bme_error
    if bme is None:
        return {"error": err or "No reading yet"}
    return {
        "temperature_c": bme.temperature_c,
        "temperature_f": bme.temperature_f,
        "humidity_rh": bme.humidity_rh,
        "pressure_hpa": bme.pressure_hpa,
        "gas_resistance_ohm": bme.gas_resistance_ohm,
        "altitude_m": bme.altitude_m,
        "air_quality_label": bme.air_quality_label,
    }


@app.get(f"{router_prefix}/sensors/motion")
async def get_motion() -> dict:  # type: ignore[type-arg]
    """PIR motion sensor reading."""
    with _state.lock:
        pir = _state.pir
        err = _state.pir_error
        events = _state.pir_events
    return {
        "detected": pir.motion_detected if pir else False,
        "raw_moving": pir.raw_object_moved if pir else False,
        "event_count": events,
        "error": err,
    }


@app.get(f"{router_prefix}/sensors/distance")
async def get_distance() -> dict:  # type: ignore[type-arg]
    """dToF Time-of-Flight 3×3 zone distance readings."""
    with _state.lock:
        dtof = _state.dtof
        err = _state.dtof_error
    if dtof is None:
        return {"error": err or "No reading yet"}
    return {
        "distances_mm": dtof.distances_mm,
        "confidences": dtof.confidences,
        "center_mm": dtof.center_distance_mm,
        "min_mm": dtof.min_distance_mm,
    }


@app.get(f"{router_prefix}/sensors/nfc")
async def get_nfc() -> dict:  # type: ignore[type-arg]
    """NFC/RFID tag status and user memory content."""
    with _state.lock:
        nfc = _state.nfc
        err = _state.nfc_error
    if nfc is None:
        return {"error": err or "No reading yet"}
    return {
        "rf_field_present": nfc.rf_field_present,
        "text": nfc.text,
        "raw_hex": nfc.raw_bytes.hex(),
    }


@app.get(f"{router_prefix}/sensors/audio")
async def get_audio() -> dict:  # type: ignore[type-arg]
    """Microphone RMS level."""
    with _state.lock:
        db = _state.audio_db
        peak = _state.audio_peak
    level = max(0.0, (db - _DB_MIN) / (0.0 - _DB_MIN))
    peak_level = max(0.0, (peak - _DB_MIN) / (0.0 - _DB_MIN))
    return {
        "db": round(db, 1),
        "peak_db": round(peak, 1),
        "level": round(level, 3),
        "peak_level": round(peak_level, 3),
    }


@app.get(f"{router_prefix}/sensors/stream")
async def stream_sensors() -> StreamingResponse:
    """
    Server-Sent Events stream — pushes all sensor readings every 500 ms.

    Connect with:  const es = new EventSource('/api/sensors/stream')
                   es.onmessage = (e) => data = JSON.parse(e.data)
    """
    settings = get_settings()

    async def event_generator():  # type: ignore[return]
        while True:
            snapshot = _snapshot()
            yield f"data: {json.dumps(snapshot)}\n\n"
            await asyncio.sleep(settings.sse_interval)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # noqa: S104
