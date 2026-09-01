"""Meteor shower module for Night Signal.

Provides curated, static, approximate annual meteor shower reference data
and computes tonight's shower activity/status, an approximate best viewing
window, and a simple moon-interference estimate for a given observer
location.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from astronomy import get_darkest_window_portion, get_lunar_data


# Curated annual meteor shower reference data. Active date ranges and peak
# dates are typical/approximate annual values (real peak timing can shift by
# a day or two year to year) -- they are static reference data, not computed
# dynamically from any orbital/perturbation model. Dates are (month, day)
# tuples; a start > end pair means the active range wraps across New Year's.
METEOR_SHOWERS = [
    {
        "name": "Quadrantids",
        "start": (12, 28),
        "end": (1, 12),
        "peak": (1, 4),
        "typical_zhr": 120,
        "radiant": "Boötes"
    },
    {
        "name": "Lyrids",
        "start": (4, 14),
        "end": (4, 30),
        "peak": (4, 22),
        "typical_zhr": 18,
        "radiant": "Lyra"
    },
    {
        "name": "Eta Aquariids",
        "start": (4, 19),
        "end": (5, 28),
        "peak": (5, 5),
        "typical_zhr": 50,
        "radiant": "Aquarius"
    },
    {
        "name": "Delta Aquariids",
        "start": (7, 12),
        "end": (8, 23),
        "peak": (7, 30),
        "typical_zhr": 25,
        "radiant": "Aquarius"
    },
    {
        "name": "Perseids",
        "start": (7, 17),
        "end": (8, 24),
        "peak": (8, 12),
        "typical_zhr": 100,
        "radiant": "Perseus"
    },
    {
        "name": "Orionids",
        "start": (10, 2),
        "end": (11, 7),
        "peak": (10, 21),
        "typical_zhr": 20,
        "radiant": "Orion"
    },
    {
        "name": "Leonids",
        "start": (11, 6),
        "end": (11, 30),
        "peak": (11, 17),
        "typical_zhr": 15,
        "radiant": "Leo"
    },
    {
        "name": "Geminids",
        "start": (12, 4),
        "end": (12, 17),
        "peak": (12, 13),
        "typical_zhr": 150,
        "radiant": "Gemini"
    },
    {
        "name": "Ursids",
        "start": (12, 17),
        "end": (12, 26),
        "peak": (12, 22),
        "typical_zhr": 10,
        "radiant": "Ursa Minor"
    }
]

# Classification thresholds, in days from a shower's peak date
PEAK_TONIGHT_WINDOW_DAYS = 1
NEAR_PEAK_WINDOW_DAYS = 3

# Moon illumination thresholds (%) for interference classification
MODERATE_ILLUMINATION_THRESHOLD = 20
HIGH_ILLUMINATION_THRESHOLD = 50

_MONTH_ABBREVIATIONS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]

# Priority used to sort/rank active showers by relevance
_STATUS_PRIORITY = {"Peak Tonight": 0, "Near Peak": 1, "Active": 2}


def _format_month_day(month_day):
    """Format a (month, day) tuple as a short display string, e.g. 'Dec 28'."""
    month, day = month_day
    return f"{_MONTH_ABBREVIATIONS[month - 1]} {day}"


def _day_of_year(month, day):
    """Convert a month/day to a day-of-year on a fixed non-leap reference year."""
    return date(2001, month, day).timetuple().tm_yday


def _circular_day_diff(target_day, reference_day, year_length=365):
    """Smallest signed distance (in days) from reference_day to target_day
    on a circular (wraparound) year."""
    diff = (target_day - reference_day) % year_length
    if diff > year_length / 2:
        diff -= year_length
    return diff


def _month_day_in_range(month, day, start, end):
    """Check whether a month/day falls within a start/end month/day range,
    handling ranges that wrap across the new year (e.g., Dec 28 - Jan 12)."""
    target = (month, day)
    if start <= end:
        return start <= target <= end
    return target >= start or target <= end


def _classify_shower_status(today_month_day, shower):
    """Classify a shower's status for a given (month, day).

    Rules (documented, deterministic):
    - Inactive: today is outside the shower's active date range.
    - Peak Tonight: today is within PEAK_TONIGHT_WINDOW_DAYS days of the
      peak date.
    - Near Peak: today is within NEAR_PEAK_WINDOW_DAYS days of the peak
      date (but not close enough to be "Peak Tonight").
    - Active: today is within the active range but not near the peak.
    """
    month, day = today_month_day
    if not _month_day_in_range(month, day, shower["start"], shower["end"]):
        return "Inactive"

    today_doy = _day_of_year(month, day)
    peak_doy = _day_of_year(*shower["peak"])
    days_from_peak = abs(_circular_day_diff(today_doy, peak_doy))

    if days_from_peak <= PEAK_TONIGHT_WINDOW_DAYS:
        return "Peak Tonight"
    if days_from_peak <= NEAR_PEAK_WINDOW_DAYS:
        return "Near Peak"
    return "Active"


def _classify_moon_interference(illumination_percent, moon_above_horizon_during_window):
    """Classify how much the Moon likely interferes with meteor observing.

    Rules (documented, deterministic):
    - Low: the Moon is not above the horizon at any point during the dark
      observing window (its light isn't washing out the sky that night),
      or it is up but dim (illumination below MODERATE_ILLUMINATION_THRESHOLD%).
    - Moderate: the Moon is above the horizon during the window and is
      between MODERATE_ILLUMINATION_THRESHOLD% and
      HIGH_ILLUMINATION_THRESHOLD% illuminated.
    - High: the Moon is above the horizon during the window and is at
      least HIGH_ILLUMINATION_THRESHOLD% illuminated.

    This does not affect planetary visibility scoring; it is only used to
    describe meteor observing conditions.
    """
    if not moon_above_horizon_during_window:
        return "Low"
    if illumination_percent >= HIGH_ILLUMINATION_THRESHOLD:
        return "High"
    if illumination_percent >= MODERATE_ILLUMINATION_THRESHOLD:
        return "Moderate"
    return "Low"


def _days_until_start(today, shower):
    """Days from `today` until a shower's next start date on the real calendar.

    Builds the shower's start date in today's year; if that date has
    already passed, uses the same month/day in the following year instead
    (so a December start date correctly rolls into next January). Uses
    real calendar-date arithmetic rather than a fixed 365-day reference
    year, so this stays correct across leap years.

    Args:
        today (date): The current date.
        shower (dict): Shower definition with a "start" (month, day) tuple.

    Returns:
        int: Days until the shower's start date; 0 if it starts today.
    """
    start_month, start_day = shower["start"]
    candidate_start = date(today.year, start_month, start_day)
    if candidate_start < today:
        candidate_start = date(today.year + 1, start_month, start_day)
    return (candidate_start - today).days


def _find_next_upcoming_shower(today, showers=None):
    """Find the shower whose active period starts soonest after today.

    Uses real calendar-date arithmetic (see _days_until_start) so the
    search correctly rolls from December into the following January --
    e.g., after the Ursids end, the next shower found is next year's
    Quadrantids -- and stays correct across leap years.

    Args:
        today (date): The current date.
        showers (list, optional): Shower definitions to search. Defaults
            to METEOR_SHOWERS.

    Returns:
        dict: name, active_start, peak_date, typical_zhr, and
        days_until_start for the soonest-starting shower, or None if
        `showers` is empty.
    """
    showers = METEOR_SHOWERS if showers is None else showers
    if not showers:
        return None

    upcoming = min(showers, key=lambda shower: _days_until_start(today, shower))
    return {
        "name": upcoming["name"],
        "active_start": _format_month_day(upcoming["start"]),
        "peak_date": _format_month_day(upcoming["peak"]),
        "typical_zhr": upcoming["typical_zhr"],
        "days_until_start": _days_until_start(today, upcoming)
    }


def get_meteor_activity(location, today=None):
    """Determine tonight's meteor shower activity for an observer location.

    Checks each shower in METEOR_SHOWERS against today's local date,
    classifies its status, and attaches an approximate best viewing window
    (the darker second half of tonight's observing window -- see
    get_darkest_window_portion) plus a moon-interference estimate derived
    from Night Signal's existing lunar data. Reference dates are
    approximate/typical annual values, not exact for any specific year.

    Args:
        location (Location): Observer location.
        today (date, optional): Override for "today" (local date), mainly
            for testing. Defaults to the location's current local date.

    Returns:
        dict: Contains "active_showers" (list of dicts with name, status,
        active_start, active_end, peak_date, typical_zhr, radiant,
        best_viewing_window, and moon_interference; sorted with the most
        relevant shower first), "has_activity" (bool), and "next_shower"
        (dict with name, active_start, peak_date, typical_zhr, and
        days_until_start for the soonest upcoming shower, only populated
        when there is no current activity; otherwise None).
    """
    # Track whether the caller explicitly requested a date, distinct from
    # `today` below (which gets defaulted for shower-status purposes).
    # Only an explicit request is forwarded to get_lunar_data/
    # get_darkest_window_portion, so the no-argument call path continues
    # to use their original current-moment-based behavior unchanged.
    explicit_target_date = today
    if today is None:
        today = datetime.now(ZoneInfo(location.timezone)).date()
    today_month_day = (today.month, today.day)

    try:
        lunar = get_lunar_data(location, target_date=explicit_target_date)
        moon_interference = _classify_moon_interference(
            lunar["illumination_percent"], lunar["above_horizon_during_window"]
        )
    except Exception:
        moon_interference = None

    try:
        viewing_window = get_darkest_window_portion(location, target_date=explicit_target_date)
    except Exception:
        viewing_window = {"start": None, "end": None}

    best_viewing_window = (
        f"{viewing_window['start']} - {viewing_window['end']}"
        if viewing_window["start"] and viewing_window["end"]
        else None
    )

    active_showers = []
    for shower in METEOR_SHOWERS:
        status = _classify_shower_status(today_month_day, shower)
        if status == "Inactive":
            continue
        active_showers.append({
            "name": shower["name"],
            "status": status,
            "active_start": _format_month_day(shower["start"]),
            "active_end": _format_month_day(shower["end"]),
            "peak_date": _format_month_day(shower["peak"]),
            "typical_zhr": shower["typical_zhr"],
            "radiant": shower["radiant"],
            "best_viewing_window": best_viewing_window,
            "moon_interference": moon_interference
        })

    active_showers.sort(key=lambda shower: _STATUS_PRIORITY.get(shower["status"], 3))

    next_shower = None if active_showers else _find_next_upcoming_shower(today)

    return {
        "active_showers": active_showers,
        "has_activity": len(active_showers) > 0,
        "next_shower": next_shower
    }
