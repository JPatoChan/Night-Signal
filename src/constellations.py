"""Curated constellation signal selection for Night Signal.

V1 intentionally uses a small curated set of well-known constellations
instead of a full star catalog. Selection is still location/date-aware:
the scorer samples each constellation's anchor stars across the selected
dark observing window and prefers constellations whose key stars are
higher, more fully visible, brighter, and seasonally prominent.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
from skyfield.api import Star, Topos

from astronomy import _find_tonights_window, _format_local_time, _get_ephemeris_and_timescale, _local_noon_time


CONSTELLATION_MIN_VISIBLE_STARS = 3
CONSTELLATION_MIN_AVERAGE_ALTITUDE_DEGREES = 15
CONSTELLATION_SAMPLE_INTERVAL_MINUTES = 20

STAR_COLORS = {
    "red": "#f87171",
    "orange-red": "#fb923c",
    "orange": "#f59e0b",
    "yellow-white": "#fef3c7",
    "white": "#e4ecff",
    "blue-white": "#bfdbfe",
}


CONSTELLATIONS = [
    {
        "name": "Orion",
        "description": "Prominent winter constellation with bright, easy-to-spot anchor stars.",
        "best_months": [12, 1, 2, 3],
        "direction": "south to southwest",
        "stars": [
            {"name": "Betelgeuse", "descriptor": "red supergiant", "color": "orange-red", "magnitude": 0.5, "ra_hours": 5.92, "dec_degrees": 7.41, "x": 33, "y": 22},
            {"name": "Rigel", "descriptor": "blue-white supergiant", "color": "blue-white", "magnitude": 0.1, "ra_hours": 5.24, "dec_degrees": -8.20, "x": 72, "y": 82},
            {"name": "Bellatrix", "descriptor": "blue-white giant", "color": "blue-white", "magnitude": 1.6, "ra_hours": 5.42, "dec_degrees": 6.35, "x": 67, "y": 24},
            {"name": "Saiph", "descriptor": "hot blue supergiant", "color": "blue-white", "magnitude": 2.1, "ra_hours": 5.80, "dec_degrees": -9.67, "x": 30, "y": 80},
            {"name": "Alnilam", "descriptor": "central belt star", "color": "blue-white", "magnitude": 1.7, "ra_hours": 5.60, "dec_degrees": -1.20, "x": 50, "y": 52},
        ],
        "lines": [(0, 4), (2, 4), (4, 1), (4, 3), (0, 2), (3, 1)],
    },
    {
        "name": "Ursa Major",
        "description": "Northern landmark constellation anchored by the Big Dipper pattern.",
        "best_months": [3, 4, 5, 6],
        "direction": "north",
        "stars": [
            {"name": "Dubhe", "descriptor": "orange giant pointer star", "color": "orange", "magnitude": 1.8, "ra_hours": 11.06, "dec_degrees": 61.75, "x": 24, "y": 38},
            {"name": "Merak", "descriptor": "white pointer star", "color": "white", "magnitude": 2.4, "ra_hours": 11.03, "dec_degrees": 56.38, "x": 31, "y": 62},
            {"name": "Phecda", "descriptor": "white bowl star", "color": "white", "magnitude": 2.4, "ra_hours": 11.90, "dec_degrees": 53.69, "x": 48, "y": 68},
            {"name": "Megrez", "descriptor": "blue-white bowl star", "color": "blue-white", "magnitude": 3.3, "ra_hours": 12.26, "dec_degrees": 57.03, "x": 48, "y": 45},
            {"name": "Alioth", "descriptor": "bright handle star", "color": "white", "magnitude": 1.8, "ra_hours": 12.90, "dec_degrees": 55.96, "x": 65, "y": 42},
        ],
        "lines": [(0, 1), (1, 2), (2, 3), (3, 0), (3, 4)],
    },
    {
        "name": "Cassiopeia",
        "description": "A bright W-shaped northern constellation, especially useful when the Big Dipper is low.",
        "best_months": [9, 10, 11, 12],
        "direction": "north to northeast",
        "stars": [
            {"name": "Schedar", "descriptor": "orange giant", "color": "orange", "magnitude": 2.2, "ra_hours": 0.68, "dec_degrees": 56.54, "x": 18, "y": 61},
            {"name": "Caph", "descriptor": "yellow-white giant", "color": "yellow-white", "magnitude": 2.3, "ra_hours": 0.15, "dec_degrees": 59.15, "x": 33, "y": 34},
            {"name": "Gamma Cassiopeiae", "descriptor": "blue-white variable star", "color": "blue-white", "magnitude": 2.5, "ra_hours": 0.95, "dec_degrees": 60.72, "x": 50, "y": 58},
            {"name": "Ruchbah", "descriptor": "blue-white eclipsing binary", "color": "blue-white", "magnitude": 2.7, "ra_hours": 1.43, "dec_degrees": 60.24, "x": 67, "y": 33},
            {"name": "Segin", "descriptor": "blue-white giant", "color": "blue-white", "magnitude": 3.4, "ra_hours": 1.91, "dec_degrees": 63.67, "x": 83, "y": 55},
        ],
        "lines": [(0, 1), (1, 2), (2, 3), (3, 4)],
    },
    {
        "name": "Scorpius",
        "description": "Low southern summer constellation with a curved tail and brilliant red Antares.",
        "best_months": [6, 7, 8],
        "direction": "south",
        "stars": [
            {"name": "Antares", "descriptor": "red supergiant", "color": "red", "magnitude": 1.1, "ra_hours": 16.49, "dec_degrees": -26.43, "x": 42, "y": 28},
            {"name": "Shaula", "descriptor": "blue-white stinger star", "color": "blue-white", "magnitude": 1.6, "ra_hours": 17.56, "dec_degrees": -37.10, "x": 73, "y": 77},
            {"name": "Sargas", "descriptor": "yellow-white giant", "color": "yellow-white", "magnitude": 1.9, "ra_hours": 17.62, "dec_degrees": -42.99, "x": 58, "y": 88},
            {"name": "Dschubba", "descriptor": "blue-white forehead star", "color": "blue-white", "magnitude": 2.3, "ra_hours": 16.01, "dec_degrees": -22.62, "x": 27, "y": 20},
        ],
        "lines": [(3, 0), (0, 2), (2, 1)],
    },
    {
        "name": "Cygnus",
        "description": "Summer Milky Way constellation shaped like a northern cross.",
        "best_months": [7, 8, 9, 10],
        "direction": "overhead to northeast",
        "stars": [
            {"name": "Deneb", "descriptor": "blue-white supergiant", "color": "blue-white", "magnitude": 1.3, "ra_hours": 20.69, "dec_degrees": 45.28, "x": 50, "y": 17},
            {"name": "Sadr", "descriptor": "central cross star", "color": "yellow-white", "magnitude": 2.2, "ra_hours": 20.37, "dec_degrees": 40.26, "x": 50, "y": 45},
            {"name": "Albireo", "descriptor": "colorful double star", "color": "orange", "magnitude": 3.1, "ra_hours": 19.51, "dec_degrees": 27.96, "x": 50, "y": 82},
            {"name": "Gienah", "descriptor": "orange giant wing star", "color": "orange", "magnitude": 2.5, "ra_hours": 20.77, "dec_degrees": 33.97, "x": 77, "y": 50},
            {"name": "Delta Cygni", "descriptor": "blue-white wing star", "color": "blue-white", "magnitude": 2.9, "ra_hours": 19.75, "dec_degrees": 45.13, "x": 23, "y": 50},
        ],
        "lines": [(0, 1), (1, 2), (4, 1), (1, 3)],
    },
    {
        "name": "Lyra",
        "description": "Compact summer constellation dominated by the brilliant blue-white star Vega.",
        "best_months": [6, 7, 8, 9],
        "direction": "east to overhead",
        "stars": [
            {"name": "Vega", "descriptor": "blue-white beacon star", "color": "blue-white", "magnitude": 0.0, "ra_hours": 18.62, "dec_degrees": 38.78, "x": 50, "y": 14},
            {"name": "Sheliak", "descriptor": "blue-white variable star", "color": "blue-white", "magnitude": 3.5, "ra_hours": 18.83, "dec_degrees": 33.36, "x": 34, "y": 60},
            {"name": "Sulafat", "descriptor": "blue-white giant", "color": "blue-white", "magnitude": 3.3, "ra_hours": 18.98, "dec_degrees": 32.69, "x": 65, "y": 62},
        ],
        "lines": [(0, 1), (0, 2), (1, 2)],
    },
    {
        "name": "Leo",
        "description": "Spring constellation with the Sickle asterism and bright Regulus.",
        "best_months": [2, 3, 4, 5],
        "direction": "south",
        "stars": [
            {"name": "Regulus", "descriptor": "blue-white heart of the lion", "color": "blue-white", "magnitude": 1.4, "ra_hours": 10.14, "dec_degrees": 11.97, "x": 29, "y": 67},
            {"name": "Denebola", "descriptor": "white tail star", "color": "white", "magnitude": 2.1, "ra_hours": 11.82, "dec_degrees": 14.57, "x": 78, "y": 48},
            {"name": "Algieba", "descriptor": "golden double star", "color": "yellow-white", "magnitude": 2.0, "ra_hours": 10.33, "dec_degrees": 19.84, "x": 42, "y": 35},
        ],
        "lines": [(0, 2), (2, 1)],
    },
    {
        "name": "Taurus",
        "description": "Winter constellation marked by orange Aldebaran and the Hyades star pattern.",
        "best_months": [11, 12, 1, 2],
        "direction": "south",
        "stars": [
            {"name": "Aldebaran", "descriptor": "orange-red giant", "color": "orange-red", "magnitude": 0.9, "ra_hours": 4.60, "dec_degrees": 16.51, "x": 45, "y": 50},
            {"name": "Elnath", "descriptor": "blue-white horn star", "color": "blue-white", "magnitude": 1.7, "ra_hours": 5.44, "dec_degrees": 28.61, "x": 74, "y": 20},
            {"name": "Alcyone", "descriptor": "blue-white Pleiades star", "color": "blue-white", "magnitude": 2.9, "ra_hours": 3.79, "dec_degrees": 24.11, "x": 20, "y": 30},
        ],
        "lines": [(2, 0), (0, 1)],
    },
    {
        "name": "Pegasus",
        "description": "Autumn constellation known for the large Great Square pattern.",
        "best_months": [9, 10, 11],
        "direction": "southeast to south",
        "stars": [
            {"name": "Markab", "descriptor": "blue-white square star", "color": "blue-white", "magnitude": 2.5, "ra_hours": 23.08, "dec_degrees": 15.21, "x": 24, "y": 68},
            {"name": "Scheat", "descriptor": "red giant", "color": "red", "magnitude": 2.4, "ra_hours": 23.06, "dec_degrees": 28.08, "x": 24, "y": 28},
            {"name": "Algenib", "descriptor": "blue-white square star", "color": "blue-white", "magnitude": 2.8, "ra_hours": 0.22, "dec_degrees": 15.18, "x": 76, "y": 68},
        ],
        "lines": [(0, 1), (1, 2), (2, 0)],
    },
    {
        "name": "Sagittarius",
        "description": "Summer constellation in the direction of the Milky Way's bright central region.",
        "best_months": [7, 8, 9],
        "direction": "south",
        "stars": [
            {"name": "Kaus Australis", "descriptor": "blue-white giant", "color": "blue-white", "magnitude": 1.8, "ra_hours": 18.40, "dec_degrees": -34.38, "x": 52, "y": 76},
            {"name": "Nunki", "descriptor": "blue-white star", "color": "blue-white", "magnitude": 2.0, "ra_hours": 18.92, "dec_degrees": -26.30, "x": 76, "y": 42},
            {"name": "Kaus Media", "descriptor": "orange giant", "color": "orange", "magnitude": 2.7, "ra_hours": 18.35, "dec_degrees": -29.83, "x": 42, "y": 52},
        ],
        "lines": [(2, 0), (2, 1), (0, 1)],
    },
    {
        "name": "Canis Major",
        "description": "Winter constellation containing Sirius, the brightest star in the night sky.",
        "best_months": [12, 1, 2, 3],
        "direction": "south",
        "stars": [
            {"name": "Sirius", "descriptor": "brilliant white star", "color": "white", "magnitude": -1.5, "ra_hours": 6.75, "dec_degrees": -16.72, "x": 38, "y": 31},
            {"name": "Adhara", "descriptor": "blue-white giant", "color": "blue-white", "magnitude": 1.5, "ra_hours": 6.98, "dec_degrees": -28.97, "x": 62, "y": 71},
            {"name": "Wezen", "descriptor": "yellow-white supergiant", "color": "yellow-white", "magnitude": 1.8, "ra_hours": 7.14, "dec_degrees": -26.39, "x": 78, "y": 58},
        ],
        "lines": [(0, 1), (1, 2)],
    },
    {
        "name": "Gemini",
        "description": "Twin-star winter constellation led by Castor and Pollux.",
        "best_months": [12, 1, 2, 3, 4],
        "direction": "south to southwest",
        "stars": [
            {"name": "Pollux", "descriptor": "orange giant", "color": "orange", "magnitude": 1.1, "ra_hours": 7.76, "dec_degrees": 28.03, "x": 63, "y": 25},
            {"name": "Castor", "descriptor": "white multiple star", "color": "white", "magnitude": 1.6, "ra_hours": 7.58, "dec_degrees": 31.89, "x": 40, "y": 18},
            {"name": "Alhena", "descriptor": "blue-white subgiant", "color": "blue-white", "magnitude": 1.9, "ra_hours": 6.63, "dec_degrees": 16.40, "x": 42, "y": 76},
        ],
        "lines": [(1, 2), (0, 2)],
    },
    {
        "name": "Bootes",
        "description": "Spring constellation anchored by warm orange Arcturus.",
        "best_months": [4, 5, 6, 7],
        "direction": "east to south",
        "stars": [
            {"name": "Arcturus", "descriptor": "orange giant", "color": "orange", "magnitude": -0.1, "ra_hours": 14.26, "dec_degrees": 19.18, "x": 51, "y": 80},
            {"name": "Nekkar", "descriptor": "yellow giant", "color": "yellow-white", "magnitude": 3.5, "ra_hours": 15.03, "dec_degrees": 40.39, "x": 50, "y": 15},
            {"name": "Izar", "descriptor": "colorful double star", "color": "orange", "magnitude": 2.4, "ra_hours": 14.75, "dec_degrees": 27.07, "x": 36, "y": 51},
        ],
        "lines": [(0, 2), (2, 1)],
    },
    {
        "name": "Andromeda",
        "description": "Autumn constellation pointing toward the nearby Andromeda Galaxy.",
        "best_months": [9, 10, 11, 12],
        "direction": "east to overhead",
        "stars": [
            {"name": "Alpheratz", "descriptor": "blue-white corner star", "color": "blue-white", "magnitude": 2.1, "ra_hours": 0.14, "dec_degrees": 29.09, "x": 20, "y": 55},
            {"name": "Mirach", "descriptor": "red giant", "color": "red", "magnitude": 2.1, "ra_hours": 1.16, "dec_degrees": 35.62, "x": 50, "y": 40},
            {"name": "Almach", "descriptor": "gold-blue double star", "color": "yellow-white", "magnitude": 2.1, "ra_hours": 2.06, "dec_degrees": 42.33, "x": 80, "y": 25},
        ],
        "lines": [(0, 1), (1, 2)],
    },
    {
        "name": "Aquila",
        "description": "Summer constellation whose bright Altair forms part of the Summer Triangle.",
        "best_months": [7, 8, 9],
        "direction": "south to southwest",
        "stars": [
            {"name": "Altair", "descriptor": "bright white star", "color": "white", "magnitude": 0.8, "ra_hours": 19.85, "dec_degrees": 8.87, "x": 51, "y": 46},
            {"name": "Tarazed", "descriptor": "orange bright giant", "color": "orange", "magnitude": 2.7, "ra_hours": 19.77, "dec_degrees": 10.61, "x": 42, "y": 24},
            {"name": "Alshain", "descriptor": "yellow-white companion star", "color": "yellow-white", "magnitude": 3.7, "ra_hours": 19.92, "dec_degrees": 6.41, "x": 60, "y": 70},
        ],
        "lines": [(1, 0), (0, 2)],
    },
]


def _resolve_observing_date(location, target_date):
    """Resolve Tonight mode to the observer's local date."""
    return target_date if target_date is not None else datetime.now(ZoneInfo(location.timezone)).date()


def _get_sample_times(location, target_date):
    """Return Skyfield sample times across the selected dark window."""
    ephemeris, ts = _get_ephemeris_and_timescale()
    observer_topos = Topos(latitude_degrees=location.latitude, longitude_degrees=location.longitude)
    timezone = ZoneInfo(location.timezone)
    reference_time = _local_noon_time(ts, target_date, timezone) if target_date is not None else None
    _, window_start, window_end = _find_tonights_window(ephemeris, ts, observer_topos, reference_time)

    if window_start is None or window_end is None:
        return None, None, None

    window_hours = (window_end.tt - window_start.tt) * 24
    sample_count = max(2, int((window_hours * 60) / CONSTELLATION_SAMPLE_INTERVAL_MINUTES) + 1)
    sample_times = ts.tt_jd(np.linspace(window_start.tt, window_end.tt, sample_count))
    return ephemeris, ts, sample_times


def _season_score(best_months, month):
    """Score how close the selected month is to the constellation's season."""
    if month in best_months:
        return 20
    distances = [min((month - best_month) % 12, (best_month - month) % 12) for best_month in best_months]
    closest_distance = min(distances)
    return max(0, 12 - closest_distance * 4)


def _brightness_score(stars):
    """Score a constellation's notable-star brightness."""
    average_magnitude = sum(star["magnitude"] for star in stars[:3]) / min(3, len(stars))
    return max(0, 20 - average_magnitude * 4)


def _star_display_interest(star):
    """Small tie-breaker for visually distinctive star colors."""
    return {"red": 0, "orange-red": 0, "orange": 1, "yellow-white": 2, "blue-white": 2, "white": 3}.get(star["color"], 4)


def _score_constellation(visible_star_count, average_altitude, brightness_score, season_score):
    """Combine simple visibility, altitude, brightness, and season inputs."""
    if visible_star_count < CONSTELLATION_MIN_VISIBLE_STARS:
        return None
    if average_altitude < CONSTELLATION_MIN_AVERAGE_ALTITUDE_DEGREES:
        return None
    visibility_score = visible_star_count * 15
    altitude_score = min(35, average_altitude / 2)
    return visibility_score + altitude_score + brightness_score + season_score


def _best_collective_sample(stars, star_altitude_rows):
    """Find the best sample where enough anchor stars are visible together."""
    if not star_altitude_rows:
        return None

    sample_count = len(star_altitude_rows[0])
    best = None
    for sample_index in range(sample_count):
        visible_indices = [
            star_index
            for star_index, altitudes in enumerate(star_altitude_rows)
            if float(altitudes[sample_index]) >= CONSTELLATION_MIN_AVERAGE_ALTITUDE_DEGREES
        ]
        if len(visible_indices) < CONSTELLATION_MIN_VISIBLE_STARS:
            continue

        visible_altitudes = [float(star_altitude_rows[star_index][sample_index]) for star_index in visible_indices]
        visible_stars = [stars[star_index] for star_index in visible_indices]
        average_altitude = sum(visible_altitudes) / len(visible_altitudes)
        brightness_score = _brightness_score(sorted(visible_stars, key=lambda star: star["magnitude"]))
        placement = (len(visible_indices), average_altitude, brightness_score)

        if best is None or placement > best["placement"]:
            best = {
                "sample_index": sample_index,
                "visible_indices": visible_indices,
                "visible_star_count": len(visible_indices),
                "average_altitude": average_altitude,
                "brightness_score": brightness_score,
                "placement": placement,
            }

    return best


def _evaluate_constellation(constellation, location, target_date, sample_times, ephemeris):
    """Evaluate one curated constellation for the selected observing window."""
    observer = ephemeris["earth"] + Topos(latitude_degrees=location.latitude, longitude_degrees=location.longitude)
    star_altitude_rows = []

    for star in constellation["stars"]:
        body = Star(ra_hours=star["ra_hours"], dec_degrees=star["dec_degrees"])
        apparent = observer.at(sample_times).observe(body).apparent()
        altitude, _, _ = apparent.altaz()
        star_altitude_rows.append(altitude.degrees)

    best_sample = _best_collective_sample(constellation["stars"], star_altitude_rows)
    if best_sample is None:
        return None

    query_date = _resolve_observing_date(location, target_date)
    score = _score_constellation(
        best_sample["visible_star_count"],
        best_sample["average_altitude"],
        best_sample["brightness_score"],
        _season_score(constellation["best_months"], query_date.month),
    )
    if score is None:
        return None

    return {
        "constellation": constellation,
        "score": score,
        "visible_star_count": best_sample["visible_star_count"],
        "visible_star_indices": best_sample["visible_indices"],
        "best_sample_index": best_sample["sample_index"],
        "average_altitude": round(best_sample["average_altitude"], 1),
        "best_viewing_time": _format_local_time(sample_times[best_sample["sample_index"]], ZoneInfo(location.timezone)),
    }


def _diagram_points(constellation):
    """Return stable diagram coordinates with display color metadata."""
    return [
        {
            "name": star["name"],
            "x": star["x"],
            "y": star["y"],
            "color": STAR_COLORS.get(star["color"], STAR_COLORS["white"]),
        }
        for star in constellation["stars"]
    ]


def _display_stars(constellation, visible_indices=None, limit=3):
    """Return visible featured stars with resolved display color values."""
    candidates = constellation["stars"] if visible_indices is None else [constellation["stars"][index] for index in visible_indices]
    ranked = sorted(candidates, key=lambda star: (star["magnitude"], _star_display_interest(star), star["name"]))
    return [
        {
            "name": star["name"],
            "descriptor": star["descriptor"],
            "color": star["color"],
            "display_color": STAR_COLORS.get(star["color"], STAR_COLORS["white"]),
        }
        for star in ranked[:limit]
    ]


def _format_visibility_summary(evaluation, constellation):
    """Build a compact visibility line for the dashboard card."""
    if evaluation["best_viewing_time"]:
        return (
            f"Best around {evaluation['best_viewing_time']}. Look generally {constellation['direction']}; "
            f"{evaluation['visible_star_count']} key stars clear the horizon."
        )
    return f"Look generally {constellation['direction']}; several key stars clear the horizon."


def get_constellation_signal(location, target_date=None):
    """Choose one featured constellation for the selected observing night."""
    try:
        ephemeris, _, sample_times = _get_sample_times(location, target_date)
        if sample_times is None:
            return {"has_constellation": False, "message": "No featured constellation signal available for this observing window."}

        evaluations = []
        for constellation in CONSTELLATIONS:
            evaluation = _evaluate_constellation(constellation, location, target_date, sample_times, ephemeris)
            if evaluation is not None:
                evaluations.append(evaluation)

        if not evaluations:
            return {"has_constellation": False, "message": "No featured constellation signal available for this observing window."}

        evaluations.sort(key=lambda evaluation: (-evaluation["score"], evaluation["constellation"]["name"]))
        best = evaluations[0]
        constellation = best["constellation"]

        return {
            "has_constellation": True,
            "name": constellation["name"],
            "description": constellation["description"],
            "direction": constellation["direction"],
            "best_viewing_note": _format_visibility_summary(best, constellation),
            "visibility_summary": f"Average key-star altitude about {best['average_altitude']:.0f}°.",
            "score": round(best["score"], 1),
            "stars": _display_stars(constellation, best.get("visible_star_indices")),
            "diagram_points": _diagram_points(constellation),
            "diagram_lines": constellation["lines"],
        }
    except Exception:
        return {"has_constellation": False, "message": "No featured constellation signal available for this observing window."}