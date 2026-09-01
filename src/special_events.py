"""Special Signal module: notable sky events.

Phase 3A covers NASA's public Near-Earth Object Web Service (NeoWs) feed.
Phase 3B adds observable planetary conjunctions (close apparent pairings
between bright planets), computed with Skyfield using the same
observing-window astronomy already used elsewhere in Night Signal. Phase
3C adds locally relevant eclipses, curated notable comets, and ISS passes.
This module only fetches/calculates, parses, scores, and ranks events --
dashboard presentation lives in dashboard.py.

A close NEO approach reported here is an interesting solar-system event,
not a claim that the object is visible to the naked eye or a telescope
from any particular location. Conjunctions, by contrast, are only
surfaced when both planets are actually above the horizon at the moment
of closest approach -- they are genuine sky-viewing events.
"""

import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from itertools import combinations
from zoneinfo import ZoneInfo

import numpy as np
from skyfield.api import EarthSatellite, Star, Topos, wgs84

from astronomy import (
    _get_ephemeris_and_timescale,
    _local_noon_time,
    _find_tonights_window,
    _format_local_time,
    PLANET_NAMES,
    DISPLAY_NAMES,
)


class SpecialEventsFetchError(Exception):
    """Raised when NASA's NEO API cannot provide close-approach data."""


NASA_NEO_FEED_URL = "https://api.nasa.gov/neo/rest/v1/feed"
ISS_TLE_URL = "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE"

# Ranking thresholds for _calculate_significance_score() (max ~100 points):
# - Major Signal: strongly notable (very close and/or large and/or hazardous)
# - Strong Signal: clearly notable
# - Interesting Signal: worth a mention
# Events scoring below MIN_NOTABLE_SCORE are not surfaced at all, so an
# ordinary day with only distant/tiny NEOs shows a clean empty state.
MAJOR_SIGNAL_THRESHOLD = 70
STRONG_SIGNAL_THRESHOLD = 40
MIN_NOTABLE_SCORE = 15
MAX_EVENTS = 3

# Conjunction thresholds: only pairs at least this close are surfaced.
# Deterministic and adjustable, but kept fixed once tuned:
MAJOR_CONJUNCTION_DEGREES = 0.5
STRONG_CONJUNCTION_DEGREES = 1.5
INTERESTING_CONJUNCTION_DEGREES = 3.0

# A pairing is only useful to an observer if both planets are reasonably
# clear of the horizon (not just technically "up") at closest approach.
CONJUNCTION_MIN_ALTITUDE_DEGREES = 10

# Sampling resolution across the dark observing window when scanning for
# the minimum angular separation between each planet pair.
CONJUNCTION_SAMPLE_INTERVAL_MINUTES = 10

# Curated V1 eclipse data. Solar events are deliberately bounded to broad
# local-visibility regions and are still checked against local Sun altitude;
# lunar events are checked against the Moon altitude at the local observer.
# TODO: Add major lunar occultations when a reliable, non-fragile prediction
# source is available for location-aware occultation circumstances.
CURATED_ECLIPSES = [
    {
        "name": "Total Solar Eclipse",
        "event_type": "Solar Eclipse",
        "date": "2024-04-08",
        "peak_utc": "2024-04-08T18:18:00+00:00",
        "eclipse_kind": "total",
        "visibility": "parts of Mexico, the United States, and eastern Canada",
        "lat_min": 14.0,
        "lat_max": 55.0,
        "lon_min": -115.0,
        "lon_max": -45.0,
    },
    {
        "name": "Total Solar Eclipse",
        "event_type": "Solar Eclipse",
        "date": "2026-08-12",
        "peak_utc": "2026-08-12T17:47:00+00:00",
        "eclipse_kind": "total",
        "visibility": "parts of Greenland, Iceland, and Spain",
        "lat_min": 35.0,
        "lat_max": 82.0,
        "lon_min": -75.0,
        "lon_max": 20.0,
    },
    {
        "name": "Total Solar Eclipse",
        "event_type": "Solar Eclipse",
        "date": "2027-08-02",
        "peak_utc": "2027-08-02T10:07:00+00:00",
        "eclipse_kind": "total",
        "visibility": "parts of North Africa and the Middle East",
        "lat_min": 5.0,
        "lat_max": 45.0,
        "lon_min": -20.0,
        "lon_max": 65.0,
    },
    {
        "name": "Total Lunar Eclipse",
        "event_type": "Lunar Eclipse",
        "date": "2025-03-14",
        "peak_utc": "2025-03-14T06:58:00+00:00",
        "eclipse_kind": "total",
    },
    {
        "name": "Total Lunar Eclipse",
        "event_type": "Lunar Eclipse",
        "date": "2025-09-07",
        "peak_utc": "2025-09-07T18:11:00+00:00",
        "eclipse_kind": "total",
    },
    {
        "name": "Total Lunar Eclipse",
        "event_type": "Lunar Eclipse",
        "date": "2026-03-03",
        "peak_utc": "2026-03-03T11:33:00+00:00",
        "eclipse_kind": "total",
    },
    {
        "name": "Partial Lunar Eclipse",
        "event_type": "Lunar Eclipse",
        "date": "2026-08-28",
        "peak_utc": "2026-08-28T04:13:00+00:00",
        "eclipse_kind": "partial",
    },
]

# A deliberately tiny, curated comet list. Coordinates are coarse but enough
# for V1 altitude checks; we avoid scraping and avoid claiming naked-eye
# visibility unless the curated magnitude supports it.
CURATED_COMETS = [
    {
        "name": "C/2023 A3 (Tsuchinshan-ATLAS)",
        "active_start": "2024-09-20",
        "active_end": "2024-10-31",
        "peak_date": "2024-10-12",
        "magnitude": 2.5,
        "ra_hours": 14.0,
        "dec_degrees": -5.0,
        "note": "a unusually bright comet near its best evening apparition",
    },
    {
        "name": "12P/Pons-Brooks",
        "active_start": "2024-03-01",
        "active_end": "2024-04-30",
        "peak_date": "2024-04-21",
        "magnitude": 4.5,
        "ra_hours": 2.1,
        "dec_degrees": 25.0,
        "note": "a notable periodic comet around perihelion, best with binoculars or a small telescope",
    },
]

COMET_MIN_ALTITUDE_DEGREES = 20
COMET_SAMPLE_INTERVAL_MINUTES = 20
ISS_MIN_ALTITUDE_DEGREES = 20
ISS_MAJOR_ALTITUDE_DEGREES = 70
ISS_STRONG_ALTITUDE_DEGREES = 40
ISS_TLE_VALIDITY_DAYS = 3

_MONTH_ABBREVIATIONS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]


def _get_api_key():
    """Read the NASA API key from the environment.

    Falls back to NASA's public DEMO_KEY, which works without any
    registration (but is more tightly rate-limited).
    """
    return os.environ.get("NASA_API_KEY", "DEMO_KEY")


def _fetch_neo_feed(target_date):
    """Fetch NASA's Near-Earth Object feed for a single calendar date.

    Args:
        target_date (date): Calendar date to query.

    Returns:
        list: Raw NEO dicts from NASA's NeoWs API for that date (may be
        empty if nothing approached that day).

    Raises:
        SpecialEventsFetchError: If the request fails after retries or
        the response is malformed.
    """
    try:
        date_str = target_date.isoformat()
        params = {
            "start_date": date_str,
            "end_date": date_str,
            "api_key": _get_api_key()
        }
        param_string = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{NASA_NEO_FEED_URL}?{param_string}"

        for attempt in range(2):
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())
                break
            except (TimeoutError, urllib.error.URLError) as error:
                if attempt == 1:
                    raise SpecialEventsFetchError(
                        f"Failed to fetch NEO feed after 2 attempts: {error}"
                    ) from error
                time.sleep(1)

        near_earth_objects = data.get("near_earth_objects", {})
        return near_earth_objects.get(date_str, [])

    except SpecialEventsFetchError:
        raise
    except urllib.error.URLError as e:
        raise SpecialEventsFetchError(f"Failed to fetch NEO feed: Network error - {e}")
    except json.JSONDecodeError as e:
        raise SpecialEventsFetchError(f"Failed to parse NEO feed: Invalid JSON - {e}")
    except (KeyError, ValueError) as e:
        raise SpecialEventsFetchError(f"Failed to parse NEO feed: {e}")


def _fetch_neo_feed_range(start_date, end_date):
    """Fetch NASA's Near-Earth Object feed for a short date range."""
    try:
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "api_key": _get_api_key()
        }
        param_string = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{NASA_NEO_FEED_URL}?{param_string}"

        for attempt in range(2):
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())
                break
            except (TimeoutError, urllib.error.URLError) as error:
                if attempt == 1:
                    raise SpecialEventsFetchError(
                        f"Failed to fetch NEO feed range after 2 attempts: {error}"
                    ) from error
                time.sleep(1)

        return data.get("near_earth_objects", {})

    except SpecialEventsFetchError:
        raise
    except urllib.error.URLError as e:
        raise SpecialEventsFetchError(f"Failed to fetch NEO feed range: Network error - {e}")
    except json.JSONDecodeError as e:
        raise SpecialEventsFetchError(f"Failed to parse NEO feed range: Invalid JSON - {e}")
    except (KeyError, ValueError) as e:
        raise SpecialEventsFetchError(f"Failed to parse NEO feed range: {e}")


def _parse_neo(raw_neo):
    """Extract the fields Special Signal needs from a raw NeoWs entry.

    NeoWs returns all numeric fields as JSON strings, so this converts
    them to floats where present.

    Returns:
        dict or None: Parsed fields, or None if the entry has no
        close-approach data to rank/display.
    """
    approaches = raw_neo.get("close_approach_data", [])
    if not approaches:
        return None
    approach = approaches[0]

    miss_distance = approach.get("miss_distance", {})
    miss_distance_lunar = float(miss_distance["lunar"]) if miss_distance.get("lunar") else None
    miss_distance_miles = float(miss_distance["miles"]) if miss_distance.get("miles") else None

    velocity = approach.get("relative_velocity", {})
    velocity_mph = float(velocity["miles_per_hour"]) if velocity.get("miles_per_hour") else None

    diameter_ft = raw_neo.get("estimated_diameter", {}).get("feet", {})
    diameter_min_ft = diameter_ft.get("estimated_diameter_min")
    diameter_max_ft = diameter_ft.get("estimated_diameter_max")

    diameter_km = raw_neo.get("estimated_diameter", {}).get("kilometers", {})
    diameter_meters_avg = None
    if diameter_km.get("estimated_diameter_min") is not None and diameter_km.get("estimated_diameter_max") is not None:
        diameter_meters_avg = (diameter_km["estimated_diameter_min"] + diameter_km["estimated_diameter_max"]) / 2 * 1000

    return {
        "name": raw_neo.get("name", "Unknown object"),
        "is_potentially_hazardous": bool(raw_neo.get("is_potentially_hazardous_asteroid", False)),
        "absolute_magnitude": raw_neo.get("absolute_magnitude_h"),
        "close_approach_date_full": approach.get("close_approach_date_full"),
        "miss_distance_lunar": miss_distance_lunar,
        "miss_distance_miles": miss_distance_miles,
        "velocity_mph": velocity_mph,
        "diameter_min_ft": diameter_min_ft,
        "diameter_max_ft": diameter_max_ft,
        "diameter_meters_avg": diameter_meters_avg
    }


def _distance_score(miss_distance_lunar):
    """Closer approaches score higher (max 40 points).

    Full points within 1 lunar distance (the Earth-Moon distance),
    scaling linearly down to zero at 30 lunar distances.
    """
    if miss_distance_lunar is None:
        return 0
    if miss_distance_lunar <= 1:
        return 40
    if miss_distance_lunar >= 30:
        return 0
    return 40 * (30 - miss_distance_lunar) / 29


def _size_score(diameter_meters_avg):
    """Larger objects score higher (max 30 points).

    Thresholds reference NASA's ~140m potentially-hazardous-size cutoff
    and a 1km "large" cutoff.
    """
    if diameter_meters_avg is None:
        return 0
    if diameter_meters_avg >= 1000:
        return 30
    if diameter_meters_avg >= 140:
        return 15
    if diameter_meters_avg >= 30:
        return 5
    return 0


def _hazard_score(is_potentially_hazardous):
    """NASA's own hazard designation adds a flat bonus (max 30 points)."""
    return 30 if is_potentially_hazardous else 0


def _calculate_significance_score(parsed):
    """Deterministic 0-100 significance score combining distance, size,
    and NASA's potentially-hazardous designation."""
    return (
        _distance_score(parsed["miss_distance_lunar"])
        + _size_score(parsed["diameter_meters_avg"])
        + _hazard_score(parsed["is_potentially_hazardous"])
    )


def _classify_signal_level(score):
    """Map a significance score to a display tier."""
    if score >= MAJOR_SIGNAL_THRESHOLD:
        return "Major Signal"
    if score >= STRONG_SIGNAL_THRESHOLD:
        return "Strong Signal"
    return "Interesting Signal"


def _format_month_day(target_date):
    """Format a date as a short display string, e.g. 'Oct 21'."""
    return f"{_MONTH_ABBREVIATIONS[target_date.month - 1]} {target_date.day}"


def _build_summary(parsed, target_date):
    """Build a concise, non-misleading 'why this matters' sentence.

    Deliberately avoids implying the object is visible to the naked eye
    or a telescope -- a close approach is an interesting solar-system
    event, not a guaranteed visual target.
    """
    when = "tonight" if target_date is None else f"on {_format_month_day(target_date)}"
    distance_note = (
        f"about {parsed['miss_distance_lunar']:.1f}x the Moon's distance away"
        if parsed["miss_distance_lunar"] is not None
        else "at a notable distance"
    )
    hazard_note = " and is flagged potentially hazardous by NASA" if parsed["is_potentially_hazardous"] else ""
    return (
        f"A notable close approach {when}, passing {distance_note}{hazard_note}. "
        "This is an interesting solar-system event, not a confirmed naked-eye or telescope target."
    )


def _normalize_event(parsed, score, target_date):
    """Build the normalized Special Signal event shape for the dashboard."""
    return {
        "name": parsed["name"],
        "event_type": "Near-Earth Object",
        "signal_level": _classify_signal_level(score),
        "event_time": parsed["close_approach_date_full"],
        "summary": _build_summary(parsed, target_date),
        "details": {
            "miss_distance_miles": parsed["miss_distance_miles"],
            "miss_distance_lunar": parsed["miss_distance_lunar"],
            "velocity_mph": parsed["velocity_mph"],
            "diameter_min_ft": parsed["diameter_min_ft"],
            "diameter_max_ft": parsed["diameter_max_ft"],
            "is_potentially_hazardous": parsed["is_potentially_hazardous"],
            "absolute_magnitude": parsed["absolute_magnitude"]
        }
    }


def _get_ranked_neo_events(location, target_date):
    """Fetch and rank notable NEO close approaches for the selected date.

    Args:
        location (Location): Observer location. Only used to resolve
            "today" in the observer's own timezone when target_date is
            not given.
        target_date (date, optional): Selected observing date.

    Returns:
        list: Up to MAX_EVENTS normalized NEO event dicts, most notable
        first.

    Raises:
        SpecialEventsFetchError: If the NASA API request fails after
        retries or the response is malformed.
    """
    query_date = target_date if target_date is not None else datetime.now(ZoneInfo(location.timezone)).date()

    raw_neos = _fetch_neo_feed(query_date)

    return _rank_raw_neos(raw_neos, target_date)


def _rank_raw_neos(raw_neos, target_date):
    """Parse, score, filter, and normalize raw NEO entries."""
    scored = []
    for raw_neo in raw_neos:
        parsed = _parse_neo(raw_neo)
        if parsed is None:
            continue
        score = _calculate_significance_score(parsed)
        if score < MIN_NOTABLE_SCORE:
            continue
        scored.append((score, parsed))

    scored.sort(key=lambda item: item[0], reverse=True)
    top = scored[:MAX_EVENTS]

    return [_normalize_event(parsed, score, target_date) for score, parsed in top]


def _classify_conjunction_signal_level(separation_degrees):
    """Map an angular separation (degrees) to a display tier.

    Deterministic thresholds:
    - <= 0.5 deg: Major Signal
    - <= 1.5 deg: Strong Signal
    - <= 3.0 deg: Interesting Signal
    - >  3.0 deg: not notable enough to surface (returns None)
    """
    if separation_degrees <= MAJOR_CONJUNCTION_DEGREES:
        return "Major Signal"
    if separation_degrees <= STRONG_CONJUNCTION_DEGREES:
        return "Strong Signal"
    if separation_degrees <= INTERESTING_CONJUNCTION_DEGREES:
        return "Interesting Signal"
    return None


def _moon_width_note(separation_degrees):
    """A brief, understandable comparison for a separation distance."""
    if separation_degrees <= 0.6:
        return " (about the width of the full Moon)"
    if separation_degrees <= 1.2:
        return " (about two Moon-widths)"
    return ""


def _build_conjunction_summary(name_a, name_b, separation_degrees):
    """Build the 'why this matters' sentence for a conjunction card."""
    moon_note = _moon_width_note(separation_degrees)
    return (
        f"{name_a} and {name_b} pass just {separation_degrees:.1f}\u00b0 apart "
        f"during the dark observing window{moon_note}."
    )


def get_planetary_conjunctions(location, target_date=None):
    """Find observable close pairings between bright planets tonight (or
    on the selected observing date).

    Reuses Night Signal's existing dark-window astronomy helpers rather
    than duplicating date/window logic. Samples every pair of Mercury,
    Venus, Mars, Jupiter, and Saturn's apparent angular separation across
    the dark observing window at CONJUNCTION_SAMPLE_INTERVAL_MINUTES
    resolution, and surfaces only pairs whose minimum separation is
    notable (see _classify_conjunction_signal_level) AND both planets are
    at least CONJUNCTION_MIN_ALTITUDE_DEGREES above the horizon at that
    moment -- a pairing below the horizon is never reported.

    Args:
        location (Location): Observer location.
        target_date (date, optional): Selected observing date. Defaults
            to None, meaning tonight (the current-moment-based window).

    Returns:
        list: Normalized conjunction event dicts, sorted by signal tier
        then by closest separation, most notable first. Empty if the
        observing window couldn't be determined or nothing qualifies.
    """
    ephemeris, ts = _get_ephemeris_and_timescale()
    earth = ephemeris["earth"]
    observer_topos = Topos(latitude_degrees=location.latitude, longitude_degrees=location.longitude)
    observer = earth + observer_topos
    timezone = ZoneInfo(location.timezone)

    reference_time = _local_noon_time(ts, target_date, timezone) if target_date is not None else None
    _, window_start, window_end = _find_tonights_window(ephemeris, ts, observer_topos, reference_time)

    if window_start is None or window_end is None:
        return []

    window_hours = (window_end.tt - window_start.tt) * 24
    sample_count = max(2, int((window_hours * 60) / CONJUNCTION_SAMPLE_INTERVAL_MINUTES) + 1)
    sample_tt = np.linspace(window_start.tt, window_end.tt, sample_count)
    sample_times = ts.tt_jd(sample_tt)

    apparent_positions = {
        planet_id: observer.at(sample_times).observe(ephemeris[planet_id]).apparent()
        for planet_id in PLANET_NAMES
    }

    events = []
    for planet_a_id, planet_b_id in combinations(PLANET_NAMES, 2):
        apparent_a = apparent_positions[planet_a_id]
        apparent_b = apparent_positions[planet_b_id]

        separations = apparent_a.separation_from(apparent_b).degrees
        min_index = int(np.argmin(separations))
        min_separation = float(separations[min_index])

        signal_level = _classify_conjunction_signal_level(min_separation)
        if signal_level is None:
            continue

        altitude_a = float(apparent_a.altaz()[0].degrees[min_index])
        altitude_b = float(apparent_b.altaz()[0].degrees[min_index])

        if altitude_a < CONJUNCTION_MIN_ALTITUDE_DEGREES or altitude_b < CONJUNCTION_MIN_ALTITUDE_DEGREES:
            continue

        name_a = DISPLAY_NAMES[planet_a_id]
        name_b = DISPLAY_NAMES[planet_b_id]
        approximate_altitude = round((altitude_a + altitude_b) / 2, 1)
        separation_rounded = round(min_separation, 1)
        best_viewing_time = _format_local_time(sample_times[min_index], timezone)

        events.append({
            "name": f"{name_a} & {name_b}",
            "event_type": "Planetary Conjunction",
            "signal_level": signal_level,
            "event_time": best_viewing_time,
            "angular_separation_degrees": separation_rounded,
            "altitude_degrees": approximate_altitude,
            "summary": _build_conjunction_summary(name_a, name_b, min_separation),
            "details": {
                "planet_a": name_a,
                "planet_b": name_b,
                "best_viewing_time": best_viewing_time,
                "approximate_altitude_degrees": approximate_altitude,
                "angular_separation_degrees": separation_rounded
            }
        })

    tier_rank = {"Major Signal": 0, "Strong Signal": 1, "Interesting Signal": 2}
    events.sort(key=lambda event: (tier_rank[event["signal_level"]], event["angular_separation_degrees"]))

    return events


def _resolve_observing_date(location, target_date):
    """Resolve Tonight mode to the observer's local date."""
    return target_date if target_date is not None else datetime.now(ZoneInfo(location.timezone)).date()


def _parse_utc_datetime(value):
    """Parse an ISO timestamp into a timezone-aware UTC datetime."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_datetime_local(dt, timezone_name):
    """Format a timezone-aware datetime as a local time label."""
    return dt.astimezone(ZoneInfo(timezone_name)).strftime("%I:%M %p %Z").lstrip("0")


def _event_matches_observing_date(event_dt_utc, location, query_date):
    """True when a timestamp belongs to the selected observing session.

    Daytime sources (solar eclipses) can match by local calendar date;
    nighttime sources can also match when they fall inside the selected
    dark observing window, including after local midnight.
    """
    local_dt = event_dt_utc.astimezone(ZoneInfo(location.timezone))
    if local_dt.date() == query_date:
        return True

    try:
        window = _get_observing_window_datetimes(location, query_date)
    except Exception:
        return False
    if window is None:
        return False
    window_start, window_end = window
    return window_start <= event_dt_utc <= window_end


def _get_observing_window_datetimes(location, target_date):
    """Return the selected dark-window bounds as UTC datetimes."""
    ephemeris, ts = _get_ephemeris_and_timescale()
    observer_topos = Topos(latitude_degrees=location.latitude, longitude_degrees=location.longitude)
    timezone_info = ZoneInfo(location.timezone)
    reference_time = _local_noon_time(ts, target_date, timezone_info) if target_date is not None else None
    _, window_start, window_end = _find_tonights_window(ephemeris, ts, observer_topos, reference_time)

    if window_start is None or window_end is None:
        return None
    return window_start.utc_datetime(), window_end.utc_datetime()


def _altitude_degrees_for_body(location, body_name, event_dt_utc):
    """Calculate a solar-system body's altitude at a UTC datetime."""
    ephemeris, ts = _get_ephemeris_and_timescale()
    observer = ephemeris["earth"] + Topos(latitude_degrees=location.latitude, longitude_degrees=location.longitude)
    t = ts.from_datetime(event_dt_utc)
    apparent = observer.at(t).observe(ephemeris[body_name]).apparent()
    altitude, _, _ = apparent.altaz()
    return float(altitude.degrees)


def _location_in_event_bounds(location, event):
    """Check a curated event's broad latitude/longitude relevance bounds."""
    return (
        event["lat_min"] <= location.latitude <= event["lat_max"]
        and event["lon_min"] <= location.longitude <= event["lon_max"]
    )


def _classify_eclipse_signal_level(event):
    """Classify a locally relevant eclipse."""
    eclipse_kind = event.get("eclipse_kind")
    if event["event_type"] == "Solar Eclipse" and eclipse_kind in {"total", "annular"}:
        return "Major Signal"
    if event["event_type"] == "Lunar Eclipse" and eclipse_kind == "total":
        return "Major Signal"
    return "Strong Signal"


def _normalize_eclipse_event(event, location, event_dt_utc, altitude_degrees=None):
    """Build the normalized Special Signal event shape for an eclipse."""
    signal_level = _classify_eclipse_signal_level(event)
    local_time = _format_datetime_local(event_dt_utc, location.timezone)
    eclipse_kind = event.get("eclipse_kind", "eclipse")

    if event["event_type"] == "Solar Eclipse":
        summary = (
            "This solar eclipse is relevant to your region and the Sun is above "
            f"the horizon near peak ({local_time}). Exact local eclipse magnitude "
            "or totality is not calculated in this V1 dataset."
        )
    else:
        summary = (
            f"A {eclipse_kind} lunar eclipse is observable from this location "
            f"near {local_time}."
        )

    return {
        "name": event["name"],
        "event_type": event["event_type"],
        "signal_level": signal_level,
        "event_time": local_time,
        "summary": summary,
        "details": {
            "eclipse_kind": eclipse_kind,
            "global_eclipse_kind": eclipse_kind,
            "local_circumstances_precision": "broad-region V1 estimate",
            "event_time": local_time,
            "peak_utc": event_dt_utc.isoformat(),
            "visibility": event.get("visibility"),
            "altitude_degrees": round(altitude_degrees, 1) if altitude_degrees is not None else None,
        }
    }


def get_eclipse_events(location, target_date=None):
    """Find locally relevant curated solar/lunar eclipse events.

    This V1 intentionally uses a small curated eclipse set rather than a
    fragile scraper. Solar eclipses must match broad local visibility
    bounds and have the Sun above the local horizon; lunar eclipses must
    have the Moon above the local horizon and match the selected
    observing session. Lunar occultations remain a documented TODO until
    a reliable location-aware source is added.
    """
    query_date = _resolve_observing_date(location, target_date)
    events = []

    for eclipse in CURATED_ECLIPSES:
        event_dt_utc = _parse_utc_datetime(eclipse["peak_utc"])
        if not _event_matches_observing_date(event_dt_utc, location, query_date):
            continue

        if eclipse["event_type"] == "Solar Eclipse":
            if not _location_in_event_bounds(location, eclipse):
                continue
            altitude_degrees = _altitude_degrees_for_body(location, "sun", event_dt_utc)
            if altitude_degrees <= 0:
                continue
        else:
            altitude_degrees = _altitude_degrees_for_body(location, "moon", event_dt_utc)
            if altitude_degrees <= 0:
                continue

        events.append(_normalize_eclipse_event(eclipse, location, event_dt_utc, altitude_degrees))

    tier_rank = {"Major Signal": 0, "Strong Signal": 1, "Interesting Signal": 2}
    events.sort(key=lambda event: (tier_rank[event["signal_level"]], event["event_time"]))
    return events


def _classify_comet_signal_level(magnitude):
    """Map curated comet magnitude to a Special Signal tier."""
    if magnitude is None:
        return None
    if magnitude <= 2:
        return "Major Signal"
    if magnitude <= 6:
        return "Strong Signal"
    if magnitude <= 10:
        return "Interesting Signal"
    return None


def _sample_body_altitude_over_window(location, target_date, body):
    """Return best local time and altitude for a fixed sky position."""
    window = _get_observing_window_datetimes(location, target_date)
    if window is None:
        return None
    window_start, window_end = window
    ephemeris, ts = _get_ephemeris_and_timescale()
    observer = ephemeris["earth"] + Topos(latitude_degrees=location.latitude, longitude_degrees=location.longitude)

    window_hours = (window_end - window_start).total_seconds() / 3600
    sample_count = max(2, int((window_hours * 60) / COMET_SAMPLE_INTERVAL_MINUTES) + 1)
    start_tt = ts.from_datetime(window_start).tt
    end_tt = ts.from_datetime(window_end).tt
    sample_times = ts.tt_jd(np.linspace(start_tt, end_tt, sample_count))

    apparent = observer.at(sample_times).observe(body).apparent()
    altitude, _, _ = apparent.altaz()
    altitude_degrees = altitude.degrees
    best_index = int(np.argmax(altitude_degrees))
    best_altitude = float(altitude_degrees[best_index])

    return _format_local_time(sample_times[best_index], ZoneInfo(location.timezone)), best_altitude


def _normalize_comet_event(comet, best_time, best_altitude, target_date):
    """Build the normalized Special Signal event shape for a curated comet."""
    magnitude = comet.get("magnitude")
    signal_level = _classify_comet_signal_level(magnitude)
    magnitude_text = f"estimated magnitude {magnitude:.1f}" if magnitude is not None else "brightness not well constrained"
    when = "tonight" if target_date is None else f"on {_format_month_day(target_date)}"

    if magnitude is not None and magnitude <= 6:
        visibility_note = "potentially accessible with binoculars or a small telescope under good conditions"
    else:
        visibility_note = "a challenging telescope target, not a claimed naked-eye sight"

    return {
        "name": comet["name"],
        "event_type": "Comet",
        "signal_level": signal_level,
        "event_time": best_time,
        "summary": (
            f"{comet['name']} is {comet['note']} {when}; {magnitude_text}, "
            f"{visibility_note}. Viewing time and altitude are approximate "
            "because this V1 comet source uses curated fixed coordinates, not a precise ephemeris."
        ),
        "details": {
            "best_viewing_time": best_time,
            "approximate_altitude_degrees": round(best_altitude, 1),
            "magnitude": magnitude,
            "peak_date": comet.get("peak_date"),
            "visibility_note": visibility_note,
            "position_precision": "curated approximate fixed coordinates",
        }
    }


def get_comet_events(location, target_date=None):
    """Surface a small curated set of notable, plausibly observable comets."""
    query_date = _resolve_observing_date(location, target_date)
    events = []

    for comet in CURATED_COMETS:
        active_start = datetime.fromisoformat(comet["active_start"]).date()
        active_end = datetime.fromisoformat(comet["active_end"]).date()
        if not (active_start <= query_date <= active_end):
            continue

        signal_level = _classify_comet_signal_level(comet.get("magnitude"))
        if signal_level is None:
            continue

        body = Star(ra_hours=comet["ra_hours"], dec_degrees=comet["dec_degrees"])
        best = _sample_body_altitude_over_window(location, target_date, body)
        if best is None:
            continue
        best_time, best_altitude = best
        if best_altitude < COMET_MIN_ALTITUDE_DEGREES:
            continue

        events.append(_normalize_comet_event(comet, best_time, best_altitude, target_date))

    tier_rank = {"Major Signal": 0, "Strong Signal": 1, "Interesting Signal": 2}
    events.sort(key=lambda event: (tier_rank[event["signal_level"]], event["details"].get("magnitude", 99)))
    return events


def _fetch_iss_tle():
    """Fetch the current ISS TLE from CelesTrak."""
    try:
        with urllib.request.urlopen(ISS_TLE_URL, timeout=5) as response:
            lines = response.read().decode().strip().splitlines()
    except (TimeoutError, urllib.error.URLError) as error:
        raise SpecialEventsFetchError(f"Failed to fetch ISS TLE: {error}") from error

    if len(lines) < 3:
        raise SpecialEventsFetchError("Failed to parse ISS TLE: response did not contain three lines")

    return lines[0].strip(), lines[1].strip(), lines[2].strip()


def _classify_iss_signal_level(max_altitude_degrees):
    """Map an ISS pass altitude to a Special Signal tier."""
    if max_altitude_degrees >= ISS_MAJOR_ALTITUDE_DEGREES:
        return "Major Signal"
    if max_altitude_degrees >= ISS_STRONG_ALTITUDE_DEGREES:
        return "Strong Signal"
    if max_altitude_degrees >= ISS_MIN_ALTITUDE_DEGREES:
        return "Interesting Signal"
    return None


def _is_within_iss_tle_validity(query_date, center_date):
    """True when the observing date is close enough for current-TLE ISS predictions."""
    return abs((query_date - center_date).days) <= ISS_TLE_VALIDITY_DAYS


def _iss_tle_epoch_date(satellite, location):
    """Resolve a Skyfield satellite TLE epoch into the observer's local date."""
    epoch = getattr(satellite, "epoch", None)
    if epoch is None:
        return None
    return epoch.utc_datetime().astimezone(ZoneInfo(location.timezone)).date()


def _normalize_iss_event(start_time, peak_time, end_time, max_altitude_degrees, location):
    """Build the normalized Special Signal event shape for an ISS pass."""
    start_dt = start_time.utc_datetime().astimezone(ZoneInfo(location.timezone))
    peak_dt = peak_time.utc_datetime().astimezone(ZoneInfo(location.timezone))
    end_dt = end_time.utc_datetime().astimezone(ZoneInfo(location.timezone))
    duration_minutes = max(1, round((end_dt - start_dt).total_seconds() / 60))
    best_time = peak_dt.strftime("%I:%M %p %Z").lstrip("0")
    signal_level = _classify_iss_signal_level(max_altitude_degrees)

    return {
        "name": "ISS Pass",
        "event_type": "ISS Pass",
        "signal_level": signal_level,
        "event_time": best_time,
        "summary": (
            f"The International Space Station makes a locally visible pass, "
            f"peaking near {max_altitude_degrees:.0f}\u00b0 above the horizon."
        ),
        "details": {
            "start_time": start_dt.strftime("%I:%M %p %Z").lstrip("0"),
            "best_viewing_time": best_time,
            "end_time": end_dt.strftime("%I:%M %p %Z").lstrip("0"),
            "max_altitude_degrees": round(max_altitude_degrees, 1),
            "duration_minutes": duration_minutes,
        }
    }


def get_iss_passes(location, target_date=None):
    """Find useful ISS passes during the selected dark observing window.

    Uses current ISS TLE data from CelesTrak and Skyfield's event finder.
    A pass only counts if it occurs inside the observing window, reaches
    at least ISS_MIN_ALTITUDE_DEGREES, and Skyfield can establish that
    the station is sunlit at peak (so it is actually visible).
    """
    query_date = _resolve_observing_date(location, target_date)
    local_current_date = datetime.now(ZoneInfo(location.timezone)).date()
    if not _is_within_iss_tle_validity(query_date, local_current_date):
        return []

    window = _get_observing_window_datetimes(location, target_date)
    if window is None:
        return []

    ephemeris, ts = _get_ephemeris_and_timescale()
    observer = wgs84.latlon(location.latitude, location.longitude)
    tle_name, line1, line2 = _fetch_iss_tle()
    satellite = EarthSatellite(line1, line2, tle_name, ts)
    tle_epoch_date = _iss_tle_epoch_date(satellite, location)
    if tle_epoch_date is not None and not _is_within_iss_tle_validity(query_date, tle_epoch_date):
        return []

    t0 = ts.from_datetime(window[0])
    t1 = ts.from_datetime(window[1])
    times, event_codes = satellite.find_events(observer, t0, t1, altitude_degrees=ISS_MIN_ALTITUDE_DEGREES)

    events = []
    current_start = None
    current_peak = None
    for event_time, event_code in zip(times, event_codes):
        if event_code == 0:
            current_start = event_time
            current_peak = None
        elif event_code == 1 and current_start is not None:
            current_peak = event_time
        elif event_code == 2 and current_start is not None and current_peak is not None:
            peak_altitude, _, _ = (satellite - observer).at(current_peak).altaz()
            max_altitude = float(peak_altitude.degrees)
            signal_level = _classify_iss_signal_level(max_altitude)
            is_sunlit = bool(satellite.at(current_peak).is_sunlit(ephemeris))
            if signal_level is not None and is_sunlit:
                events.append(_normalize_iss_event(current_start, current_peak, event_time, max_altitude, location))
            current_start = None
            current_peak = None

    tier_rank = {"Major Signal": 0, "Strong Signal": 1, "Interesting Signal": 2}
    events.sort(key=lambda event: (tier_rank[event["signal_level"]], -event["details"]["max_altitude_degrees"]))
    return events


def _source_events_or_failure(source, location, target_date):
    """Return (events, failed) for an isolated Special Signal source."""
    try:
        return source(location, target_date), False
    except Exception:
        return [], True


def _special_event_priority(event):
    """Deterministic unified ranking for all Special Signal sources.

    Ranking favors rare and locally observable events over informational
    NEO close approaches, so NEOs cannot crowd out visible sky events.
    """
    event_type = event["event_type"]
    signal_level = event["signal_level"]
    eclipse_kind = event.get("details", {}).get("eclipse_kind")

    if event_type == "Solar Eclipse" and signal_level == "Major Signal":
        return 0
    if event_type == "Lunar Eclipse" and eclipse_kind == "total":
        return 1
    if event_type == "Comet" and signal_level == "Major Signal":
        return 2
    if event_type == "Planetary Conjunction" and signal_level == "Major Signal":
        return 3
    if event_type == "ISS Pass" and signal_level == "Major Signal":
        return 4
    if event_type == "Planetary Conjunction" and signal_level == "Strong Signal":
        return 5
    if event_type in {"Solar Eclipse", "Lunar Eclipse", "Lunar Occultation"}:
        return 6
    if event_type == "Comet" and signal_level == "Strong Signal":
        return 7
    if event_type == "Near-Earth Object" and signal_level == "Major Signal":
        return 8
    if event_type == "Planetary Conjunction" and signal_level == "Interesting Signal":
        return 9
    if event_type == "ISS Pass":
        return 10
    if event_type == "Comet":
        return 11
    if event_type == "Near-Earth Object":
        return 12
    return 99


def _upcoming_start_date(location, target_date):
    """Return the first date eligible for Coming Up fallbacks."""
    return _resolve_observing_date(location, target_date) + timedelta(days=1)


def _signal_strength_rank(signal_level):
    """Sort stronger signals first when upcoming events share a date."""
    return {"Major Signal": 0, "Strong Signal": 1, "Interesting Signal": 2}.get(signal_level, 9)


def _observability_rank(event_type):
    """Prefer directly observable events over informational ones as a tie-breaker."""
    if event_type in {"Solar Eclipse", "Lunar Eclipse", "Lunar Occultation", "Comet", "ISS Pass", "Planetary Conjunction"}:
        return 0
    return 1


def _normalize_upcoming_event(event, event_date):
    """Build the compact normalized Coming Up event shape."""
    event_type = event["event_type"]
    display_type = "Near-Earth Object Flyby" if event_type == "Near-Earth Object" else event_type
    return {
        "name": event["name"],
        "event_type": display_type,
        "date": event_date,
        "event_time": event.get("event_time"),
        "signal_level": event["signal_level"],
        "summary": event["summary"],
        "details": event.get("details", {}),
    }


def get_next_notable_neo(location, target_date=None, max_days_ahead=30):
    """Find the next future date containing at least one notable NEO.

    Starts strictly after the selected observing date and stops on the
    first qualifying date, returning that date's highest-ranked NEO. A
    NASA/API failure returns None so Coming Up never breaks primary cards.
    """
    start_date = _upcoming_start_date(location, target_date)
    search_end = start_date + timedelta(days=max_days_ahead - 1)
    chunk_start = start_date

    while chunk_start <= search_end:
        chunk_end = min(chunk_start + timedelta(days=6), search_end)
        try:
            raw_by_date = _fetch_neo_feed_range(chunk_start, chunk_end)
        except Exception:
            return None

        candidate_date = chunk_start
        while candidate_date <= chunk_end:
            events = _rank_raw_neos(raw_by_date.get(candidate_date.isoformat(), []), candidate_date)
            if events:
                return _normalize_upcoming_event(events[0], candidate_date)
            candidate_date += timedelta(days=1)

        chunk_start = chunk_end + timedelta(days=1)
    return None


def get_next_planetary_conjunction(location, target_date=None, max_days_ahead=90):
    """Find the next future observable planetary conjunction."""
    start_date = _upcoming_start_date(location, target_date)
    for offset in range(max_days_ahead):
        candidate_date = start_date + timedelta(days=offset)
        try:
            events = get_planetary_conjunctions(location, candidate_date)
        except Exception:
            return None
        if events:
            return _normalize_upcoming_event(events[0], candidate_date)
    return None


def get_next_eclipse_event(location, target_date=None):
    """Find the next future curated eclipse relevant to this location."""
    start_date = _upcoming_start_date(location, target_date)
    candidate_dates = sorted({datetime.fromisoformat(eclipse["date"]).date() for eclipse in CURATED_ECLIPSES})

    for candidate_date in candidate_dates:
        if candidate_date < start_date:
            continue
        try:
            events = get_eclipse_events(location, candidate_date)
        except Exception:
            return None
        if events:
            return _normalize_upcoming_event(events[0], candidate_date)
    return None


def get_next_comet_event(location, target_date=None):
    """Find the next future curated comet window relevant to this location."""
    start_date = _upcoming_start_date(location, target_date)
    candidates = []

    for comet in CURATED_COMETS:
        active_start = datetime.fromisoformat(comet["active_start"]).date()
        active_end = datetime.fromisoformat(comet["active_end"]).date()
        candidate_date = max(start_date, active_start)
        while candidate_date <= active_end:
            try:
                events = get_comet_events(location, candidate_date)
            except Exception:
                return None
            matching_events = [event for event in events if event["name"] == comet["name"]]
            if matching_events:
                candidates.append(_normalize_upcoming_event(matching_events[0], candidate_date))
                break
            candidate_date += timedelta(days=1)

    candidates.sort(key=lambda event: (event["date"], _signal_strength_rank(event["signal_level"]), event["name"]))
    return candidates[0] if candidates else None


def get_next_iss_pass(location, target_date=None, max_days_ahead=ISS_TLE_VALIDITY_DAYS):
    """Find the next future ISS pass without bypassing TLE validity limits."""
    selected_date = _resolve_observing_date(location, target_date)
    local_current_date = datetime.now(ZoneInfo(location.timezone)).date()
    if not _is_within_iss_tle_validity(selected_date, local_current_date):
        return None

    start_date = _upcoming_start_date(location, target_date)
    for offset in range(max_days_ahead):
        candidate_date = start_date + timedelta(days=offset)
        try:
            events = get_iss_passes(location, candidate_date)
        except Exception:
            return None
        if events:
            return _normalize_upcoming_event(events[0], candidate_date)
    return None


def get_upcoming_special_signals(location, target_date=None, limit=2):
    """Collect the soonest Coming Up events across existing sources.

    Each source contributes at most one candidate. Chronological order is
    primary; signal strength and direct observability are tie-breakers.
    """
    source_functions = [
        get_next_notable_neo,
        get_next_planetary_conjunction,
        get_next_eclipse_event,
        get_next_comet_event,
        get_next_iss_pass,
    ]
    earliest_allowed = _upcoming_start_date(location, target_date)
    candidates = []

    for source in source_functions:
        try:
            event = source(location, target_date)
        except Exception:
            event = None
        if event is None or event["date"] < earliest_allowed:
            continue
        candidates.append(event)

    candidates.sort(key=lambda event: (
        event["date"],
        _signal_strength_rank(event["signal_level"]),
        _observability_rank(event["event_type"]),
        event["name"],
    ))
    return candidates[:limit]


def get_special_signal(location, target_date=None):
    """Determine tonight's (or the selected date's) Special Signal events.

    Combines independent sources -- eclipses, curated comets, ISS passes,
    planetary conjunctions, and NASA NEO close approaches -- each
    isolated so a failure in one never suppresses the others. Ranking is
    documented in _special_event_priority and favors rare, locally
    observable events over informational NEO close approaches.

    Args:
        location (Location): Observer location. Only used to resolve
            "today" in the observer's own timezone (never the server's)
            when target_date is not given.
        target_date (date, optional): Selected observing date. Defaults
            to None, meaning "tonight".

    Returns:
        dict: Contains "events" (list of up to MAX_EVENTS normalized
        event dicts, most notable first) and "has_events" (bool).
    """
    source_functions = [
        get_eclipse_events,
        get_comet_events,
        get_iss_passes,
        get_planetary_conjunctions,
        _get_ranked_neo_events,
    ]

    combined = []
    failures = []
    for source in source_functions:
        source_events, failed = _source_events_or_failure(source, location, target_date)
        combined.extend(source_events)
        failures.append(failed)

    combined.sort(key=lambda event: (_special_event_priority(event), event.get("event_time") or ""))
    events = combined[:MAX_EVENTS]

    if len(events) >= MAX_EVENTS:
        upcoming = []
    else:
        upcoming_limit = 1 if events else 2
        try:
            upcoming = get_upcoming_special_signals(location, target_date, limit=upcoming_limit)
        except Exception:
            upcoming = []

    return {
        "events": events,
        "has_events": len(events) > 0,
        "all_sources_failed": all(failures) and not events and not upcoming,
        "upcoming": upcoming,
    }

