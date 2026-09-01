"""Tests for Night Signal's Phase 2C date-aware weather (alternate-date forecast support)."""

import sys
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Add repo root (for dashboard.py) and src/ (for weather.py)
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from weather import (
    MAX_FORECAST_DAYS,
    _forecast_days_for_date,
    find_nearest_forecast,
    get_conditions_for_time,
)
from config import NASHVILLE
import dashboard


def _build_forecast(start, hours):
    """Build a fake hourly forecast dict starting at `start` for `hours` hours."""
    times = [start + timedelta(hours=i) for i in range(hours)]
    return {
        "times": times,
        "cloud_cover": [10.0 for _ in range(hours)],
        "visibility": [10.0 for _ in range(hours)],
        "temperature": [15.0 for _ in range(hours)]
    }


def test_forecast_days_within_horizon():
    """A date a few days out should compute a small, sufficient forecast_days."""
    today = date(2026, 9, 1)
    target = date(2026, 9, 4)  # 3 days ahead
    assert _forecast_days_for_date(today, target) == 5  # 3 + 2 padding
    print("✓ Forecast days computed correctly within the supported horizon")


def test_forecast_days_beyond_horizon_returns_none():
    """A date far beyond Open-Meteo's supported horizon should return None,
    signaling 'not forecastable' rather than fabricating a request."""
    today = date(2026, 9, 1)
    target = today + timedelta(days=30)
    assert _forecast_days_for_date(today, target) is None
    print("✓ Dates beyond the forecast horizon return None cleanly")


def test_forecast_days_for_past_date_returns_none():
    """A date in the past isn't forecastable and should return None."""
    today = date(2026, 9, 1)
    target = today - timedelta(days=1)
    assert _forecast_days_for_date(today, target) is None
    print("✓ Past dates return None cleanly")


def test_forecast_days_at_exact_horizon_boundary():
    """The last still-forecastable date should return exactly MAX_FORECAST_DAYS."""
    today = date(2026, 9, 1)
    target = today + timedelta(days=MAX_FORECAST_DAYS - 2)
    assert _forecast_days_for_date(today, target) == MAX_FORECAST_DAYS
    # One day further should push it out of range
    target_over = today + timedelta(days=MAX_FORECAST_DAYS - 1)
    assert _forecast_days_for_date(today, target_over) is None
    print("✓ Forecast horizon boundary is handled correctly")


def test_target_forecast_matching_uses_best_viewing_time_utc():
    """Per-target forecast matching should key off best_viewing_time_utc,
    exactly like Tonight mode, whether the forecast covers tonight or an
    alternate date."""
    start = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)
    forecast = _build_forecast(start, hours=10)
    target = {"best_viewing_time_utc": start + timedelta(hours=3, minutes=5)}

    result = get_conditions_for_time(location=None, target_time=target["best_viewing_time_utc"], forecast=forecast)
    assert result is not None
    assert result["forecast_time"] == start + timedelta(hours=3)
    print("✓ Target forecast matching uses best_viewing_time_utc for alternate dates too")


def test_observing_night_weather_crosses_midnight():
    """A forecast anchor near midnight should still match correctly across
    the calendar-day boundary."""
    start = datetime(2026, 9, 4, 20, 0, tzinfo=timezone.utc)
    forecast = _build_forecast(start, hours=10)  # spans into 2026-09-05
    anchor = datetime(2026, 9, 5, 2, 58, tzinfo=timezone.utc)

    result = find_nearest_forecast(forecast, anchor)
    assert result is not None
    assert result["forecast_time"] == datetime(2026, 9, 5, 3, 0, tzinfo=timezone.utc)
    print("✓ Observing-night weather matching crosses midnight correctly")


def test_current_conditions_never_used_for_alternate_date():
    """get_conditions_for_time with a pre-fetched forecast never touches
    current/live conditions -- it only reads from the supplied forecast."""
    start = datetime(2026, 9, 10, 0, 0, tzinfo=timezone.utc)
    forecast = _build_forecast(start, hours=4)
    anchor = start + timedelta(hours=1)

    # location=None proves no live API call (get_observing_conditions) is
    # ever reached; only the pre-fetched forecast dict is consulted
    result = get_conditions_for_time(location=None, target_time=anchor, forecast=forecast)
    assert result is not None
    assert result["cloud_cover"] == 10.0
    print("✓ Current conditions are never substituted for an alternate date")


def test_api_failure_leaves_matching_gracefully_unavailable():
    """If no forecast is available (e.g. API failure upstream), matching
    should return None rather than raising or fabricating data."""
    result = get_conditions_for_time(location=None, target_time=datetime.now(timezone.utc), forecast=None)
    # forecast=None with location=None forces get_hourly_forecast(None) to
    # raise internally; get_conditions_for_time must catch it gracefully
    assert result is None
    print("✓ API/forecast failure leaves matching gracefully unavailable")


def test_representative_conditions_from_observing_night_not_current_moment():
    """Representative panel conditions should come from the forecast entry
    nearest the observing night's start, not 'right now'."""
    observing_night_start = datetime(2026, 12, 20, 1, 0, tzinfo=timezone.utc)
    forecast = _build_forecast(observing_night_start - timedelta(hours=5), hours=15)

    far_future_now = datetime(2027, 1, 1, tzinfo=timezone.utc)  # simulate "current moment" being unrelated
    result_for_night = get_conditions_for_time(location=None, target_time=observing_night_start, forecast=forecast)
    result_for_now = get_conditions_for_time(location=None, target_time=far_future_now, forecast=forecast)

    assert result_for_night is not None
    assert result_for_now is None  # far outside the forecast's covered range
    print("✓ Representative conditions are drawn from the observing night, not the current moment")


def test_alternate_weather_message_distinguishes_failure_from_out_of_range():
    """The two future-date weather outcomes must produce distinct,
    non-misleading messages (no historical case in V1)."""
    forecast_failure_msg = dashboard.get_alternate_weather_unavailable_message(fetch_failed=True)
    out_of_range_msg = dashboard.get_alternate_weather_unavailable_message(fetch_failed=False)

    assert forecast_failure_msg != out_of_range_msg
    assert "temporarily unavailable" in forecast_failure_msg
    assert "this far out" in out_of_range_msg
    print("✓ Forecast failure and out-of-range messages are distinct")


def test_no_historical_weather_helper_exists():
    """Historical weather support has been removed from V1: no
    get_hourly_historical_weather helper should be importable."""
    import weather
    assert not hasattr(weather, "get_hourly_historical_weather")
    print("✓ Historical weather helper no longer exists")


def test_is_past_observing_date_for_past_date():
    """A date before the location's local today should be treated as a
    past observing date, which skips weather entirely."""
    today_local = datetime.now(ZoneInfo(NASHVILLE.timezone)).date()
    past_date = today_local - timedelta(days=5)
    assert dashboard.is_past_observing_date(NASHVILLE, past_date) is True
    print("✓ A past date is correctly identified as a past observing date")


def test_is_past_observing_date_for_future_date():
    """A date after the location's local today should not be treated as
    a past observing date."""
    today_local = datetime.now(ZoneInfo(NASHVILLE.timezone)).date()
    future_date = today_local + timedelta(days=5)
    assert dashboard.is_past_observing_date(NASHVILLE, future_date) is False
    print("✓ A future date is correctly identified as not a past observing date")


def test_is_past_observing_date_for_tonight_mode():
    """Tonight mode (target_date=None) is never treated as a past date."""
    assert dashboard.is_past_observing_date(NASHVILLE, None) is False
    print("✓ Tonight mode is never treated as a past observing date")


if __name__ == "__main__":
    print("Running Phase 2C date-aware weather tests...\n")
    test_forecast_days_within_horizon()
    test_forecast_days_beyond_horizon_returns_none()
    test_forecast_days_for_past_date_returns_none()
    test_forecast_days_at_exact_horizon_boundary()
    test_target_forecast_matching_uses_best_viewing_time_utc()
    test_observing_night_weather_crosses_midnight()
    test_current_conditions_never_used_for_alternate_date()
    test_api_failure_leaves_matching_gracefully_unavailable()
    test_representative_conditions_from_observing_night_not_current_moment()
    test_alternate_weather_message_distinguishes_failure_from_out_of_range()
    test_no_historical_weather_helper_exists()
    test_is_past_observing_date_for_past_date()
    test_is_past_observing_date_for_future_date()
    test_is_past_observing_date_for_tonight_mode()
    print("\n✓ All tests passed!")
