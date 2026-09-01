"""Tests for lunar phase classification and lunar data in the astronomy module."""

import sys
from pathlib import Path

# Add src to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from astronomy import _classify_moon_phase, _filter_valid_events, _select_moonrise_moonset, get_lunar_data
from config import NASHVILLE


class _FakeTime:
    """Minimal stand-in for a Skyfield Time, exposing only the `.tt` field
    that _select_moonrise_moonset relies on."""

    def __init__(self, tt):
        self.tt = tt


def test_classify_new_moon():
    """Angles near 0/360 degrees should classify as New Moon."""
    assert _classify_moon_phase(0) == "New Moon"
    assert _classify_moon_phase(359) == "New Moon"
    print("✓ New Moon classified correctly")


def test_classify_first_quarter():
    """An angle of 90 degrees should classify as First Quarter."""
    assert _classify_moon_phase(90) == "First Quarter"
    print("✓ First Quarter classified correctly")


def test_classify_full_moon():
    """An angle of 180 degrees should classify as Full Moon."""
    assert _classify_moon_phase(180) == "Full Moon"
    print("✓ Full Moon classified correctly")


def test_classify_last_quarter():
    """An angle of 270 degrees should classify as Last Quarter."""
    assert _classify_moon_phase(270) == "Last Quarter"
    print("✓ Last Quarter classified correctly")


def test_classify_waxing_and_waning_ranges():
    """Angles between the named phases should classify as crescent/gibbous."""
    assert _classify_moon_phase(45) == "Waxing Crescent"
    assert _classify_moon_phase(135) == "Waxing Gibbous"
    assert _classify_moon_phase(225) == "Waning Gibbous"
    assert _classify_moon_phase(315) == "Waning Crescent"
    print("✓ Waxing/waning crescent and gibbous ranges classified correctly")


def test_get_lunar_data_returns_expected_fields():
    """get_lunar_data should return all documented keys with sane values."""
    lunar = get_lunar_data(NASHVILLE)
    expected_keys = {
        "phase_name", "illumination_percent", "is_waxing",
        "moonrise", "moonset", "above_horizon_during_window",
        "best_viewing_time", "max_altitude"
    }
    assert expected_keys.issubset(lunar.keys())
    assert 0 <= lunar["illumination_percent"] <= 100
    assert isinstance(lunar["above_horizon_during_window"], bool)
    assert isinstance(lunar["is_waxing"], bool)
    print("✓ get_lunar_data returns all expected fields with sane values")


def test_moonrise_before_window_but_still_up():
    """If the Moon rose before the window and is still up, use that rise."""
    window_start = _FakeTime(10.0)
    window_end = _FakeTime(10.5)
    rise_times = [_FakeTime(9.5)]
    set_times = [_FakeTime(10.2)]

    moonrise, moonset = _select_moonrise_moonset(rise_times, set_times, window_start, window_end, True)
    assert moonrise.tt == 9.5
    assert moonset.tt == 10.2
    print("✓ Moonrise before the window is used when the Moon is already up")


def test_moonrise_during_window():
    """If the Moon rises during the window, that rise (and its set) should be used."""
    window_start = _FakeTime(10.0)
    window_end = _FakeTime(10.5)
    rise_times = [_FakeTime(10.2)]
    set_times = [_FakeTime(10.6)]

    moonrise, moonset = _select_moonrise_moonset(rise_times, set_times, window_start, window_end, False)
    assert moonrise.tt == 10.2
    assert moonset.tt == 10.6
    print("✓ Moonrise occurring during the window is used")


def test_avoids_following_nights_moonrise():
    """A future rise after the window shouldn't override tonight's earlier rise."""
    window_start = _FakeTime(10.0)
    window_end = _FakeTime(10.5)
    rise_times = [_FakeTime(9.5), _FakeTime(11.0)]  # 9.5 = tonight, 11.0 = next night
    set_times = [_FakeTime(10.2)]

    moonrise, moonset = _select_moonrise_moonset(rise_times, set_times, window_start, window_end, True)
    assert moonrise.tt == 9.5
    print("✓ Following night's moonrise is not selected when the Moon is already up")


def test_no_applicable_rise_returns_none():
    """If nothing rises during the window and the Moon isn't already up, return None."""
    window_start = _FakeTime(10.0)
    window_end = _FakeTime(10.5)
    rise_times = [_FakeTime(20.0)]  # well beyond the window
    set_times = []

    moonrise, moonset = _select_moonrise_moonset(rise_times, set_times, window_start, window_end, False)
    assert moonrise is None
    assert moonset is None
    print("✓ No applicable rise/set gracefully returns None")


def test_filter_valid_events_ignores_false_flags():
    """A candidate event whose Skyfield flag is False should be discarded."""
    times = [_FakeTime(1.0), _FakeTime(2.0), _FakeTime(3.0)]
    flags = [True, False, True]
    filtered = _filter_valid_events(times, flags)
    assert [t.tt for t in filtered] == [1.0, 3.0]
    print("✓ Events with a False Skyfield flag are filtered out")


if __name__ == "__main__":
    print("Running lunar phase tests...\n")
    test_classify_new_moon()
    test_classify_first_quarter()
    test_classify_full_moon()
    test_classify_last_quarter()
    test_classify_waxing_and_waning_ranges()
    test_get_lunar_data_returns_expected_fields()
    test_moonrise_before_window_but_still_up()
    test_moonrise_during_window()
    test_avoids_following_nights_moonrise()
    test_no_applicable_rise_returns_none()
    test_filter_valid_events_ignores_false_flags()
    print("\n✓ All tests passed!")
