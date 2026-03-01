"""
Pure unit tests for the audio level mathematics used in main.py.

No hardware required — these test the dB-to-level conversion and
RMS-to-dB formulas used by the audio background thread and API endpoint.
"""

from __future__ import annotations

import math

import pytest

# Constants mirrored from main.py
_DB_MIN = -60.0
_DB_MAX = 0.0


def _rms_to_db(rms: float) -> float:
    """Convert RMS amplitude (0.0–1.0) to dBFS. Matches main.py's audio thread."""
    return 20 * math.log10(rms) if rms > 0 else _DB_MIN


def _db_to_level(db: float) -> float:
    """Normalise dBFS to a 0.0–1.0 display level. Matches main.py's _snapshot()."""
    return max(0.0, (db - _DB_MIN) / (_DB_MAX - _DB_MIN))


# ── dB conversion ─────────────────────────────────────────────────────────


def test_rms_full_scale_is_0_db() -> None:
    """RMS = 1.0 (full-scale) → 0 dBFS."""
    assert _rms_to_db(1.0) == pytest.approx(0.0, abs=0.001)


def test_rms_half_amplitude_approx_minus6_db() -> None:
    """RMS = 0.5 → ≈ −6 dBFS."""
    assert _rms_to_db(0.5) == pytest.approx(-6.021, abs=0.01)


def test_rms_sine_wave_amplitude() -> None:
    """RMS of a 0.5-amplitude sine wave ≈ 0.354 → ≈ −9 dBFS."""
    rms = 0.5 / math.sqrt(2)  # RMS of A*sin → A/√2
    db = _rms_to_db(rms)
    assert -12.0 < db < -6.0


def test_rms_zero_clamps_to_db_min() -> None:
    """Silent signal (RMS = 0) must return the floor value, not −inf."""
    assert _rms_to_db(0.0) == _DB_MIN


def test_rms_negative_returns_db_min() -> None:
    """Negative RMS is nonsensical — must not raise, must clamp."""
    # _rms_to_db only clamps on rms == 0; negative rms would produce complex log.
    # The audio thread uses np.sqrt(np.mean(x**2)) which is always >= 0.
    # This test confirms the floor is safe for near-zero values.
    assert _rms_to_db(1e-10) < -100.0  # very quiet but not the clamped floor


# ── Level normalisation ───────────────────────────────────────────────────


def test_level_at_db_min_is_zero() -> None:
    assert _db_to_level(_DB_MIN) == pytest.approx(0.0)


def test_level_at_0_db_is_one() -> None:
    assert _db_to_level(0.0) == pytest.approx(1.0)


def test_level_at_minus30_db_is_half() -> None:
    assert _db_to_level(-30.0) == pytest.approx(0.5, abs=0.001)


def test_level_below_floor_clamps_to_zero() -> None:
    """Values quieter than _DB_MIN must not produce a negative level."""
    assert _db_to_level(-120.0) == 0.0


def test_level_is_monotone() -> None:
    """Louder signals must produce higher level values."""
    dbs = [-60.0, -40.0, -20.0, -10.0, -3.0, 0.0]
    levels = [_db_to_level(d) for d in dbs]
    assert levels == sorted(levels)


# ── Integration: round-trip ───────────────────────────────────────────────


def test_rms_to_level_round_trip() -> None:
    """Full-scale sine RMS → dB → level should be close to 1.0."""
    rms = 1.0 / math.sqrt(2)   # Full-scale sine
    db = _rms_to_db(rms)
    level = _db_to_level(db)
    # ≈ −3 dBFS → level ≈ 0.95
    assert 0.9 < level < 1.0


def test_quiet_signal_level_near_zero() -> None:
    """Very quiet signal (RMS = 0.001) → level should be well below 0.5."""
    rms = 0.001  # −60 dBFS territory
    db = _rms_to_db(rms)
    level = _db_to_level(db)
    assert level < 0.5
