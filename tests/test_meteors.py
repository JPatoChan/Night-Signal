"""Tests for meteor shower classification and lunar-based interference in the meteors module."""

import sys
from pathlib import Path
from datetime import date

# Add src to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meteors import (
    _classify_shower_status,
    _classify_moon_interference,
    _days_until_start,
    _find_next_upcoming_shower,
    get_meteor_activity,
    METEOR_SHOWERS
)
from astronomy import _midpoint_tt, get_darkest_window_portion
from config import NASHVILLE


def _shower(name):
    """Look up a shower definition by name from the reference data."""
    return next(s for s in METEOR_SHOWERS if s["name"] == name)


def test_inactive_date():
    """A date well outside any active range should classify as Inactive."""
    perseids = _shower("Perseids")  # active Jul 17 - Aug 24
    assert _classify_shower_status((3, 1), perseids) == "Inactive"
    print("✓ Inactive date classified correctly")


def test_active_date():
    """A date within the active range but far from peak should be Active."""
    perseids = _shower("Perseids")  # peak Aug 12
    assert _classify_shower_status((8, 1), perseids) == "Active"
    print("✓ Active date (far from peak) classified correctly")


def test_near_peak_date():
    """A date within NEAR_PEAK_WINDOW_DAYS but outside PEAK_TONIGHT_WINDOW_DAYS is Near Peak."""
    perseids = _shower("Perseids")  # peak Aug 12
    assert _classify_shower_status((8, 10), perseids) == "Near Peak"
    print("✓ Near-peak date classified correctly")


def test_peak_date():
    """The peak date (and the day after, within the tolerance) should be Peak Tonight."""
    perseids = _shower("Perseids")  # peak Aug 12
    assert _classify_shower_status((8, 12), perseids) == "Peak Tonight"
    assert _classify_shower_status((8, 13), perseids) == "Peak Tonight"
    print("✓ Peak date classified correctly")


def test_date_range_crosses_new_year():
    """Quadrantids' active range and peak wrap across New Year's correctly."""
    quadrantids = _shower("Quadrantids")  # active Dec 28 - Jan 12, peak Jan 4

    # Dec 28 is the very start of the range, several days from peak -> Active
    assert _classify_shower_status((12, 28), quadrantids) == "Active"

    # Jan 2 is 2 days before the Jan 4 peak, crossing the year boundary -> Near Peak
    assert _classify_shower_status((1, 2), quadrantids) == "Near Peak"

    # Jan 4 is the peak itself -> Peak Tonight
    assert _classify_shower_status((1, 4), quadrantids) == "Peak Tonight"

    # Jan 13 is just past the active range's end -> Inactive
    assert _classify_shower_status((1, 13), quadrantids) == "Inactive"
    print("✓ Date ranges crossing New Year's handled correctly")


def test_moon_interference_classification():
    """Moon interference should follow the documented illumination/horizon rules."""
    assert _classify_moon_interference(90, False) == "Low"  # not above horizon -> Low regardless
    assert _classify_moon_interference(10, True) == "Low"
    assert _classify_moon_interference(35, True) == "Moderate"
    assert _classify_moon_interference(80, True) == "High"
    print("✓ Moon interference classified correctly")


def test_get_meteor_activity_returns_expected_structure():
    """get_meteor_activity should return sane, well-formed results for a real location."""
    activity = get_meteor_activity(NASHVILLE, today=date(2026, 8, 12))  # Perseids peak
    assert activity["has_activity"] is True
    names = [s["name"] for s in activity["active_showers"]]
    assert "Perseids" in names
    primary = activity["active_showers"][0]
    assert primary["name"] == "Perseids"
    assert primary["status"] == "Peak Tonight"
    expected_keys = {
        "name", "status", "active_start", "active_end", "peak_date",
        "typical_zhr", "radiant", "best_viewing_window", "moon_interference"
    }
    assert expected_keys.issubset(primary.keys())
    print("✓ get_meteor_activity returns expected structure for a real location")


def test_get_meteor_activity_no_activity():
    """A date with no active showers should report has_activity=False."""
    activity = get_meteor_activity(NASHVILLE, today=date(2026, 3, 1))
    assert activity["has_activity"] is False
    assert activity["active_showers"] == []
    print("✓ get_meteor_activity reports no activity when nothing is active")


def test_midpoint_unaffected_by_midnight_crossing():
    """Midpoint math operates on continuous Julian dates, so a window that
    crosses local midnight (e.g. 8:45 PM to 4:49 AM) is handled correctly
    without any local-calendar wraparound logic."""
    start_tt = 2460000.0
    end_tt = start_tt + (8 / 24)  # 8 hours later, crossing midnight locally
    midpoint = _midpoint_tt(start_tt, end_tt)
    assert abs(midpoint - (start_tt + (4 / 24))) < 1e-9
    print("✓ Midpoint calculation is unaffected by midnight rollover")


def test_darkest_window_portion_for_real_location():
    """get_darkest_window_portion should return a valid start/end for a
    real location whose dark window is known to cross midnight."""
    window = get_darkest_window_portion(NASHVILLE)
    assert window["start"] is not None
    assert window["end"] is not None
    print("✓ Best viewing window resolves correctly across midnight")


def test_next_upcoming_shower_within_same_year():
    """Between Quadrantids and Lyrids, the next upcoming shower should be
    Lyrids later in the same calendar year, with no wraparound needed."""
    upcoming = _find_next_upcoming_shower(date(2026, 2, 1))  # nothing active
    assert upcoming["name"] == "Lyrids"
    assert upcoming["active_start"] == "Apr 14"
    assert upcoming["days_until_start"] > 0
    print("✓ Next upcoming shower within the same calendar year resolved correctly")


def test_next_upcoming_shower_across_new_year():
    """A synthetic shower list is used to force the search to wrap from
    December into the following January, confirming the circular distance
    math handles year rollover rather than picking a same-year shower."""
    synthetic_showers = [
        {"name": "Early January Shower", "start": (1, 5), "end": (1, 10),
         "peak": (1, 7), "typical_zhr": 30, "radiant": "Test"},
        {"name": "Mid-Year Shower", "start": (6, 1), "end": (6, 10),
         "peak": (6, 5), "typical_zhr": 40, "radiant": "Test"},
    ]
    # Dec 20: the only forward path to "Early January Shower" wraps into
    # next year, while "Mid-Year Shower" is much farther away either way
    upcoming = _find_next_upcoming_shower(date(2026, 12, 20), synthetic_showers)
    assert upcoming["name"] == "Early January Shower"
    assert upcoming["days_until_start"] == 16  # Dec 20, 2026 -> Jan 5, 2027
    print("✓ Next upcoming shower across New Year's resolved correctly")


def test_days_until_start_leap_year_correctness():
    """Real calendar-date arithmetic must count Feb 29 in a leap year,
    unlike a fixed 365-day reference year which would undercount by one."""
    synthetic_shower = {"name": "March Shower", "start": (3, 1), "end": (3, 5),
                         "peak": (3, 3), "typical_zhr": 10, "radiant": "Test"}
    # 2024 is a leap year: Jan 30 -> Mar 1 spans a 29-day February
    days = _days_until_start(date(2024, 1, 30), synthetic_shower)
    assert days == 31
    print("✓ Leap-year day counting is correct")


def test_days_until_start_same_day_returns_zero():
    """If a shower starts today, days_until_start should be exactly 0."""
    synthetic_shower = {"name": "Today Shower", "start": (8, 12), "end": (8, 20),
                         "peak": (8, 15), "typical_zhr": 10, "radiant": "Test"}
    days = _days_until_start(date(2026, 8, 12), synthetic_shower)
    assert days == 0
    print("✓ Same-day shower start returns 0 days")


def test_no_active_shower_empty_state_data():
    """When nothing is active, get_meteor_activity should populate
    next_shower with usable empty-state data instead of leaving it blank."""
    activity = get_meteor_activity(NASHVILLE, today=date(2026, 3, 1))
    assert activity["has_activity"] is False
    assert activity["active_showers"] == []
    next_shower = activity["next_shower"]
    assert next_shower is not None
    expected_keys = {"name", "active_start", "peak_date", "typical_zhr", "days_until_start"}
    assert expected_keys.issubset(next_shower.keys())
    assert next_shower["days_until_start"] > 0
    print("✓ No-active-shower empty state includes usable next-shower data")


if __name__ == "__main__":
    print("Running meteor shower tests...\n")
    test_inactive_date()
    test_active_date()
    test_near_peak_date()
    test_peak_date()
    test_date_range_crosses_new_year()
    test_moon_interference_classification()
    test_get_meteor_activity_returns_expected_structure()
    test_get_meteor_activity_no_activity()
    test_midpoint_unaffected_by_midnight_crossing()
    test_darkest_window_portion_for_real_location()
    test_next_upcoming_shower_within_same_year()
    test_next_upcoming_shower_across_new_year()
    test_days_until_start_leap_year_correctness()
    test_days_until_start_same_day_returns_zero()
    test_no_active_shower_empty_state_data()
    print("\n✓ All tests passed!")
