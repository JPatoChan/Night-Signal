"""Tests for Night Signal's date-aware astronomy and meteor calculations (Phase 2A)."""

import sys
from pathlib import Path
from datetime import date, timedelta
from zoneinfo import ZoneInfo

# Add src to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from skyfield.api import Topos

from astronomy import (
    _get_ephemeris_and_timescale,
    _local_noon_time,
    _find_tonights_window,
    get_observing_window,
    get_observing_window_utc,
    get_target_list,
    get_lunar_data,
    get_darkest_window_portion,
)
from meteors import get_meteor_activity
from config import NASHVILLE, DENVER


def test_default_behavior_still_works_without_target_date():
    """Calling the public functions with no target_date should still work
    exactly as before (no exceptions, sane structure)."""
    window = get_observing_window(NASHVILLE)
    assert "evening_twilight_end" in window and "morning_twilight_begin" in window

    targets = get_target_list(NASHVILLE)
    assert isinstance(targets, list)

    lunar = get_lunar_data(NASHVILLE)
    assert "phase_name" in lunar

    darkest = get_darkest_window_portion(NASHVILLE)
    assert "start" in darkest and "end" in darkest
    print("✓ Default (no target_date) behavior still works for all four functions")


def test_future_target_date_returns_window_for_that_evening():
    """A known future date should produce an observing window, not an error."""
    target_date = date(2026, 12, 20)  # well in the future relative to "today"
    window = get_observing_window(NASHVILLE, target_date=target_date)
    assert window["evening_twilight_end"] is not None
    assert window["morning_twilight_begin"] is not None
    print("✓ A future target date returns a populated observing window")


def test_observing_window_crosses_midnight_for_target_date():
    """The dark window for a given evening should start on target_date and
    end the following calendar day, in the observer's own timezone."""
    ephemeris, ts = _get_ephemeris_and_timescale()
    timezone = ZoneInfo(NASHVILLE.timezone)
    observer_topos = Topos(latitude_degrees=NASHVILLE.latitude, longitude_degrees=NASHVILLE.longitude)

    target_date = date(2026, 8, 12)
    reference_time = _local_noon_time(ts, target_date, timezone)
    _, window_start, window_end = _find_tonights_window(ephemeris, ts, observer_topos, reference_time)

    start_local_date = window_start.utc_datetime().astimezone(timezone).date()
    end_local_date = window_end.utc_datetime().astimezone(timezone).date()

    assert start_local_date == target_date
    assert end_local_date == target_date + timedelta(days=1)
    print("✓ Observing window correctly crosses midnight for the requested date")


def test_selected_date_uses_location_timezone():
    """The same calendar date should resolve using each location's own
    timezone, not a shared/server timezone."""
    target_date = date(2026, 8, 12)

    nashville_window = get_observing_window(NASHVILLE, target_date=target_date)
    denver_window = get_observing_window(DENVER, target_date=target_date)

    assert any(tz in nashville_window["evening_twilight_end"] for tz in ("CDT", "CST"))
    assert any(tz in denver_window["evening_twilight_end"] for tz in ("MDT", "MST"))
    print("✓ Selected date resolution uses each location's own timezone")


def test_dst_boundary_behavior():
    """A target date shortly after a US DST transition should still
    resolve to a valid same-day observing window."""
    # 2026 DST spring-forward is March 8; pick the following day
    target_date = date(2026, 3, 9)
    window = get_observing_window(NASHVILLE, target_date=target_date)
    assert window["evening_twilight_end"] is not None
    assert window["morning_twilight_begin"] is not None
    print("✓ DST boundary date resolves to a valid observing window")


def test_planet_targets_use_requested_date():
    """Planet best-viewing UTC datetimes should fall within the requested
    date's evening/next-morning window, not the real current night."""
    target_date = date(2026, 12, 20)
    targets = get_target_list(NASHVILLE, target_date=target_date)
    assert isinstance(targets, list)

    timezone = ZoneInfo(NASHVILLE.timezone)
    for target in targets:
        assert "best_viewing_time_utc" in target
        local_date = target["best_viewing_time_utc"].astimezone(timezone).date()
        assert local_date in (target_date, target_date + timedelta(days=1))
    print("✓ Planet target calculations use the requested observing date")


def test_lunar_data_changes_with_target_date():
    """Lunar phase/illumination should differ meaningfully roughly two
    weeks apart (near-opposite points in the lunar cycle)."""
    date_a = date(2026, 8, 1)
    date_b = date_a + timedelta(days=15)

    lunar_a = get_lunar_data(NASHVILLE, target_date=date_a)
    lunar_b = get_lunar_data(NASHVILLE, target_date=date_b)

    assert (
        lunar_a["phase_name"] != lunar_b["phase_name"]
        or abs(lunar_a["illumination_percent"] - lunar_b["illumination_percent"]) > 10
    )
    print("✓ Lunar data changes appropriately when the target date changes")


def test_meteor_activity_uses_requested_date():
    """get_meteor_activity should reflect Perseids being at peak on Aug 12."""
    activity = get_meteor_activity(NASHVILLE, today=date(2026, 8, 12))
    assert activity["has_activity"] is True
    primary = activity["active_showers"][0]
    assert primary["name"] == "Perseids"
    assert primary["status"] == "Peak Tonight"
    assert primary["best_viewing_window"] is not None
    print("✓ Meteor activity uses the requested observing date")


def test_darkest_window_portion_uses_requested_date():
    """get_darkest_window_portion should resolve differently across two
    dates roughly six months apart (different sunset/sunrise times)."""
    window_summer = get_darkest_window_portion(NASHVILLE, target_date=date(2026, 8, 12))
    window_winter = get_darkest_window_portion(NASHVILLE, target_date=date(2026, 12, 20))

    assert window_summer["start"] is not None and window_summer["end"] is not None
    assert window_winter["start"] is not None and window_winter["end"] is not None
    assert window_summer != window_winter
    print("✓ get_darkest_window_portion uses the requested observing date")


def test_observing_window_utc_matches_formatted_window():
    """get_observing_window_utc should describe the same window as
    get_observing_window(), just as UTC datetimes instead of formatted
    local strings (used as a forecast-matching anchor in Phase 2C)."""
    target_date = date(2026, 8, 12)
    timezone = ZoneInfo(NASHVILLE.timezone)

    formatted_window = get_observing_window(NASHVILLE, target_date=target_date)
    utc_window = get_observing_window_utc(NASHVILLE, target_date=target_date)

    assert utc_window["evening_twilight_end"] is not None
    assert utc_window["morning_twilight_begin"] is not None

    local_start = utc_window["evening_twilight_end"].astimezone(timezone)
    assert local_start.strftime("%I:%M %p %Z").lstrip("0") == formatted_window["evening_twilight_end"]
    print("✓ get_observing_window_utc matches the formatted observing window")


if __name__ == "__main__":
    print("Running date-aware astronomy/meteor tests...\n")
    test_default_behavior_still_works_without_target_date()
    test_future_target_date_returns_window_for_that_evening()
    test_observing_window_crosses_midnight_for_target_date()
    test_selected_date_uses_location_timezone()
    test_dst_boundary_behavior()
    test_planet_targets_use_requested_date()
    test_lunar_data_changes_with_target_date()
    test_meteor_activity_uses_requested_date()
    test_darkest_window_portion_uses_requested_date()
    test_observing_window_utc_matches_formatted_window()
    print("\n✓ All tests passed!")
