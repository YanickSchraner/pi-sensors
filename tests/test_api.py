"""
Unit tests for the FastAPI sensor endpoints.

No hardware required — sensor state is injected directly via the module-level
_state singleton before each test.  The FastAPI lifespan (background sensor
threads) is disabled so tests run on any machine.

SSE stream tests use anyio + httpx.AsyncClient so the infinite generator is
properly cancelled via an anyio cancel scope rather than hanging indefinitely.
"""

from __future__ import annotations

import anyio
import httpx
import pytest
from fastapi.testclient import TestClient

import pi_sensors.main as m
from pi_sensors.main import SensorState, _snapshot, app
from pi_sensors.sensors.bme688 import BME688Reading
from pi_sensors.sensors.dtof import DTOFReading
from pi_sensors.sensors.nfc import NFCReading
from pi_sensors.sensors.pir import PIRReading

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_BME = BME688Reading(
    temperature_c=22.5,
    humidity_rh=55.0,
    pressure_hpa=1013.25,
    gas_resistance_ohm=150_000.0,
    altitude_m=100.0,
)
_SAMPLE_PIR = PIRReading(motion_detected=False, raw_object_moved=False)
_SAMPLE_DTOF = DTOFReading(
    distances_mm=[500, 600, 700, 800, 900, 800, 700, 600, 500],
    confidences=[200, 180, 160, 190, 210, 185, 165, 175, 200],
)
_SAMPLE_NFC = NFCReading(raw_bytes=b"\x00" * 32, rf_field_present=False)


@pytest.fixture
def mock_state(monkeypatch: pytest.MonkeyPatch) -> SensorState:
    """Replace the module-level _state with fully-populated test data."""
    state = SensorState()
    state.bme = _SAMPLE_BME
    state.pir = _SAMPLE_PIR
    state.pir_events = 3
    state.dtof = _SAMPLE_DTOF
    state.nfc = _SAMPLE_NFC
    state.audio_db = -20.0
    state.audio_peak = -15.0
    monkeypatch.setattr(m, "_state", state)
    return state


@pytest.fixture
def empty_state(monkeypatch: pytest.MonkeyPatch) -> SensorState:
    """Replace _state with all-None sensor data (sensors unavailable)."""
    state = SensorState()
    state.bme_error = "I2C device not found"
    state.pir_error = "I2C device not found"
    state.dtof_error = "I2C device not found"
    state.nfc_error = "I2C device not found"
    monkeypatch.setattr(m, "_state", state)
    return state


@pytest.fixture
def client() -> TestClient:
    """TestClient with lifespan disabled — no background sensor threads."""
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


def test_health_returns_200(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200


def test_health_body(client: TestClient) -> None:
    r = client.get("/health")
    assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# /api/sensors/all
# ---------------------------------------------------------------------------


def test_all_sensors_keys(client: TestClient, mock_state: SensorState) -> None:
    r = client.get("/api/sensors/all")
    assert r.status_code == 200
    body = r.json()
    assert "environment" in body
    assert "motion" in body
    assert "distance" in body
    assert "nfc" in body
    assert "audio" in body


def test_all_sensors_environment_values(client: TestClient, mock_state: SensorState) -> None:
    body = client.get("/api/sensors/all").json()
    env = body["environment"]
    assert env["temperature_c"] == pytest.approx(22.5)
    assert env["humidity_rh"] == pytest.approx(55.0)
    assert env["pressure_hpa"] == pytest.approx(1013.25)
    assert env["air_quality_label"] == "Good"


def test_all_sensors_motion_values(client: TestClient, mock_state: SensorState) -> None:
    body = client.get("/api/sensors/all").json()
    motion = body["motion"]
    assert motion["detected"] is False
    assert motion["raw_moving"] is False
    assert motion["event_count"] == 3


def test_all_sensors_audio_values(client: TestClient, mock_state: SensorState) -> None:
    body = client.get("/api/sensors/all").json()
    audio = body["audio"]
    assert audio["db"] == pytest.approx(-20.0, abs=0.1)
    assert audio["peak_db"] == pytest.approx(-15.0, abs=0.1)
    assert 0.0 <= audio["level"] <= 1.0
    assert 0.0 <= audio["peak_level"] <= 1.0


def test_all_sensors_unavailable(client: TestClient, empty_state: SensorState) -> None:
    body = client.get("/api/sensors/all").json()
    assert body["environment"] is None
    assert body["environment_error"] == "I2C device not found"
    assert body["distance"] is None
    assert body["nfc"] is None


# ---------------------------------------------------------------------------
# /api/sensors/environment
# ---------------------------------------------------------------------------


def test_environment_happy_path(client: TestClient, mock_state: SensorState) -> None:
    r = client.get("/api/sensors/environment")
    assert r.status_code == 200
    body = r.json()
    assert body["temperature_c"] == pytest.approx(22.5)
    assert body["temperature_f"] == pytest.approx(72.5, abs=0.1)
    assert body["humidity_rh"] == pytest.approx(55.0)
    assert body["pressure_hpa"] == pytest.approx(1013.25)
    assert body["gas_resistance_ohm"] == pytest.approx(150_000.0)
    assert body["altitude_m"] == pytest.approx(100.0)
    assert body["air_quality_label"] in {"Excellent", "Good", "Fair", "Poor"}


def test_environment_temperature_f_conversion(client: TestClient, mock_state: SensorState) -> None:
    body = client.get("/api/sensors/environment").json()
    expected_f = body["temperature_c"] * 9 / 5 + 32
    assert body["temperature_f"] == pytest.approx(expected_f, abs=0.01)


def test_environment_unavailable(client: TestClient, empty_state: SensorState) -> None:
    body = client.get("/api/sensors/environment").json()
    assert "error" in body


# ---------------------------------------------------------------------------
# /api/sensors/motion
# ---------------------------------------------------------------------------


def test_motion_fields(client: TestClient, mock_state: SensorState) -> None:
    body = client.get("/api/sensors/motion").json()
    assert isinstance(body["detected"], bool)
    assert isinstance(body["raw_moving"], bool)
    assert isinstance(body["event_count"], int)


def test_motion_no_detection(client: TestClient, mock_state: SensorState) -> None:
    body = client.get("/api/sensors/motion").json()
    assert body["detected"] is False
    assert body["event_count"] == 3


def test_motion_detected(client: TestClient, mock_state: SensorState) -> None:
    mock_state.pir = PIRReading(motion_detected=True, raw_object_moved=True)
    mock_state.pir_events = 7
    body = client.get("/api/sensors/motion").json()
    assert body["detected"] is True
    assert body["event_count"] == 7


def test_motion_error_field(client: TestClient, empty_state: SensorState) -> None:
    body = client.get("/api/sensors/motion").json()
    assert body["error"] == "I2C device not found"


# ---------------------------------------------------------------------------
# /api/sensors/distance
# ---------------------------------------------------------------------------


def test_distance_zone_count(client: TestClient, mock_state: SensorState) -> None:
    body = client.get("/api/sensors/distance").json()
    assert len(body["distances_mm"]) == 9
    assert len(body["confidences"]) == 9


def test_distance_center_zone(client: TestClient, mock_state: SensorState) -> None:
    body = client.get("/api/sensors/distance").json()
    assert body["center_mm"] == body["distances_mm"][4]


def test_distance_min_is_smallest_positive(client: TestClient, mock_state: SensorState) -> None:
    body = client.get("/api/sensors/distance").json()
    valid = [d for d in body["distances_mm"] if d > 0]
    expected_min = min(valid) if valid else -1
    assert body["min_mm"] == expected_min


def test_distance_unavailable(client: TestClient, empty_state: SensorState) -> None:
    body = client.get("/api/sensors/distance").json()
    assert "error" in body


# ---------------------------------------------------------------------------
# /api/sensors/nfc
# ---------------------------------------------------------------------------


def test_nfc_fields(client: TestClient, mock_state: SensorState) -> None:
    body = client.get("/api/sensors/nfc").json()
    assert "rf_field_present" in body
    assert "text" in body
    assert "raw_hex" in body


def test_nfc_rf_field_is_bool(client: TestClient, mock_state: SensorState) -> None:
    body = client.get("/api/sensors/nfc").json()
    assert isinstance(body["rf_field_present"], bool)


def test_nfc_raw_hex_length(client: TestClient, mock_state: SensorState) -> None:
    """32 raw bytes → 64 hex characters."""
    body = client.get("/api/sensors/nfc").json()
    assert len(body["raw_hex"]) == 64


def test_nfc_rf_on(client: TestClient, mock_state: SensorState) -> None:
    mock_state.nfc = NFCReading(raw_bytes=b"Hello NFC\x00" * 3 + b"\x00" * 2, rf_field_present=True)
    body = client.get("/api/sensors/nfc").json()
    assert body["rf_field_present"] is True
    assert "Hello NFC" in body["text"]


def test_nfc_unavailable(client: TestClient, empty_state: SensorState) -> None:
    body = client.get("/api/sensors/nfc").json()
    assert "error" in body


# ---------------------------------------------------------------------------
# /api/sensors/audio
# ---------------------------------------------------------------------------


def test_audio_fields(client: TestClient, mock_state: SensorState) -> None:
    body = client.get("/api/sensors/audio").json()
    assert "db" in body
    assert "peak_db" in body
    assert "level" in body
    assert "peak_level" in body


def test_audio_level_in_range(client: TestClient, mock_state: SensorState) -> None:
    body = client.get("/api/sensors/audio").json()
    assert 0.0 <= body["level"] <= 1.0
    assert 0.0 <= body["peak_level"] <= 1.0


def test_audio_peak_at_least_current(client: TestClient, mock_state: SensorState) -> None:
    """Peak dB must be >= current dB (peak holds the maximum)."""
    body = client.get("/api/sensors/audio").json()
    assert body["peak_db"] >= body["db"]


def test_audio_silent_state(client: TestClient, mock_state: SensorState) -> None:
    mock_state.audio_db = -60.0
    mock_state.audio_peak = -60.0
    body = client.get("/api/sensors/audio").json()
    assert body["level"] == pytest.approx(0.0, abs=0.01)


def test_audio_full_scale(client: TestClient, mock_state: SensorState) -> None:
    mock_state.audio_db = 0.0
    mock_state.audio_peak = 0.0
    body = client.get("/api/sensors/audio").json()
    assert body["level"] == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# /api/sensors/stream (SSE)
#
# These tests use anyio + httpx.AsyncClient so the infinite SSE generator is
# cancelled cleanly via an anyio cancel scope instead of hanging.
# ---------------------------------------------------------------------------

_TRANSPORT = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
_BASE = "http://test"
_SSE_TIMEOUT = 5.0  # seconds — more than enough to receive one event


@pytest.mark.anyio
async def test_sse_status_and_content_type(mock_state: SensorState) -> None:
    # Wrap in a helper so the move_on_after cancel scope can abort the stream
    # cleanup (which hangs on an infinite while-True generator) without failing
    # the test — assertions are checked *before* cleanup starts.
    async def _check() -> None:
        async with httpx.AsyncClient(transport=_TRANSPORT, base_url=_BASE) as ac:
            async with ac.stream("GET", "/api/sensors/stream") as r:
                assert r.status_code == 200
                assert "text/event-stream" in r.headers["content-type"]

    with anyio.move_on_after(_SSE_TIMEOUT):
        await _check()


def test_snapshot_keys(mock_state: SensorState) -> None:
    """_snapshot() — the function that backs the SSE stream — has all expected keys."""
    payload = _snapshot()
    assert "environment" in payload
    assert "motion" in payload
    assert "distance" in payload
    assert "nfc" in payload
    assert "audio" in payload


def test_snapshot_environment_values(mock_state: SensorState) -> None:
    """_snapshot() returns the correct mocked sensor values."""
    payload = _snapshot()
    env = payload["environment"]
    assert env is not None
    assert env["temperature_c"] == pytest.approx(22.5)
    assert env["humidity_rh"] == pytest.approx(55.0)
    assert env["air_quality_label"] == "Good"


def test_snapshot_motion_values(mock_state: SensorState) -> None:
    payload = _snapshot()
    motion = payload["motion"]
    assert motion["detected"] is False
    assert motion["event_count"] == 3


def test_snapshot_audio_level_normalised(mock_state: SensorState) -> None:
    """audio.level must be between 0 and 1 for any dB value."""
    payload = _snapshot()
    assert 0.0 <= payload["audio"]["level"] <= 1.0
    assert 0.0 <= payload["audio"]["peak_level"] <= 1.0


def test_snapshot_nfc_hex(mock_state: SensorState) -> None:
    """raw_hex must be 64 chars for 32 raw bytes."""
    payload = _snapshot()
    assert len(payload["nfc"]["raw_hex"]) == 64


def test_snapshot_unavailable_sensors(empty_state: SensorState) -> None:
    """When sensors are absent, environment/distance/nfc must be None."""
    payload = _snapshot()
    assert payload["environment"] is None
    assert payload["distance"] is None
    assert payload["nfc"] is None
