"""Tests for Night Signal's Special Signal (Phase 3A: NEO close approaches)."""

import sys
import json
from contextlib import ExitStack
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo

import numpy as np

# Add repo root (for dashboard.py) and src/ (for special_events.py)
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import special_events
from special_events import (
    MAX_EVENTS,
    MAJOR_SIGNAL_THRESHOLD,
    STRONG_SIGNAL_THRESHOLD,
    SpecialEventsFetchError,
    _classify_signal_level,
    _parse_neo,
    get_special_signal,
    get_planetary_conjunctions,
    _classify_conjunction_signal_level,
    MAJOR_CONJUNCTION_DEGREES,
    STRONG_CONJUNCTION_DEGREES,
    INTERESTING_CONJUNCTION_DEGREES,
    ISS_MAJOR_ALTITUDE_DEGREES,
    ISS_MIN_ALTITUDE_DEGREES,
    ISS_STRONG_ALTITUDE_DEGREES,
    ISS_TLE_VALIDITY_DAYS,
    _classify_comet_signal_level,
    _classify_eclipse_signal_level,
    _classify_iss_signal_level,
    get_next_comet_event,
    get_next_eclipse_event,
    get_next_iss_pass,
    get_next_notable_neo,
    get_next_planetary_conjunction,
    get_upcoming_special_signals,
    get_comet_events,
    get_eclipse_events,
    get_iss_passes,
)
from config import NASHVILLE
import dashboard


def _make_raw_neo(name, lunar_distance, diameter_min_km, diameter_max_km, hazardous, miles=None, mph=None):
    """Build a raw NeoWs-shaped NEO entry (NASA returns numbers as strings)."""
    return {
        "name": name,
        "is_potentially_hazardous_asteroid": hazardous,
        "absolute_magnitude_h": 20.0,
        "estimated_diameter": {
            "kilometers": {
                "estimated_diameter_min": diameter_min_km,
                "estimated_diameter_max": diameter_max_km
            },
            "feet": {
                "estimated_diameter_min": diameter_min_km * 3280.8,
                "estimated_diameter_max": diameter_max_km * 3280.8
            }
        },
        "close_approach_data": [
            {
                "close_approach_date_full": "2026-Oct-21 05:16",
                "relative_velocity": {"miles_per_hour": str(mph or 25000)},
                "miss_distance": {
                    "lunar": str(lunar_distance),
                    "miles": str(miles or lunar_distance * 238855)
                }
            }
        ]
    }


def _mock_neo_response(date_str, raw_neos):
    """Build a MagicMock standing in for NASA's feed API urlopen response."""
    payload = {"near_earth_objects": {date_str: raw_neos}}
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(payload).encode()
    mock_response.__enter__.return_value = mock_response
    return mock_response


def _mock_no_upcoming():
    """Keep primary Special Signal tests from doing fallback/network work."""
    return patch.object(special_events, "get_upcoming_special_signals", return_value=[])


def _mock_non_neo_primary_sources():
    """Keep NEO-focused tests from doing unrelated primary-source work."""
    stack = ExitStack()
    stack.enter_context(patch.object(special_events, "get_eclipse_events", return_value=[]))
    stack.enter_context(patch.object(special_events, "get_comet_events", return_value=[]))
    stack.enter_context(patch.object(special_events, "get_iss_passes", return_value=[]))
    stack.enter_context(patch.object(special_events, "get_planetary_conjunctions", return_value=[]))
    return stack


def test_selected_date_is_passed_to_neo_fetch():
    """get_special_signal should query the NASA feed for the selected
    target_date, not the current server date."""
    target_date = date(2026, 10, 21)
    captured_urls = []

    def fake_urlopen(url, timeout=5):
        captured_urls.append(url)
        return _mock_neo_response(target_date.isoformat(), [])

    with patch.object(special_events.urllib.request, "urlopen", side_effect=fake_urlopen), _mock_non_neo_primary_sources(), _mock_no_upcoming():
        get_special_signal(NASHVILLE, target_date=target_date)

    assert any("2026-10-21" in url for url in captured_urls)
    print("✓ Selected date is passed to the NEO data fetch")


def test_successful_api_parsing():
    """A mocked API response should parse into the expected normalized shape."""
    target_date = date(2026, 10, 21)
    raw_neo = _make_raw_neo("(2026 XY1)", lunar_distance=0.5, diameter_min_km=0.5, diameter_max_km=1.2, hazardous=True)
    mock_response = _mock_neo_response(target_date.isoformat(), [raw_neo])

    with patch.object(special_events.urllib.request, "urlopen", return_value=mock_response), _mock_non_neo_primary_sources(), _mock_no_upcoming():
        result = get_special_signal(NASHVILLE, target_date=target_date)

    assert result["has_events"] is True
    event = result["events"][0]
    assert event["name"] == "(2026 XY1)"
    assert event["event_type"] == "Near-Earth Object"
    assert event["signal_level"] == "Major Signal"
    assert event["details"]["is_potentially_hazardous"] is True
    assert "naked-eye" in event["summary"] or "telescope" in event["summary"]
    print("✓ Successful API response parses into the expected structure")


def test_ranking_chooses_most_notable_events():
    """The most significant events (closest/largest/hazardous) should
    sort first."""
    target_date = date(2026, 10, 21)
    small_far = _make_raw_neo("Small Far", lunar_distance=25, diameter_min_km=0.02, diameter_max_km=0.03, hazardous=False)
    big_close_hazardous = _make_raw_neo("Big Close Hazardous", lunar_distance=0.3, diameter_min_km=1.0, diameter_max_km=1.5, hazardous=True)
    mock_response = _mock_neo_response(target_date.isoformat(), [small_far, big_close_hazardous])

    with patch.object(special_events.urllib.request, "urlopen", return_value=mock_response), _mock_non_neo_primary_sources(), _mock_no_upcoming():
        result = get_special_signal(NASHVILLE, target_date=target_date)

    names = [event["name"] for event in result["events"]]
    assert names[0] == "Big Close Hazardous"
    print("✓ Ranking surfaces the most notable event first")


def test_ranking_caps_output_at_three():
    """No more than MAX_EVENTS notable events should ever be returned."""
    target_date = date(2026, 10, 21)
    raw_neos = [
        _make_raw_neo(f"Notable {i}", lunar_distance=0.2, diameter_min_km=1.0, diameter_max_km=1.5, hazardous=True)
        for i in range(6)
    ]
    mock_response = _mock_neo_response(target_date.isoformat(), raw_neos)

    with patch.object(special_events.urllib.request, "urlopen", return_value=mock_response), _mock_non_neo_primary_sources(), _mock_no_upcoming():
        result = get_special_signal(NASHVILLE, target_date=target_date)

    assert len(result["events"]) == MAX_EVENTS
    print("✓ Ranking caps output at MAX_EVENTS")


def test_signal_tiers_are_assigned_deterministically():
    """Signal tier thresholds should be strict and deterministic."""
    assert _classify_signal_level(MAJOR_SIGNAL_THRESHOLD) == "Major Signal"
    assert _classify_signal_level(MAJOR_SIGNAL_THRESHOLD - 1) == "Strong Signal"
    assert _classify_signal_level(STRONG_SIGNAL_THRESHOLD) == "Strong Signal"
    assert _classify_signal_level(STRONG_SIGNAL_THRESHOLD - 1) == "Interesting Signal"
    print("✓ Signal tiers are assigned deterministically")


def test_empty_data_produces_clean_empty_state():
    """No NEOs (or none notable enough) for a date should produce a clean
    empty state, not an error."""
    target_date = date(2026, 10, 21)
    mock_response = _mock_neo_response(target_date.isoformat(), [])

    with patch.object(special_events.urllib.request, "urlopen", return_value=mock_response), _mock_non_neo_primary_sources(), _mock_no_upcoming():
        result = get_special_signal(NASHVILLE, target_date=target_date)

    assert result["has_events"] is False
    assert result["events"] == []
    print("✓ Empty NEO data produces a clean empty state")


def test_below_threshold_events_are_excluded():
    """An event scoring below MIN_NOTABLE_SCORE should not be surfaced."""
    target_date = date(2026, 10, 21)
    tiny_distant = _make_raw_neo("Tiny Distant", lunar_distance=29, diameter_min_km=0.01, diameter_max_km=0.015, hazardous=False)
    mock_response = _mock_neo_response(target_date.isoformat(), [tiny_distant])

    with patch.object(special_events.urllib.request, "urlopen", return_value=mock_response), _mock_non_neo_primary_sources(), _mock_no_upcoming():
        result = get_special_signal(NASHVILLE, target_date=target_date)

    assert result["has_events"] is False
    print("✓ Below-threshold events are excluded from the surfaced list")


def test_api_failure_degrades_gracefully():
    """A NASA API failure must not raise or suppress other Special Signal
    sources (e.g. conjunctions) -- get_special_signal() isolates NEO
    fetch failures internally and simply omits NEO events."""
    with patch.object(special_events.urllib.request, "urlopen", side_effect=special_events.urllib.error.URLError("boom")), _mock_non_neo_primary_sources(), _mock_no_upcoming():
        result = get_special_signal(NASHVILLE, target_date=date(2026, 10, 21))

    assert isinstance(result, dict)
    assert "events" in result and "has_events" in result
    assert all(e["event_type"] != "Near-Earth Object" for e in result["events"])
    print("✓ NASA API failure degrades gracefully instead of raising")


def test_alternate_date_does_not_use_current_date():
    """A far-future target_date should be queried exactly, never silently
    substituted with today's date."""
    target_date = date.today() + timedelta(days=100)
    captured_urls = []

    def fake_urlopen(url, timeout=5):
        captured_urls.append(url)
        return _mock_neo_response(target_date.isoformat(), [])

    with patch.object(special_events.urllib.request, "urlopen", side_effect=fake_urlopen), _mock_non_neo_primary_sources(), _mock_no_upcoming():
        get_special_signal(NASHVILLE, target_date=target_date)

    assert any(target_date.isoformat() in url for url in captured_urls)
    assert not any(date.today().isoformat() in url for url in captured_urls) or target_date == date.today()
    print("✓ Alternate date does not accidentally use the current date")


def test_dashboard_renders_special_signal_failure_gracefully():
    """render_special_signal(None) must not raise -- Special Signal
    failing should never break the rest of the dashboard."""
    dashboard.render_special_signal(None, target_date=date(2026, 10, 21))
    dashboard.render_special_signal({"events": [], "has_events": False}, target_date=None)
    print("✓ Dashboard renders Special Signal's failure/empty states without raising")


def test_parse_neo_handles_missing_close_approach_data():
    """A NEO entry with no close_approach_data should parse to None
    rather than raising."""
    assert _parse_neo({"name": "No Approach Data"}) is None
    print("✓ Missing close-approach data is handled gracefully")


class _FakeAngle:
    """Stand-in for a Skyfield Angle: exposes only .degrees."""
    def __init__(self, degrees):
        self.degrees = degrees


class _FakeApparent:
    """Stand-in for a Skyfield Apparent position with fixed separation/altitude arrays."""
    def __init__(self, separations, altitudes):
        self._separations = separations
        self._altitudes = altitudes

    def separation_from(self, other):
        return _FakeAngle(self._separations)

    def altaz(self):
        return (_FakeAngle(self._altitudes), None, None)


class _FakeObservePosition:
    def __init__(self, apparent):
        self._apparent = apparent

    def apparent(self):
        return self._apparent


class _FakeAstrometric:
    def __init__(self, apparents_by_token):
        self._apparents_by_token = apparents_by_token

    def observe(self, planet_token):
        return _FakeObservePosition(self._apparents_by_token[planet_token])


class _FakeObserver:
    def __init__(self, apparents_by_token):
        self._apparents_by_token = apparents_by_token

    def at(self, times):
        return _FakeAstrometric(self._apparents_by_token)


class _FakeEarth:
    def __init__(self, apparents_by_token):
        self._apparents_by_token = apparents_by_token

    def __add__(self, topos):
        return _FakeObserver(self._apparents_by_token)


def _patched_conjunction_environment(separation_degrees, altitude_a=45.0, altitude_b=45.0):
    """Patch special_events' astronomy calls so get_planetary_conjunctions
    operates over exactly one fake planet pair with a fixed, known
    separation and altitude at every sample point. Returns an ExitStack;
    caller must use `with`."""
    num_samples = 145
    separations = np.full(num_samples, separation_degrees)
    altitudes_a = np.full(num_samples, altitude_a)
    altitudes_b = np.full(num_samples, altitude_b)

    apparents_by_token = {
        "planet_a": _FakeApparent(separations, altitudes_a),
        "planet_b": _FakeApparent(separations, altitudes_b),
    }
    fake_ephemeris = {"earth": _FakeEarth(apparents_by_token), "planet_a": "planet_a", "planet_b": "planet_b"}

    class _FakeTs:
        def tt_jd(self, arr):
            return arr

    class _FakeTime:
        def __init__(self, tt):
            self.tt = tt

    stack = ExitStack()
    stack.enter_context(patch.object(special_events, "PLANET_NAMES", ["planet_a", "planet_b"]))
    stack.enter_context(patch.object(special_events, "DISPLAY_NAMES", {"planet_a": "A", "planet_b": "B"}))
    stack.enter_context(patch.object(special_events, "_get_ephemeris_and_timescale", return_value=(fake_ephemeris, _FakeTs())))
    stack.enter_context(patch.object(special_events, "_find_tonights_window", return_value=(None, _FakeTime(0.0), _FakeTime(1.0))))
    stack.enter_context(patch.object(special_events, "_format_local_time", return_value="10:00 PM CDT"))
    return stack


def test_conjunction_signal_tier_thresholds():
    """Angular separation maps deterministically to a signal tier."""
    assert _classify_conjunction_signal_level(0.3) == "Major Signal"
    assert _classify_conjunction_signal_level(MAJOR_CONJUNCTION_DEGREES) == "Major Signal"
    assert _classify_conjunction_signal_level(0.8) == "Strong Signal"
    assert _classify_conjunction_signal_level(STRONG_CONJUNCTION_DEGREES) == "Strong Signal"
    assert _classify_conjunction_signal_level(2.5) == "Interesting Signal"
    assert _classify_conjunction_signal_level(INTERESTING_CONJUNCTION_DEGREES) == "Interesting Signal"
    print("✓ Angular separation maps to the correct signal tier")


def test_conjunction_excludes_wide_separations():
    """Separations wider than the Interesting threshold are not surfaced."""
    assert _classify_conjunction_signal_level(3.5) is None
    print("✓ Separations wider than 3.0° are excluded")


def test_conjunction_major_tier_end_to_end():
    """A very close, well-placed pair produces a Major Signal conjunction event."""
    with _patched_conjunction_environment(separation_degrees=0.3, altitude_a=45.0, altitude_b=45.0):
        events = get_planetary_conjunctions(NASHVILLE)

    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "Planetary Conjunction"
    assert event["signal_level"] == "Major Signal"
    assert event["name"] == "A & B"
    assert event["angular_separation_degrees"] == 0.3
    print("✓ A close, well-placed pair produces a Major Signal conjunction")


def test_conjunction_below_horizon_excluded():
    """A close pair is not surfaced if either planet is below the
    minimum altitude threshold, even at closest approach."""
    with _patched_conjunction_environment(separation_degrees=0.3, altitude_a=5.0, altitude_b=45.0):
        events = get_planetary_conjunctions(NASHVILLE)

    assert events == []
    print("✓ A pair below the minimum altitude is excluded")


def test_conjunction_event_time_within_window():
    """The reported best-viewing sample always falls within the sampled window."""
    with _patched_conjunction_environment(separation_degrees=1.0, altitude_a=30.0, altitude_b=30.0):
        events = get_planetary_conjunctions(NASHVILLE)

    assert len(events) == 1
    print("✓ Reported event time is drawn from within the observing window")


def test_conjunction_respects_target_date():
    """target_date is threaded into _local_noon_time; Tonight mode (None)
    never calls it, so it can't accidentally reuse a stale reference."""
    with _patched_conjunction_environment(separation_degrees=5.0):
        with patch.object(special_events, "_local_noon_time") as mock_local_noon:
            get_planetary_conjunctions(NASHVILLE, target_date=None)
            mock_local_noon.assert_not_called()

            some_date = date(2026, 10, 21)
            get_planetary_conjunctions(NASHVILLE, target_date=some_date)
            assert mock_local_noon.call_args[0][1] == some_date
    print("✓ target_date is respected and Tonight mode never reuses a stale reference")


def test_merge_combines_conjunctions_and_neos():
    """Combined results include both event types and are capped at MAX_EVENTS."""
    conjunction_events = [
        {"name": "A & B", "event_type": "Planetary Conjunction", "signal_level": "Major Signal",
         "angular_separation_degrees": 0.3, "event_time": "x", "altitude_degrees": 40.0,
         "summary": "s", "details": {}},
        {"name": "C & D", "event_type": "Planetary Conjunction", "signal_level": "Strong Signal",
         "angular_separation_degrees": 1.0, "event_time": "x", "altitude_degrees": 40.0,
         "summary": "s", "details": {}},
    ]
    neo_events = [
        {"name": "NEO1", "event_type": "Near-Earth Object", "signal_level": "Major Signal",
         "event_time": "x", "summary": "s", "details": {}},
        {"name": "NEO2", "event_type": "Near-Earth Object", "signal_level": "Strong Signal",
         "event_time": "x", "summary": "s", "details": {}},
        {"name": "NEO3", "event_type": "Near-Earth Object", "signal_level": "Interesting Signal",
         "event_time": "x", "summary": "s", "details": {}},
    ]
    with patch.object(special_events, "_get_ranked_neo_events", return_value=neo_events), \
         patch.object(special_events, "get_planetary_conjunctions", return_value=conjunction_events):
        result = get_special_signal(NASHVILLE)

    assert len(result["events"]) == MAX_EVENTS
    names = [e["name"] for e in result["events"]]
    assert names == ["A & B", "C & D", "NEO1"]
    print("✓ Combined results merge both sources, ranked correctly and capped at MAX_EVENTS")


def test_observable_conjunction_outranks_weaker_neo():
    """An Interesting-tier conjunction ranks above a non-Major NEO."""
    conjunction_events = [
        {"name": "A & B", "event_type": "Planetary Conjunction", "signal_level": "Interesting Signal",
         "angular_separation_degrees": 2.5, "event_time": "x", "altitude_degrees": 20.0,
         "summary": "s", "details": {}},
    ]
    neo_events = [
        {"name": "NEO1", "event_type": "Near-Earth Object", "signal_level": "Strong Signal",
         "event_time": "x", "summary": "s", "details": {}},
    ]
    with patch.object(special_events, "_get_ranked_neo_events", return_value=neo_events), \
         patch.object(special_events, "get_planetary_conjunctions", return_value=conjunction_events):
        result = get_special_signal(NASHVILLE)

    assert [e["name"] for e in result["events"]] == ["A & B", "NEO1"]
    print("✓ An observable conjunction outranks a weaker NEO")


def test_one_special_signal_source_failing_does_not_suppress_other():
    """A NEO fetch failure still allows conjunctions to render, and vice versa."""
    conjunction_events = [
        {"name": "A & B", "event_type": "Planetary Conjunction", "signal_level": "Major Signal",
         "angular_separation_degrees": 0.3, "event_time": "x", "altitude_degrees": 40.0,
         "summary": "s", "details": {}},
    ]
    with patch.object(special_events, "_get_ranked_neo_events", side_effect=SpecialEventsFetchError("boom")), \
         patch.object(special_events, "get_planetary_conjunctions", return_value=conjunction_events):
        result = get_special_signal(NASHVILLE)
    assert [e["name"] for e in result["events"]] == ["A & B"]

    neo_events = [
        {"name": "NEO1", "event_type": "Near-Earth Object", "signal_level": "Major Signal",
         "event_time": "x", "summary": "s", "details": {}},
    ]
    with patch.object(special_events, "_get_ranked_neo_events", return_value=neo_events), \
         patch.object(special_events, "get_planetary_conjunctions", side_effect=RuntimeError("boom")):
        result = get_special_signal(NASHVILLE)
    assert [e["name"] for e in result["events"]] == ["NEO1"]
    print("✓ One Special Signal source failing does not suppress the other")


def test_locally_relevant_solar_eclipse_is_surfaced():
    """A curated solar eclipse is only surfaced when the selected location
    is inside the local visibility region and the Sun is above the horizon."""
    eclipse = {
        "name": "Test Total Solar Eclipse",
        "event_type": "Solar Eclipse",
        "date": "2026-10-21",
        "peak_utc": "2026-10-21T18:00:00+00:00",
        "eclipse_kind": "total",
        "visibility": "test visibility region",
        "lat_min": 30.0,
        "lat_max": 40.0,
        "lon_min": -90.0,
        "lon_max": -80.0,
    }
    with patch.object(special_events, "CURATED_ECLIPSES", [eclipse]), \
         patch.object(special_events, "_altitude_degrees_for_body", return_value=42.0):
        events = get_eclipse_events(NASHVILLE, target_date=date(2026, 10, 21))

    assert len(events) == 1
    assert events[0]["event_type"] == "Solar Eclipse"
    assert events[0]["signal_level"] == "Major Signal"
    assert "relevant to your region" in events[0]["summary"]
    assert "Exact local eclipse magnitude or totality is not calculated" in events[0]["summary"]
    assert "total solar eclipse will be visible from this location" not in events[0]["summary"]
    print("✓ Locally relevant solar eclipse is surfaced")


def test_eclipse_elsewhere_is_excluded():
    """A solar eclipse outside the observer's local visibility region is not surfaced."""
    eclipse = {
        "name": "Elsewhere Solar Eclipse",
        "event_type": "Solar Eclipse",
        "date": "2026-10-21",
        "peak_utc": "2026-10-21T18:00:00+00:00",
        "eclipse_kind": "partial",
        "visibility": "elsewhere",
        "lat_min": -40.0,
        "lat_max": -30.0,
        "lon_min": 120.0,
        "lon_max": 150.0,
    }
    with patch.object(special_events, "CURATED_ECLIPSES", [eclipse]), \
         patch.object(special_events, "_altitude_degrees_for_body", return_value=42.0):
        events = get_eclipse_events(NASHVILLE, target_date=date(2026, 10, 21))

    assert events == []
    print("✓ Eclipse elsewhere is excluded for the selected location")


def test_lunar_eclipse_target_date_and_tier_are_respected():
    """A locally observable total lunar eclipse matches the selected date
    and receives the correct signal tier."""
    eclipse = {
        "name": "Test Total Lunar Eclipse",
        "event_type": "Lunar Eclipse",
        "date": "2026-10-21",
        "peak_utc": "2026-10-22T02:00:00+00:00",
        "eclipse_kind": "total",
    }

    def fake_window(location, target_date):
        if target_date == date(2026, 10, 21):
            return (
                datetime(2026, 10, 22, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc),
            )
        return (
            datetime(2026, 10, 21, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc),
        )

    with patch.object(special_events, "CURATED_ECLIPSES", [eclipse]), \
         patch.object(special_events, "_get_observing_window_datetimes", side_effect=fake_window), \
         patch.object(special_events, "_altitude_degrees_for_body", return_value=35.0):
        wrong_date_events = get_eclipse_events(NASHVILLE, target_date=date(2026, 10, 20))
        selected_date_events = get_eclipse_events(NASHVILLE, target_date=date(2026, 10, 21))

    assert wrong_date_events == []
    assert len(selected_date_events) == 1
    assert selected_date_events[0]["signal_level"] == "Major Signal"
    assert _classify_eclipse_signal_level({"event_type": "Lunar Eclipse", "eclipse_kind": "partial"}) == "Strong Signal"
    print("✓ Lunar eclipse target_date and signal tier are respected")


def test_notable_comet_is_surfaced():
    """A curated comet that is active, bright enough, and high enough is surfaced."""
    comet = {
        "name": "Test Comet",
        "active_start": "2026-10-01",
        "active_end": "2026-10-31",
        "peak_date": "2026-10-21",
        "magnitude": 4.2,
        "ra_hours": 12.0,
        "dec_degrees": 20.0,
        "note": "near a useful peak",
    }
    captured = []

    def fake_best(location, target_date, body):
        captured.append((location, target_date))
        return "9:30 PM CDT", 44.0

    with patch.object(special_events, "CURATED_COMETS", [comet]), \
         patch.object(special_events, "_sample_body_altitude_over_window", side_effect=fake_best):
        events = get_comet_events(NASHVILLE, target_date=date(2026, 10, 21))

    assert len(events) == 1
    assert events[0]["event_type"] == "Comet"
    assert events[0]["signal_level"] == "Strong Signal"
    assert "Viewing time and altitude are approximate" in events[0]["summary"]
    assert events[0]["details"]["position_precision"] == "curated approximate fixed coordinates"
    assert captured == [(NASHVILLE, date(2026, 10, 21))]
    print("✓ Notable comet is surfaced with target_date and location respected")


def test_weak_or_low_comet_is_excluded_and_visibility_not_fabricated():
    """Weak comets are excluded, and challenging surfaced comets do not
    claim naked-eye visibility."""
    weak_comet = {
        "name": "Weak Comet",
        "active_start": "2026-10-01",
        "active_end": "2026-10-31",
        "peak_date": "2026-10-21",
        "magnitude": 12.0,
        "ra_hours": 12.0,
        "dec_degrees": 20.0,
        "note": "too faint for the primary signal",
    }
    challenging_comet = dict(weak_comet, name="Challenging Comet", magnitude=8.0)

    with patch.object(special_events, "CURATED_COMETS", [weak_comet]), \
         patch.object(special_events, "_sample_body_altitude_over_window", return_value=("9:30 PM CDT", 44.0)):
        assert get_comet_events(NASHVILLE, target_date=date(2026, 10, 21)) == []

    with patch.object(special_events, "CURATED_COMETS", [challenging_comet]), \
         patch.object(special_events, "_sample_body_altitude_over_window", return_value=("9:30 PM CDT", 44.0)):
        events = get_comet_events(NASHVILLE, target_date=date(2026, 10, 21))

    assert len(events) == 1
    assert events[0]["signal_level"] == "Interesting Signal"
    assert "not a claimed naked-eye sight" in events[0]["summary"]
    assert _classify_comet_signal_level(12.0) is None
    print("✓ Weak comet is excluded and visibility claims are not fabricated")


class _FakeSatelliteTime:
    def __init__(self, dt):
        self._dt = dt

    def utc_datetime(self):
        return self._dt


class _FakeSatelliteAltitude:
    def __init__(self, degrees):
        self.degrees = degrees


class _FakeSatelliteTopocentric:
    def __init__(self, altitude_degrees):
        self._altitude_degrees = altitude_degrees

    def altaz(self):
        return (_FakeSatelliteAltitude(self._altitude_degrees), None, None)

    def is_sunlit(self, ephemeris):
        return True


class _FakeSatellite:
    def __init__(self, line1, line2, name, ts):
        self.name = name

    def find_events(self, observer, t0, t1, altitude_degrees=20):
        if observer.latitude.degrees > 40:
            return [], []
        return ([
            _FakeSatelliteTime(datetime(2026, 10, 22, 1, 10, tzinfo=timezone.utc)),
            _FakeSatelliteTime(datetime(2026, 10, 22, 1, 14, tzinfo=timezone.utc)),
            _FakeSatelliteTime(datetime(2026, 10, 22, 1, 18, tzinfo=timezone.utc)),
        ], [0, 1, 2])

    def __sub__(self, observer):
        return self

    def at(self, time):
        return _FakeSatelliteTopocentric(62.0)


class _FakeSatelliteTimescale:
    def from_datetime(self, dt):
        return _FakeSatelliteTime(dt)


def test_high_altitude_iss_pass_is_surfaced_and_local_time_is_used():
    """A sunlit ISS pass above the altitude threshold is surfaced with a local peak time."""
    target_date = datetime.now(ZoneInfo(NASHVILLE.timezone)).date()
    with patch.object(special_events, "_get_observing_window_datetimes", return_value=(
            datetime(2026, 10, 22, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc),
         )), \
         patch.object(special_events, "_get_ephemeris_and_timescale", return_value=({"earth": object(), "sun": object()}, _FakeSatelliteTimescale())), \
         patch.object(special_events, "_fetch_iss_tle", return_value=("ISS", "1", "2")), \
         patch.object(special_events, "EarthSatellite", _FakeSatellite):
        events = get_iss_passes(NASHVILLE, target_date=target_date)

    assert len(events) == 1
    assert events[0]["event_type"] == "ISS Pass"
    assert events[0]["signal_level"] == "Strong Signal"
    assert events[0]["details"]["best_viewing_time"] == "8:14 PM CDT"
    assert _classify_iss_signal_level(ISS_MAJOR_ALTITUDE_DEGREES) == "Major Signal"
    assert _classify_iss_signal_level(ISS_STRONG_ALTITUDE_DEGREES) == "Strong Signal"
    assert _classify_iss_signal_level(ISS_MIN_ALTITUDE_DEGREES) == "Interesting Signal"
    print("✓ High-altitude ISS pass is surfaced with local/date-aware timing")


def test_near_date_iss_pass_still_works():
    """ISS pass prediction is still allowed inside the conservative TLE window."""
    target_date = datetime.now(ZoneInfo(NASHVILLE.timezone)).date() + timedelta(days=ISS_TLE_VALIDITY_DAYS)
    with patch.object(special_events, "_get_observing_window_datetimes", return_value=(
            datetime(2026, 10, 22, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc),
         )), \
         patch.object(special_events, "_get_ephemeris_and_timescale", return_value=({"earth": object(), "sun": object()}, _FakeSatelliteTimescale())), \
         patch.object(special_events, "_fetch_iss_tle", return_value=("ISS", "1", "2")), \
         patch.object(special_events, "EarthSatellite", _FakeSatellite):
        events = get_iss_passes(NASHVILLE, target_date=target_date)

    assert len(events) == 1
    print("✓ Near-date ISS pass still works inside the TLE validity window")


def test_low_altitude_iss_pass_is_excluded():
    """ISS passes below 20° are not useful enough for the primary signal."""
    assert _classify_iss_signal_level(19.9) is None
    print("✓ Low-altitude ISS pass is excluded")


def test_iss_selected_location_and_target_date_affect_relevance():
    """The ISS source receives the selected location/date and can produce
    different results by observer latitude."""
    high_lat_location = type(NASHVILLE)("High Lat", 45.0, NASHVILLE.longitude, NASHVILLE.timezone)
    target_date = datetime.now(ZoneInfo(NASHVILLE.timezone)).date()
    captured = []

    def fake_window(location, target_date):
        captured.append((location, target_date))
        return (
            datetime(2026, 10, 22, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc),
        )

    with patch.object(special_events, "_get_observing_window_datetimes", side_effect=fake_window), \
         patch.object(special_events, "_get_ephemeris_and_timescale", return_value=({"earth": object(), "sun": object()}, _FakeSatelliteTimescale())), \
         patch.object(special_events, "_fetch_iss_tle", return_value=("ISS", "1", "2")), \
         patch.object(special_events, "EarthSatellite", _FakeSatellite):
        nashville_events = get_iss_passes(NASHVILLE, target_date=target_date)
        high_lat_events = get_iss_passes(high_lat_location, target_date=target_date)

    assert len(nashville_events) == 1
    assert high_lat_events == []
    assert captured == [(NASHVILLE, target_date), (high_lat_location, target_date)]
    print("✓ ISS pass relevance respects selected location and target_date")


def test_far_future_iss_date_returns_no_events_without_error():
    """Current ISS TLEs are not used for far-future pass predictions."""
    far_future = datetime.now(ZoneInfo(NASHVILLE.timezone)).date() + timedelta(days=ISS_TLE_VALIDITY_DAYS + 1)
    with patch.object(special_events, "_get_observing_window_datetimes") as mock_window, \
         patch.object(special_events, "_fetch_iss_tle") as mock_fetch:
        events = get_iss_passes(NASHVILLE, target_date=far_future)

    assert events == []
    mock_window.assert_not_called()
    mock_fetch.assert_not_called()
    print("✓ Far-future ISS date returns no events without error")


def test_far_past_iss_date_returns_no_events_without_error():
    """Current ISS TLEs are not used for far-past pass predictions."""
    far_past = datetime.now(ZoneInfo(NASHVILLE.timezone)).date() - timedelta(days=ISS_TLE_VALIDITY_DAYS + 1)
    with patch.object(special_events, "_get_observing_window_datetimes") as mock_window, \
         patch.object(special_events, "_fetch_iss_tle") as mock_fetch:
        events = get_iss_passes(NASHVILLE, target_date=far_past)

    assert events == []
    mock_window.assert_not_called()
    mock_fetch.assert_not_called()
    print("✓ Far-past ISS date returns no events without error")


def test_all_special_signal_types_merge_and_cap():
    """All source types merge into one deterministic, capped Special Signal list."""
    eclipse_events = [{"name": "Solar", "event_type": "Solar Eclipse", "signal_level": "Major Signal", "event_time": "1", "summary": "s", "details": {"eclipse_kind": "total"}}]
    comet_events = [{"name": "Comet", "event_type": "Comet", "signal_level": "Major Signal", "event_time": "2", "summary": "s", "details": {}}]
    iss_events = [{"name": "ISS", "event_type": "ISS Pass", "signal_level": "Major Signal", "event_time": "3", "summary": "s", "details": {}}]
    conjunction_events = [{"name": "Conj", "event_type": "Planetary Conjunction", "signal_level": "Major Signal", "event_time": "4", "summary": "s", "details": {}}]
    neo_events = [{"name": "NEO", "event_type": "Near-Earth Object", "signal_level": "Major Signal", "event_time": "5", "summary": "s", "details": {}}]

    with patch.object(special_events, "get_eclipse_events", return_value=eclipse_events), \
         patch.object(special_events, "get_comet_events", return_value=comet_events), \
         patch.object(special_events, "get_iss_passes", return_value=iss_events), \
         patch.object(special_events, "get_planetary_conjunctions", return_value=conjunction_events), \
         patch.object(special_events, "_get_ranked_neo_events", return_value=neo_events):
        result = get_special_signal(NASHVILLE)

    assert len(result["events"]) == MAX_EVENTS
    assert [event["name"] for event in result["events"]] == ["Solar", "Comet", "Conj"]
    print("✓ All Special Signal types merge correctly and cap at MAX_EVENTS")


def test_empty_successful_sources_produce_clean_empty_state():
    """If every source succeeds but none has a notable event, the result is a normal empty state."""
    with patch.object(special_events, "get_eclipse_events", return_value=[]), \
         patch.object(special_events, "get_comet_events", return_value=[]), \
         patch.object(special_events, "get_iss_passes", return_value=[]), \
         patch.object(special_events, "get_planetary_conjunctions", return_value=[]), \
            patch.object(special_events, "_get_ranked_neo_events", return_value=[]), \
            _mock_no_upcoming():
        result = get_special_signal(NASHVILLE)

    assert result["has_events"] is False
    assert result["all_sources_failed"] is False
    print("✓ Empty successful sources produce a clean empty state")


def test_total_special_signal_failure_is_reported_gracefully():
    """If every source fails, Special Signal reports an unavailable state instead of crashing."""
    with patch.object(special_events, "get_eclipse_events", side_effect=RuntimeError("boom")), \
         patch.object(special_events, "get_comet_events", side_effect=RuntimeError("boom")), \
         patch.object(special_events, "get_iss_passes", side_effect=RuntimeError("boom")), \
         patch.object(special_events, "get_planetary_conjunctions", side_effect=RuntimeError("boom")), \
            patch.object(special_events, "_get_ranked_neo_events", side_effect=RuntimeError("boom")), \
            patch.object(special_events, "get_upcoming_special_signals", side_effect=RuntimeError("boom")):
        result = get_special_signal(NASHVILLE)

    assert result["has_events"] is False
    assert result["all_sources_failed"] is True
    dashboard.render_special_signal(result, target_date=date(2026, 10, 21))
    print("✓ Total Special Signal failure produces a graceful unavailable state")


def test_next_notable_neo_finds_first_qualifying_future_date():
    """NEO fallback skips selected date/non-notable days and returns the
    highest-ranked NEO on the first future qualifying date."""
    selected_date = date(2026, 10, 21)
    first_future = selected_date + timedelta(days=1)
    second_future = selected_date + timedelta(days=2)
    selected_day_neo = _make_raw_neo("Selected Day", lunar_distance=0.2, diameter_min_km=1.0, diameter_max_km=1.5, hazardous=True)
    non_notable = _make_raw_neo("Too Quiet", lunar_distance=29, diameter_min_km=0.01, diameter_max_km=0.015, hazardous=False)
    weaker = _make_raw_neo("Weaker Future", lunar_distance=10, diameter_min_km=0.2, diameter_max_km=0.3, hazardous=False)
    stronger = _make_raw_neo("Stronger Future", lunar_distance=0.2, diameter_min_km=1.0, diameter_max_km=1.5, hazardous=True)

    def fake_range(start_date, end_date):
        assert start_date == first_future
        return {
            selected_date.isoformat(): [selected_day_neo],
            first_future.isoformat(): [non_notable],
            second_future.isoformat(): [weaker, stronger],
        }

    with patch.object(special_events, "_fetch_neo_feed_range", side_effect=fake_range):
        event = get_next_notable_neo(NASHVILLE, target_date=selected_date, max_days_ahead=7)

    assert event["date"] == second_future
    assert event["name"] == "Stronger Future"
    assert event["event_type"] == "Near-Earth Object Flyby"
    print("✓ Next NEO fallback finds the first future qualifying date and top NEO")


def test_next_notable_neo_respects_horizon_and_api_failure():
    """NEO fallback respects max_days_ahead and returns None on API failure."""
    selected_date = date(2026, 10, 21)
    future_outside_horizon = selected_date + timedelta(days=3)
    notable = _make_raw_neo("Outside Horizon", lunar_distance=0.2, diameter_min_km=1.0, diameter_max_km=1.5, hazardous=True)

    with patch.object(special_events, "_fetch_neo_feed_range", return_value={future_outside_horizon.isoformat(): [notable]}):
        assert get_next_notable_neo(NASHVILLE, target_date=selected_date, max_days_ahead=2) is None

    with patch.object(special_events, "_fetch_neo_feed_range", side_effect=SpecialEventsFetchError("boom")):
        assert get_next_notable_neo(NASHVILLE, target_date=selected_date, max_days_ahead=2) is None
    print("✓ Next NEO fallback respects horizon and API failures")


def test_next_planetary_conjunction_finds_first_observable_date_and_stops():
    """Conjunction fallback skips quiet dates, respects location/date,
    and stops after the first qualifying future observing date."""
    selected_date = date(2026, 10, 21)
    candidate_event = {"name": "Venus & Jupiter", "event_type": "Planetary Conjunction", "signal_level": "Strong Signal", "event_time": "9:00 PM CDT", "summary": "s", "details": {}}
    calls = []

    def fake_conjunctions(location, target_date):
        calls.append((location, target_date))
        if target_date == selected_date + timedelta(days=3):
            return [candidate_event]
        return []

    with patch.object(special_events, "_coarse_conjunction_candidate_dates", return_value=[
            selected_date + timedelta(days=1),
            selected_date + timedelta(days=2),
            selected_date + timedelta(days=3),
         ]), \
         patch.object(special_events, "get_planetary_conjunctions", side_effect=fake_conjunctions):
        event = get_next_planetary_conjunction(NASHVILLE, target_date=selected_date, max_days_ahead=10)

    assert event["name"] == "Venus & Jupiter"
    assert event["date"] == selected_date + timedelta(days=3)
    assert calls == [
        (NASHVILLE, selected_date + timedelta(days=1)),
        (NASHVILLE, selected_date + timedelta(days=2)),
        (NASHVILLE, selected_date + timedelta(days=3)),
    ]
    print("✓ Next conjunction fallback finds the first observable date and stops")


def test_next_eclipse_finds_future_local_event_with_conservative_wording():
    """Eclipse fallback uses the curated dataset and preserves V1 locality caveats."""
    selected_date = date(2026, 10, 21)
    irrelevant = {
        "name": "Irrelevant Eclipse", "event_type": "Solar Eclipse", "date": "2026-10-22",
        "peak_utc": "2026-10-22T18:00:00+00:00", "eclipse_kind": "total", "visibility": "elsewhere",
        "lat_min": -40.0, "lat_max": -30.0, "lon_min": 120.0, "lon_max": 150.0,
    }
    relevant = {
        "name": "Relevant Eclipse", "event_type": "Solar Eclipse", "date": "2026-10-25",
        "peak_utc": "2026-10-25T18:00:00+00:00", "eclipse_kind": "total", "visibility": "nearby",
        "lat_min": 30.0, "lat_max": 40.0, "lon_min": -90.0, "lon_max": -80.0,
    }

    with patch.object(special_events, "CURATED_ECLIPSES", [irrelevant, relevant]), \
         patch.object(special_events, "_altitude_degrees_for_body", return_value=42.0):
        event = get_next_eclipse_event(NASHVILLE, target_date=selected_date)

    assert event["name"] == "Relevant Eclipse"
    assert event["date"] == date(2026, 10, 25)
    assert "Exact local eclipse magnitude or totality is not calculated" in event["summary"]
    print("✓ Next eclipse fallback finds local event and preserves conservative wording")


def test_next_comet_finds_future_window_and_preserves_approximation_caveat():
    """Comet fallback finds the next curated active window and keeps approximation wording."""
    selected_date = date(2026, 10, 21)
    comet = {
        "name": "Future Comet", "active_start": "2026-10-24", "active_end": "2026-10-26",
        "peak_date": "2026-10-25", "magnitude": 5.0, "ra_hours": 12.0, "dec_degrees": 20.0,
        "note": "near a useful future window",
    }

    with patch.object(special_events, "CURATED_COMETS", [comet]), \
         patch.object(special_events, "_sample_body_altitude_over_window", return_value=("9:30 PM CDT", 44.0)):
        event = get_next_comet_event(NASHVILLE, target_date=selected_date)

    assert event["name"] == "Future Comet"
    assert event["date"] == date(2026, 10, 24)
    assert "Viewing time and altitude are approximate" in event["summary"]

    with patch.object(special_events, "CURATED_COMETS", []):
        assert get_next_comet_event(NASHVILLE, target_date=selected_date) is None
    print("✓ Next comet fallback finds future window and preserves approximation caveat")


def test_next_iss_pass_uses_only_valid_tle_window():
    """ISS fallback can search near dates but returns no far-date fallback."""
    current_date = datetime.now(ZoneInfo(NASHVILLE.timezone)).date()
    iss_event = {"name": "ISS Pass", "event_type": "ISS Pass", "signal_level": "Interesting Signal", "event_time": "8:12 PM CDT", "summary": "s", "details": {}}
    calls = []

    def fake_passes(location, target_date):
        calls.append(target_date)
        return [iss_event]

    with patch.object(special_events, "get_iss_passes", side_effect=fake_passes):
        event = get_next_iss_pass(NASHVILLE, target_date=current_date, max_days_ahead=1)

    assert event["date"] == current_date + timedelta(days=1)
    assert calls == [current_date + timedelta(days=1)]

    far_future = current_date + timedelta(days=ISS_TLE_VALIDITY_DAYS + 1)
    far_past = current_date - timedelta(days=ISS_TLE_VALIDITY_DAYS + 2)
    with patch.object(special_events, "_get_observing_window_datetimes") as mock_window, \
         patch.object(special_events, "_fetch_iss_tle") as mock_fetch:
        assert get_next_iss_pass(NASHVILLE, target_date=far_future) is None
        assert get_next_iss_pass(NASHVILLE, target_date=far_past) is None
    mock_window.assert_not_called()
    mock_fetch.assert_not_called()
    print("✓ Next ISS fallback uses only the valid TLE window")


def test_upcoming_candidates_sort_chronologically_and_cap_at_two():
    """Coming Up sorting is chronological first; a farther Major eclipse
    does not outrank a sooner Strong conjunction."""
    selected_date = date(2026, 10, 21)
    sooner_conjunction = {"name": "Soon Conjunction", "event_type": "Planetary Conjunction", "date": selected_date + timedelta(days=2), "event_time": "9 PM", "signal_level": "Strong Signal", "summary": "s"}
    middle_comet = {"name": "Middle Comet", "event_type": "Comet", "date": selected_date + timedelta(days=3), "event_time": "10 PM", "signal_level": "Strong Signal", "summary": "s"}
    farther_eclipse = {"name": "Far Eclipse", "event_type": "Solar Eclipse", "date": selected_date + timedelta(days=10), "event_time": "Noon", "signal_level": "Major Signal", "summary": "s"}

    with patch.object(special_events, "get_next_notable_neo", return_value=None), \
         patch.object(special_events, "get_next_planetary_conjunction", return_value=sooner_conjunction), \
         patch.object(special_events, "get_next_eclipse_event", return_value=farther_eclipse), \
         patch.object(special_events, "get_next_comet_event", return_value=middle_comet), \
         patch.object(special_events, "get_next_iss_pass", return_value=None):
        upcoming = get_upcoming_special_signals(NASHVILLE, target_date=selected_date, limit=2)

    assert [event["name"] for event in upcoming] == ["Soon Conjunction", "Middle Comet"]
    print("✓ Upcoming candidates sort chronologically and cap at two")


def test_upcoming_signal_strength_breaks_same_date_ties_and_selected_date_is_excluded():
    """Same-date Coming Up ties use signal strength, and selected-date
    candidates are never returned as future fallbacks."""
    selected_date = date(2026, 10, 21)
    selected_day_event = {"name": "Selected Day", "event_type": "Comet", "date": selected_date, "event_time": "9 PM", "signal_level": "Major Signal", "summary": "s"}
    strong_event = {"name": "Strong Same Day", "event_type": "ISS Pass", "date": selected_date + timedelta(days=2), "event_time": "8 PM", "signal_level": "Strong Signal", "summary": "s"}
    major_event = {"name": "Major Same Day", "event_type": "Comet", "date": selected_date + timedelta(days=2), "event_time": "9 PM", "signal_level": "Major Signal", "summary": "s"}

    with patch.object(special_events, "get_next_notable_neo", return_value=selected_day_event), \
         patch.object(special_events, "get_next_planetary_conjunction", return_value=strong_event), \
         patch.object(special_events, "get_next_eclipse_event", return_value=major_event), \
         patch.object(special_events, "get_next_comet_event", return_value=None), \
         patch.object(special_events, "get_next_iss_pass", side_effect=RuntimeError("boom")):
        upcoming = get_upcoming_special_signals(NASHVILLE, target_date=selected_date, limit=2)

    assert [event["name"] for event in upcoming] == ["Major Same Day", "Strong Same Day"]
    print("✓ Signal strength breaks same-date ties and selected-date events are excluded")


def test_get_special_signal_limits_upcoming_by_primary_count():
    """Primary events remain unchanged and determine how many Coming Up rows are returned."""
    primary_one = {"name": "Primary 1", "event_type": "Comet", "signal_level": "Major Signal", "event_time": "1", "summary": "s", "details": {}}
    primary_two = {"name": "Primary 2", "event_type": "ISS Pass", "signal_level": "Strong Signal", "event_time": "2", "summary": "s", "details": {}}
    primary_three = {"name": "Primary 3", "event_type": "Planetary Conjunction", "signal_level": "Interesting Signal", "event_time": "3", "summary": "s", "details": {}}
    upcoming = [
        {"name": "Up 1", "event_type": "Comet", "date": date(2026, 10, 22), "event_time": "9 PM", "signal_level": "Strong Signal", "summary": "s"},
        {"name": "Up 2", "event_type": "ISS Pass", "date": date(2026, 10, 23), "event_time": "8 PM", "signal_level": "Interesting Signal", "summary": "s"},
    ]

    with patch.object(special_events, "get_eclipse_events", return_value=[primary_one, primary_two, primary_three]), \
         patch.object(special_events, "get_comet_events", return_value=[]), \
         patch.object(special_events, "get_iss_passes", return_value=[]), \
         patch.object(special_events, "get_planetary_conjunctions", return_value=[]), \
         patch.object(special_events, "_get_ranked_neo_events", return_value=[]), \
         patch.object(special_events, "get_upcoming_special_signals", return_value=upcoming) as mock_upcoming:
        result = get_special_signal(NASHVILLE)
    assert {event["name"] for event in result["events"]} == {"Primary 1", "Primary 2", "Primary 3"}
    assert result["upcoming"] == []
    mock_upcoming.assert_not_called()

    with patch.object(special_events, "get_eclipse_events", return_value=[primary_one]), \
         patch.object(special_events, "get_comet_events", return_value=[]), \
         patch.object(special_events, "get_iss_passes", return_value=[]), \
         patch.object(special_events, "get_planetary_conjunctions", return_value=[]), \
         patch.object(special_events, "_get_ranked_neo_events", return_value=[]), \
         patch.object(special_events, "get_upcoming_special_signals", return_value=upcoming[:1]) as mock_upcoming:
        result = get_special_signal(NASHVILLE)
    assert [event["name"] for event in result["events"]] == ["Primary 1"]
    assert len(result["upcoming"]) == 1
    mock_upcoming.assert_called_once_with(NASHVILLE, None, limit=1, skip_sources=set())

    with patch.object(special_events, "get_eclipse_events", return_value=[]), \
         patch.object(special_events, "get_comet_events", return_value=[]), \
         patch.object(special_events, "get_iss_passes", return_value=[]), \
         patch.object(special_events, "get_planetary_conjunctions", return_value=[]), \
         patch.object(special_events, "_get_ranked_neo_events", return_value=[]), \
         patch.object(special_events, "get_upcoming_special_signals", return_value=upcoming) as mock_upcoming:
        result = get_special_signal(NASHVILLE)
    assert result["events"] == []
    assert len(result["upcoming"]) == 2
    mock_upcoming.assert_called_once_with(NASHVILLE, None, limit=2, skip_sources=set())
    print("✓ Primary event count controls Coming Up limits without displacing primaries")


def test_render_special_signal_omits_empty_coming_up_section():
    """The dashboard does not render the Coming Up heading when upcoming is empty."""
    calls = []
    with patch.object(dashboard.st, "markdown", side_effect=lambda text, **kwargs: calls.append(text)), \
         patch.object(dashboard.st, "info", side_effect=lambda text: calls.append(text)):
        dashboard.render_special_signal({"events": [], "has_events": False, "all_sources_failed": False, "upcoming": []})

    assert not any("Coming Up" in call for call in calls)
    assert any("No unusual sky signals" in call for call in calls)
    print("✓ Empty Coming Up list does not render a Coming Up section")


if __name__ == "__main__":
    print("Running Special Signal tests...\n")
    test_selected_date_is_passed_to_neo_fetch()
    test_successful_api_parsing()
    test_ranking_chooses_most_notable_events()
    test_ranking_caps_output_at_three()
    test_signal_tiers_are_assigned_deterministically()
    test_empty_data_produces_clean_empty_state()
    test_below_threshold_events_are_excluded()
    test_api_failure_degrades_gracefully()
    test_alternate_date_does_not_use_current_date()
    test_dashboard_renders_special_signal_failure_gracefully()
    test_parse_neo_handles_missing_close_approach_data()
    test_conjunction_signal_tier_thresholds()
    test_conjunction_excludes_wide_separations()
    test_conjunction_major_tier_end_to_end()
    test_conjunction_below_horizon_excluded()
    test_conjunction_event_time_within_window()
    test_conjunction_respects_target_date()
    test_merge_combines_conjunctions_and_neos()
    test_observable_conjunction_outranks_weaker_neo()
    test_one_special_signal_source_failing_does_not_suppress_other()
    test_locally_relevant_solar_eclipse_is_surfaced()
    test_eclipse_elsewhere_is_excluded()
    test_lunar_eclipse_target_date_and_tier_are_respected()
    test_notable_comet_is_surfaced()
    test_weak_or_low_comet_is_excluded_and_visibility_not_fabricated()
    test_high_altitude_iss_pass_is_surfaced_and_local_time_is_used()
    test_near_date_iss_pass_still_works()
    test_low_altitude_iss_pass_is_excluded()
    test_iss_selected_location_and_target_date_affect_relevance()
    test_far_future_iss_date_returns_no_events_without_error()
    test_far_past_iss_date_returns_no_events_without_error()
    test_all_special_signal_types_merge_and_cap()
    test_empty_successful_sources_produce_clean_empty_state()
    test_total_special_signal_failure_is_reported_gracefully()
    test_next_notable_neo_finds_first_qualifying_future_date()
    test_next_notable_neo_respects_horizon_and_api_failure()
    test_next_planetary_conjunction_finds_first_observable_date_and_stops()
    test_next_eclipse_finds_future_local_event_with_conservative_wording()
    test_next_comet_finds_future_window_and_preserves_approximation_caveat()
    test_next_iss_pass_uses_only_valid_tle_window()
    test_upcoming_candidates_sort_chronologically_and_cap_at_two()
    test_upcoming_signal_strength_breaks_same_date_ties_and_selected_date_is_excluded()
    test_get_special_signal_limits_upcoming_by_primary_count()
    test_render_special_signal_omits_empty_coming_up_section()
    print("\n✓ All tests passed!")
