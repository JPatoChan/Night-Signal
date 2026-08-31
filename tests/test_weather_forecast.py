"""Tests for hourly forecast matching in the weather module."""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add src to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from weather import find_nearest_forecast, get_conditions_for_time


def _build_forecast(start, hours):
    """Build a fake hourly forecast dict starting at `start` for `hours` hours."""
    times = [start + timedelta(hours=i) for i in range(hours)]
    return {
        "times": times,
        "cloud_cover": [10 * i for i in range(hours)],
        "visibility": [10.0 for _ in range(hours)],
        "temperature": [15.0 + i for i in range(hours)]
    }


def test_matches_target_before_midnight_same_night():
    """A target time earlier the same night should match the nearest same-day hour."""
    start = datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc)
    forecast = _build_forecast(start, hours=6)
    target_time = start + timedelta(hours=2, minutes=52)  # closest to hour 3
    result = find_nearest_forecast(forecast, target_time)
    assert result is not None
    assert result["forecast_time"] == start + timedelta(hours=3)
    print("✓ Matches nearest hour before midnight")


def test_matches_target_after_midnight():
    """A target time that rolls into the next calendar day should still match correctly."""
    start = datetime(2026, 8, 31, 20, 0, tzinfo=timezone.utc)
    forecast = _build_forecast(start, hours=10)  # spans through 2026-09-01 05:00
    target_time = datetime(2026, 9, 1, 2, 58, tzinfo=timezone.utc)
    result = find_nearest_forecast(forecast, target_time)
    assert result is not None
    assert result["forecast_time"] == datetime(2026, 9, 1, 3, 0, tzinfo=timezone.utc)
    print("✓ Matches nearest hour after midnight")


def test_nearest_hour_matching_picks_closer_point():
    """When a target sits between two hourly points, the closer one wins."""
    start = datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc)
    forecast = _build_forecast(start, hours=5)

    result = find_nearest_forecast(forecast, start + timedelta(hours=1, minutes=20))
    assert result["forecast_time"] == start + timedelta(hours=1)

    result = find_nearest_forecast(forecast, start + timedelta(hours=1, minutes=45))
    assert result["forecast_time"] == start + timedelta(hours=2)
    print("✓ Nearest-hour matching picks the closer forecast point")


def test_missing_forecast_data_returns_none():
    """Empty or missing forecast data should fail gracefully without raising."""
    empty_forecast = {"times": [], "cloud_cover": [], "visibility": [], "temperature": []}
    assert find_nearest_forecast(empty_forecast, datetime.now(timezone.utc)) is None
    assert find_nearest_forecast(empty_forecast, None) is None
    assert find_nearest_forecast(None, datetime.now(timezone.utc)) is None
    print("✓ Missing forecast data returns None without raising")


def test_target_outside_forecast_range_returns_none():
    """A target more than 90 minutes from the nearest forecast point should be rejected."""
    start = datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc)
    forecast = _build_forecast(start, hours=3)  # covers 00:00, 01:00, 02:00
    target_time = start + timedelta(hours=5)  # nearest point (02:00) is 3 hours away
    assert find_nearest_forecast(forecast, target_time) is None
    print("✓ Target outside forecast range returns None")


def test_forecast_entry_with_missing_value_returns_none():
    """A forecast entry missing a required weather value should be rejected."""
    start = datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc)
    forecast = _build_forecast(start, hours=3)
    forecast["cloud_cover"][1] = None  # nearest index for target below
    target_time = start + timedelta(hours=1, minutes=5)
    assert find_nearest_forecast(forecast, target_time) is None
    print("✓ Forecast entry with missing value returns None")


def test_get_conditions_for_time_uses_provided_forecast():
    """get_conditions_for_time should use a pre-fetched forecast without re-fetching."""
    start = datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc)
    forecast = _build_forecast(start, hours=4)
    target_time = start + timedelta(hours=2, minutes=10)
    result = get_conditions_for_time(location=None, target_time=target_time, forecast=forecast)
    assert result is not None
    assert result["forecast_time"] == start + timedelta(hours=2)
    print("✓ get_conditions_for_time uses a pre-fetched forecast without network access")


if __name__ == "__main__":
    print("Running weather forecast matching tests...\n")
    test_matches_target_before_midnight_same_night()
    test_matches_target_after_midnight()
    test_nearest_hour_matching_picks_closer_point()
    test_missing_forecast_data_returns_none()
    test_target_outside_forecast_range_returns_none()
    test_forecast_entry_with_missing_value_returns_none()
    test_get_conditions_for_time_uses_provided_forecast()
    print("\n✓ All tests passed!")
