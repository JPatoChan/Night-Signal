"""Astronomy module for celestial observations."""

from datetime import datetime, time as dt_time

import numpy as np
from zoneinfo import ZoneInfo
from skyfield.api import Topos, load
from skyfield import almanac


# Planet identifiers in Skyfield ephemeris
PLANET_NAMES = ["mercury barycenter", "venus barycenter", "mars barycenter", 
                "jupiter barycenter", "saturn barycenter"]

# Approximate apparent magnitudes (placeholders, not calculated from orbital position)
# These are typical values but vary with Earth-planet distance and phase angle
APPROXIMATE_MAGNITUDES = {
    "mercury barycenter": 0.0,
    "venus barycenter": -4.0,
    "mars barycenter": 0.5,
    "jupiter barycenter": -2.0,
    "saturn barycenter": 0.5
}

# Display names
DISPLAY_NAMES = {
    "mercury barycenter": "Mercury",
    "venus barycenter": "Venus",
    "mars barycenter": "Mars",
    "jupiter barycenter": "Jupiter",
    "saturn barycenter": "Saturn"
}

# Sample interval used to scan the observing window for altitude peaks
SAMPLE_INTERVAL_MINUTES = 5

# Cached ephemeris/timescale so repeated calls don't reload from disk
_ephemeris = None
_timescale = None


def _get_ephemeris_and_timescale():
    """Load (and cache) the JPL ephemeris and Skyfield timescale."""
    global _ephemeris, _timescale
    if _ephemeris is None:
        _ephemeris = load("de421.bsp")
    if _timescale is None:
        _timescale = load.timescale()
    return _ephemeris, _timescale


def _format_local_time(t, timezone):
    """Format a Skyfield Time as a local time string in the given timezone."""
    local_dt = t.utc_datetime().astimezone(timezone)
    return local_dt.strftime("%I:%M %p %Z").lstrip("0")


def _local_noon_time(ts, target_date, timezone):
    """Build a Skyfield Time for local noon on `target_date` in `timezone`.

    Noon is used as a search anchor because it's virtually never near a
    DST transition (which occur in the early morning hours in most
    zones), so it reliably falls within the correct calendar day's
    evening/morning observing session regardless of DST shifts.

    Args:
        ts: Skyfield timescale.
        target_date (date): Local calendar date to anchor to.
        timezone (ZoneInfo): Timezone the date is local to.

    Returns:
        Time: Skyfield Time for local noon on target_date.
    """
    local_noon = datetime.combine(target_date, dt_time(12, 0), tzinfo=timezone)
    return ts.from_datetime(local_noon)


def _find_tonights_window(ephemeris, ts, observer_topos, reference_time=None):
    """Find the sunset and astronomical twilight bounds for a night.

    Searches a 48-hour span centered on `reference_time` for the
    dark-of-night interval (evening astronomical twilight end -> morning
    astronomical twilight begin) whose end is still after
    `reference_time`. Sunset is also located as informational context,
    not as the start of the dark window.

    Args:
        ephemeris: Loaded JPL ephemeris.
        ts: Skyfield timescale.
        observer_topos (Topos): Observer position.
        reference_time (Time, optional): Anchor moment to search around.
            Defaults to the current moment (`ts.now()`), which selects a
            currently-in-progress or next-upcoming night. Pass a local
            noon anchor (see _local_noon_time) to instead select a
            specific calendar date's evening/morning session.

    Returns:
        tuple: (sunset_time, evening_twilight_end_time, morning_twilight_begin_time)
        as Skyfield Time objects, or (None, None, None) if not found.
    """
    if reference_time is None:
        reference_time = ts.now()

    t0 = ts.tt_jd(reference_time.tt - 1)
    t1 = ts.tt_jd(reference_time.tt + 1)

    twilight_function = almanac.dark_twilight_day(ephemeris, observer_topos)
    times, values = almanac.find_discrete(t0, t1, twilight_function)
    transitions = list(zip(times, values))

    for i, (t, v) in enumerate(transitions):
        if v != 0:
            continue
        # Find the following night -> twilight transition (morning twilight begin)
        for t2, v2 in transitions[i + 1:]:
            if v2 != 1:
                continue
            if t2.tt > reference_time.tt:
                # Locate the preceding sunset (day -> civil twilight) for context
                sunset_time = None
                for t3, v3 in reversed(transitions[:i + 1]):
                    if v3 == 3:
                        sunset_time = t3
                        break
                return sunset_time, t, t2
            break

    return None, None, None


def get_observing_window(location, target_date=None):
    """Return tonight's sunset and dark astronomical observing window.

    Args:
        location (Location): Observer location to calculate the window for.
        target_date (date, optional): Local calendar date whose evening
            observing session to calculate (e.g. Aug 12 means the night
            beginning that evening and continuing into Aug 13 morning).
            Defaults to None, which preserves the original behavior of
            using the current moment to pick a currently-in-progress or
            next-upcoming night.

    Returns:
        dict: Contains 'sunset', 'evening_twilight_end', and
        'morning_twilight_begin' as formatted local time strings, or None
        values if the window could not be determined.
    """
    ephemeris, ts = _get_ephemeris_and_timescale()
    observer_topos = Topos(latitude_degrees=location.latitude, longitude_degrees=location.longitude)
    timezone = ZoneInfo(location.timezone)
    reference_time = _local_noon_time(ts, target_date, timezone) if target_date is not None else None
    sunset_time, evening_twilight_end_time, morning_twilight_begin_time = _find_tonights_window(ephemeris, ts, observer_topos, reference_time)

    return {
        "sunset": _format_local_time(sunset_time, timezone) if sunset_time is not None else None,
        "evening_twilight_end": _format_local_time(evening_twilight_end_time, timezone) if evening_twilight_end_time is not None else None,
        "morning_twilight_begin": _format_local_time(morning_twilight_begin_time, timezone) if morning_twilight_begin_time is not None else None
    }


def get_observing_window_utc(location, target_date=None):
    """Return the dark observing window's bounds as UTC datetimes.

    Same window as get_observing_window(), but returned as
    timezone-aware UTC datetimes instead of formatted local strings, for
    use as forecast-matching anchors (e.g. representative weather
    conditions for a selected observing night).

    Args:
        location (Location): Observer location.
        target_date (date, optional): Local calendar date whose evening
            observing session to calculate. Defaults to None, which
            preserves the original current-moment-based behavior.

    Returns:
        dict: Contains 'evening_twilight_end' and 'morning_twilight_begin'
        as timezone-aware UTC datetimes, or None values if the window
        could not be determined.
    """
    ephemeris, ts = _get_ephemeris_and_timescale()
    observer_topos = Topos(latitude_degrees=location.latitude, longitude_degrees=location.longitude)
    timezone = ZoneInfo(location.timezone)
    reference_time = _local_noon_time(ts, target_date, timezone) if target_date is not None else None
    _, evening_twilight_end_time, morning_twilight_begin_time = _find_tonights_window(ephemeris, ts, observer_topos, reference_time)

    return {
        "evening_twilight_end": evening_twilight_end_time.utc_datetime() if evening_twilight_end_time is not None else None,
        "morning_twilight_begin": morning_twilight_begin_time.utc_datetime() if morning_twilight_begin_time is not None else None
    }


def get_target_list(location, target_date=None):
    """Calculate planets worth observing during tonight's full dark window.

    Uses Skyfield to find the dark astronomical observing window for
    the given observer location (evening astronomical twilight end
    through morning astronomical twilight begin), then scans that window for each
    planet's peak altitude, best viewing time, and observable duration.
    Only planets that rise above the horizon at some point during the
    window are returned.

    Apparent magnitudes are approximate placeholders and do not account for
    orbital distance or phase angle variations.

    Args:
        location (Location): Observer location to calculate targets for.
        target_date (date, optional): Local calendar date whose evening
            observing session to calculate. Defaults to None, which
            preserves the original current-moment-based behavior.

    Returns:
        list: List of dicts with name, max_altitude (degrees),
        best_viewing_time (str), observable_duration_hours (float), and
        apparent_magnitude
    """
    try:
        ephemeris, ts = _get_ephemeris_and_timescale()
        earth = ephemeris["earth"]
        observer_topos = Topos(latitude_degrees=location.latitude, longitude_degrees=location.longitude)
        observer = earth + observer_topos
        timezone = ZoneInfo(location.timezone)

        reference_time = _local_noon_time(ts, target_date, timezone) if target_date is not None else None
        _, window_start, window_end = _find_tonights_window(ephemeris, ts, observer_topos, reference_time)
        if window_start is None or window_end is None:
            raise Exception("Could not determine tonight's observing window")

        window_hours = (window_end.tt - window_start.tt) * 24
        sample_count = max(2, int((window_hours * 60) / SAMPLE_INTERVAL_MINUTES) + 1)
        sample_tt = np.linspace(window_start.tt, window_end.tt, sample_count)
        sample_times = ts.tt_jd(sample_tt)
        step_hours = window_hours / (sample_count - 1) if sample_count > 1 else 0

        targets = []

        for planet_id in PLANET_NAMES:
            try:
                planet = ephemeris[planet_id]
                apparent = observer.at(sample_times).observe(planet).apparent()
                alt, az, distance = apparent.altaz()
                altitude_degrees = alt.degrees

                above_horizon = altitude_degrees > 0
                if not above_horizon.any():
                    # Planet never rises during tonight's window; skip it
                    continue

                max_index = int(np.argmax(altitude_degrees))
                max_altitude = float(altitude_degrees[max_index])
                best_viewing_time = _format_local_time(sample_times[max_index], timezone)
                best_viewing_time_utc = sample_times[max_index].utc_datetime()

                above_indices = np.where(above_horizon)[0]
                first_index, last_index = above_indices[0], above_indices[-1]
                observable_duration_hours = (
                    (sample_times[last_index].tt - sample_times[first_index].tt) * 24 + step_hours
                )

                targets.append({
                    "name": DISPLAY_NAMES[planet_id],
                    "max_altitude": round(max_altitude, 2),
                    "best_viewing_time": best_viewing_time,
                    "best_viewing_time_utc": best_viewing_time_utc,
                    "observable_duration_hours": round(observable_duration_hours, 2),
                    "apparent_magnitude": APPROXIMATE_MAGNITUDES[planet_id]
                })
            except Exception as e:
                # Print warning but continue to next planet
                print(f"Warning: Could not calculate position for {DISPLAY_NAMES[planet_id]}: {e}")
                continue

        return targets

    except Exception as e:
        raise Exception(f"Failed to calculate planetary positions: {e}")


def _classify_moon_phase(phase_angle_degrees):
    """Classify a lunar elongation angle (0-360 degrees) into a named phase."""
    angle = phase_angle_degrees % 360
    if angle < 11.25 or angle >= 348.75:
        return "New Moon"
    if angle < 78.75:
        return "Waxing Crescent"
    if angle < 101.25:
        return "First Quarter"
    if angle < 168.75:
        return "Waxing Gibbous"
    if angle < 191.25:
        return "Full Moon"
    if angle < 258.75:
        return "Waning Gibbous"
    if angle < 281.25:
        return "Last Quarter"
    return "Waning Crescent"


def _first_time_at_or_after(times, reference):
    """Return the first Skyfield Time in `times` at or after `reference`, or None."""
    for t in sorted(times, key=lambda t: t.tt):
        if t.tt >= reference.tt:
            return t
    return None


def _filter_valid_events(times, event_flags):
    """Keep only event times whose Skyfield event flag is True.

    find_risings()/find_settings() can report a candidate time that isn't
    actually a genuine rise/set (event_flags entry False), which should
    never be treated as a real moonrise/moonset.
    """
    return [t for t, is_valid in zip(times, event_flags) if is_valid]


def _select_moonrise_moonset(rise_times, set_times, window_start, window_end, moon_already_up):
    """Pick the moonrise/moonset relevant to a specific observing window.

    Rather than simply returning the next rise/set after the current clock
    time (which can surface tomorrow's moonrise while describing tonight's
    window), this associates events with the window itself: if the moon is
    already up when the window begins, the rise that brought it up is used
    (searching backward, never forward into a future night); otherwise only
    a rise that actually falls within the window counts.

    Args:
        rise_times (list): Candidate moonrise Time objects (any order/span).
        set_times (list): Candidate moonset Time objects (any order/span).
        window_start (Time): Start of the dark observing window.
        window_end (Time): End of the dark observing window.
        moon_already_up (bool): Whether the moon is above the horizon at
            window_start.

    Returns:
        tuple: (moonrise_time, moonset_time), either of which may be None.
    """
    if moon_already_up:
        moonrise_time = None
        for t in sorted(rise_times, key=lambda t: t.tt, reverse=True):
            if t.tt <= window_start.tt:
                moonrise_time = t
                break
        moonset_time = _first_time_at_or_after(set_times, window_start)
        return moonrise_time, moonset_time

    moonrise_time = None
    for t in sorted(rise_times, key=lambda t: t.tt):
        if window_start.tt <= t.tt <= window_end.tt:
            moonrise_time = t
            break

    if moonrise_time is None:
        return None, None

    moonset_time = _first_time_at_or_after(set_times, moonrise_time)
    return moonrise_time, moonset_time


def get_lunar_data(location, target_date=None):
    """Calculate tonight's lunar phase, illumination, and visibility details.

    Args:
        location (Location): Observer location to calculate lunar data for.
        target_date (date, optional): Local calendar date whose evening
            observing session to calculate. Defaults to None, which
            preserves the original current-moment-based behavior.

    Returns:
        dict: Contains phase_name, illumination_percent, is_waxing,
        moonrise, moonset (formatted local time strings or None),
        above_horizon_during_window (bool), best_viewing_time (str or
        None), and max_altitude (degrees or None).
    """
    try:
        ephemeris, ts = _get_ephemeris_and_timescale()
        earth = ephemeris["earth"]
        moon = ephemeris["moon"]
        observer_topos = Topos(latitude_degrees=location.latitude, longitude_degrees=location.longitude)
        observer = earth + observer_topos
        timezone = ZoneInfo(location.timezone)
        now = ts.now()

        reference_time = _local_noon_time(ts, target_date, timezone) if target_date is not None else None
        search_anchor = reference_time if reference_time is not None else now

        _, window_start, window_end = _find_tonights_window(ephemeris, ts, observer_topos, reference_time)

        # Phase/illumination are slow-changing, so tonight's window start (or
        # search_anchor, if no window was found) is a fine reference moment
        phase_reference_time = window_start if window_start is not None else search_anchor
        phase_angle_degrees = almanac.moon_phase(ephemeris, phase_reference_time).degrees
        illumination_fraction = almanac.fraction_illuminated(ephemeris, "moon", phase_reference_time)

        if window_start is not None and window_end is not None:
            # Search a span padded a day on each side so a rise shortly
            # before the window, or a set shortly after it, is still found
            search_start = ts.tt_jd(window_start.tt - 1)
            search_end = ts.tt_jd(window_end.tt + 1)
            rise_times, rise_flags = almanac.find_risings(observer, moon, search_start, search_end)
            set_times, set_flags = almanac.find_settings(observer, moon, search_start, search_end)
            rise_times = _filter_valid_events(rise_times, rise_flags)
            set_times = _filter_valid_events(set_times, set_flags)

            altitude_at_window_start = observer.at(window_start).observe(moon).apparent().altaz()[0].degrees
            moon_already_up = bool(altitude_at_window_start > 0)

            moonrise_time, moonset_time = _select_moonrise_moonset(
                rise_times, set_times, window_start, window_end, moon_already_up
            )
        else:
            # No dark window determined; fall back to the next events after search_anchor
            t0 = ts.tt_jd(search_anchor.tt - 1)
            t1 = ts.tt_jd(search_anchor.tt + 1)
            rise_times, rise_flags = almanac.find_risings(observer, moon, t0, t1)
            set_times, set_flags = almanac.find_settings(observer, moon, t0, t1)
            rise_times = _filter_valid_events(rise_times, rise_flags)
            set_times = _filter_valid_events(set_times, set_flags)
            moonrise_time = _first_time_at_or_after(rise_times, search_anchor)
            moonset_time = _first_time_at_or_after(set_times, search_anchor)

        above_horizon_during_window = False
        best_viewing_time = None
        max_altitude = None

        if window_start is not None and window_end is not None:
            window_hours = (window_end.tt - window_start.tt) * 24
            sample_count = max(2, int((window_hours * 60) / SAMPLE_INTERVAL_MINUTES) + 1)
            sample_tt = np.linspace(window_start.tt, window_end.tt, sample_count)
            sample_times = ts.tt_jd(sample_tt)

            apparent = observer.at(sample_times).observe(moon).apparent()
            alt, az, distance = apparent.altaz()
            altitude_degrees = alt.degrees

            above_horizon = altitude_degrees > 0
            above_horizon_during_window = bool(above_horizon.any())

            if above_horizon_during_window:
                max_index = int(np.argmax(altitude_degrees))
                max_altitude = round(float(altitude_degrees[max_index]), 2)
                best_viewing_time = _format_local_time(sample_times[max_index], timezone)

        return {
            "phase_name": _classify_moon_phase(phase_angle_degrees),
            "illumination_percent": round(float(illumination_fraction) * 100, 1),
            "is_waxing": bool(phase_angle_degrees % 360 < 180),
            "moonrise": _format_local_time(moonrise_time, timezone) if moonrise_time is not None else None,
            "moonset": _format_local_time(moonset_time, timezone) if moonset_time is not None else None,
            "above_horizon_during_window": above_horizon_during_window,
            "best_viewing_time": best_viewing_time,
            "max_altitude": max_altitude
        }

    except Exception as e:
        raise Exception(f"Failed to calculate lunar data: {e}")


def _midpoint_tt(start_tt, end_tt):
    """Return the midpoint Julian date (tt) between two tt values.

    Operating on continuous Julian dates (rather than local calendar
    strings) means this is unaffected by local-midnight rollover.
    """
    return (start_tt + end_tt) / 2


def get_darkest_window_portion(location, target_date=None):
    """Return the later, darker portion of tonight's observing window.

    This is an MVP approximation used for recommending meteor shower
    viewing times: rather than modeling radiant altitude minute-by-minute,
    it recommends the second half of the dark astronomical window (from
    its midpoint to its end), since the sky is generally darkest and the
    radiant generally highest later in the night. This is an approximation,
    not a precise radiant-altitude calculation, and callers should treat it
    as such.

    Args:
        location (Location): Observer location.
        target_date (date, optional): Local calendar date whose evening
            observing session to calculate. Defaults to None, which
            preserves the original current-moment-based behavior.

    Returns:
        dict: Contains 'start' and 'end' as formatted local time strings,
        or None values for both if tonight's window could not be determined.
    """
    ephemeris, ts = _get_ephemeris_and_timescale()
    observer_topos = Topos(latitude_degrees=location.latitude, longitude_degrees=location.longitude)
    timezone = ZoneInfo(location.timezone)
    reference_time = _local_noon_time(ts, target_date, timezone) if target_date is not None else None
    _, window_start, window_end = _find_tonights_window(ephemeris, ts, observer_topos, reference_time)

    if window_start is None or window_end is None:
        return {"start": None, "end": None}

    midpoint_time = ts.tt_jd(_midpoint_tt(window_start.tt, window_end.tt))

    return {
        "start": _format_local_time(midpoint_time, timezone),
        "end": _format_local_time(window_end, timezone)
    }
