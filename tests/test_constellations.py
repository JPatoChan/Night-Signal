"""Tests for Night Signal's Constellation Signal feature."""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

# Add repo root (for dashboard.py) and src/ (for constellations.py)
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import constellations
from config import DENVER, NASHVILLE
from constellations import (
    CONSTELLATION_MIN_AVERAGE_ALTITUDE_DEGREES,
    CONSTELLATION_MIN_VISIBLE_STARS,
    STAR_COLORS,
    _best_collective_sample,
    _display_stars,
    _evaluate_constellation,
    _score_constellation,
    get_constellation_signal,
)
import dashboard


def _sample_constellation(name, direction="south"):
    return {
        "name": name,
        "description": f"{name} test description.",
        "best_months": [1],
        "direction": direction,
        "stars": [
            {"name": f"{name} A", "descriptor": "red giant", "color": "red", "magnitude": 1.0, "x": 20, "y": 20},
            {"name": f"{name} B", "descriptor": "blue-white star", "color": "blue-white", "magnitude": 2.0, "x": 50, "y": 50},
            {"name": f"{name} C", "descriptor": "white star", "color": "white", "magnitude": 3.0, "x": 80, "y": 80},
        ],
        "lines": [(0, 1), (1, 2)],
    }


def _fake_sample_times(location, target_date):
    return {"earth": object()}, object(), [object()]


def _sample_constellation_with_extra_stars():
    constellation = _sample_constellation("Collective")
    constellation["stars"] = [
        {"name": "Unrelated Bright", "descriptor": "bright but not simultaneous", "color": "white", "magnitude": -1.0, "ra_hours": 1.0, "dec_degrees": 1.0, "x": 10, "y": 10},
        {"name": "Visible Red", "descriptor": "red visible star", "color": "red", "magnitude": 2.0, "ra_hours": 2.0, "dec_degrees": 2.0, "x": 20, "y": 20},
        {"name": "Visible Blue", "descriptor": "blue-white visible star", "color": "blue-white", "magnitude": 1.0, "ra_hours": 3.0, "dec_degrees": 3.0, "x": 30, "y": 30},
        {"name": "Visible White", "descriptor": "white visible star", "color": "white", "magnitude": 3.0, "ra_hours": 4.0, "dec_degrees": 4.0, "x": 40, "y": 40},
        {"name": "Too Low", "descriptor": "below threshold star", "color": "orange", "magnitude": 0.5, "ra_hours": 5.0, "dec_degrees": 5.0, "x": 50, "y": 50},
    ]
    constellation["lines"] = [(0, 1), (1, 2), (2, 3), (3, 4)]
    return constellation


class _FakeAngle:
    def __init__(self, degrees):
        self.degrees = degrees


class _FakeApparent:
    def __init__(self, altitudes):
        self._altitudes = altitudes

    def altaz(self):
        return (_FakeAngle(self._altitudes), None, None)


class _FakeObservePosition:
    def __init__(self, altitudes):
        self._altitudes = altitudes

    def apparent(self):
        return _FakeApparent(self._altitudes)


class _FakeAstrometric:
    def __init__(self, altitude_by_token):
        self._altitude_by_token = altitude_by_token

    def observe(self, star_token):
        return _FakeObservePosition(self._altitude_by_token[star_token])


class _FakeObserver:
    def __init__(self, altitude_by_token):
        self._altitude_by_token = altitude_by_token

    def at(self, sample_times):
        return _FakeAstrometric(self._altitude_by_token)


class _FakeEarth:
    def __init__(self, altitude_by_token):
        self._altitude_by_token = altitude_by_token

    def __add__(self, topos):
        return _FakeObserver(self._altitude_by_token)


def test_featured_constellation_returns_sane_structure():
    """Selecting a featured constellation returns the dashboard-ready shape."""
    low_score = {"constellation": _sample_constellation("Low"), "score": 50, "visible_star_count": 3, "average_altitude": 25, "best_viewing_time": "9:00 PM CDT"}
    high_score = {"constellation": _sample_constellation("High"), "score": 90, "visible_star_count": 3, "average_altitude": 55, "best_viewing_time": "10:00 PM CDT"}

    with patch.object(constellations, "_get_sample_times", side_effect=_fake_sample_times), \
         patch.object(constellations, "CONSTELLATIONS", [low_score["constellation"], high_score["constellation"]]), \
         patch.object(constellations, "_evaluate_constellation", side_effect=[low_score, high_score]):
        signal = get_constellation_signal(NASHVILLE, target_date=date(2026, 1, 15))

    assert signal["has_constellation"] is True
    assert signal["name"] == "High"
    assert signal["direction"] == "south"
    assert len(signal["stars"]) == 3
    assert len(signal["diagram_points"]) == 3
    assert signal["diagram_lines"] == [(0, 1), (1, 2)]
    assert "Best around 10:00 PM CDT" in signal["best_viewing_note"]
    print("✓ Featured constellation returns sane structured data")


def test_selection_depends_on_location_and_date_inputs():
    """The selector passes the selected location/date into evaluation and
    can choose different constellations for different inputs."""
    winter_constellation = _sample_constellation("Winter")
    summer_constellation = _sample_constellation("Summer")
    captured = []

    def fake_evaluate(constellation, location, target_date, sample_times, ephemeris):
        captured.append((constellation["name"], location, target_date))
        if location == DENVER and target_date == date(2026, 7, 1):
            score = 95 if constellation["name"] == "Summer" else 20
        else:
            score = 95 if constellation["name"] == "Winter" else 20
        return {
            "constellation": constellation,
            "score": score,
            "visible_star_count": 3,
            "average_altitude": 40,
            "best_viewing_time": "10:00 PM",
        }

    with patch.object(constellations, "_get_sample_times", side_effect=_fake_sample_times), \
         patch.object(constellations, "CONSTELLATIONS", [winter_constellation, summer_constellation]), \
         patch.object(constellations, "_evaluate_constellation", side_effect=fake_evaluate):
        nashville_signal = get_constellation_signal(NASHVILLE, target_date=date(2026, 1, 1))
        denver_signal = get_constellation_signal(DENVER, target_date=date(2026, 7, 1))

    assert nashville_signal["name"] == "Winter"
    assert denver_signal["name"] == "Summer"
    assert ("Winter", NASHVILLE, date(2026, 1, 1)) in captured
    assert ("Summer", DENVER, date(2026, 7, 1)) in captured
    print("✓ Constellation selection depends on location and date inputs")


def test_star_color_metadata_is_preserved():
    """Featured stars keep approximate color names and resolved display colors."""
    constellation = _sample_constellation("Color Test")
    evaluation = {"constellation": constellation, "score": 80, "visible_star_count": 3, "average_altitude": 40, "best_viewing_time": "9:00 PM"}

    with patch.object(constellations, "_get_sample_times", side_effect=_fake_sample_times), \
         patch.object(constellations, "CONSTELLATIONS", [constellation]), \
         patch.object(constellations, "_evaluate_constellation", return_value=evaluation):
        signal = get_constellation_signal(NASHVILLE, target_date=date(2026, 1, 15))

    assert [star["color"] for star in signal["stars"]] == ["red", "blue-white", "white"]
    assert [star["display_color"] for star in signal["stars"]] == [STAR_COLORS["red"], STAR_COLORS["blue-white"], STAR_COLORS["white"]]
    assert signal["diagram_points"][0]["color"] == STAR_COLORS["red"]
    print("✓ Star color metadata is preserved for bullets and diagrams")


def test_constellation_fallback_when_none_qualify():
    """If no constellation qualifies, the module returns a graceful fallback shape."""
    with patch.object(constellations, "_get_sample_times", side_effect=_fake_sample_times), \
         patch.object(constellations, "CONSTELLATIONS", [_sample_constellation("Low")]), \
         patch.object(constellations, "_evaluate_constellation", return_value=None):
        signal = get_constellation_signal(NASHVILLE, target_date=date(2026, 1, 15))

    assert signal["has_constellation"] is False
    assert "No featured constellation signal" in signal["message"]
    dashboard.render_constellation_signal(signal)
    print("✓ Fallback behavior works when no constellation qualifies")


def test_score_constellation_requires_enough_visible_stars_and_altitude():
    """The pure scorer rejects weak visibility and ranks sane inputs."""
    assert _score_constellation(CONSTELLATION_MIN_VISIBLE_STARS - 1, 60, 20, 20) is None
    assert _score_constellation(CONSTELLATION_MIN_VISIBLE_STARS, CONSTELLATION_MIN_AVERAGE_ALTITUDE_DEGREES - 1, 20, 20) is None
    score = _score_constellation(CONSTELLATION_MIN_VISIBLE_STARS, 50, 15, 20)
    assert score is not None
    assert score > _score_constellation(CONSTELLATION_MIN_VISIBLE_STARS, 25, 15, 0)
    print("✓ Constellation scorer rejects weak candidates and rewards better visibility")


def test_constellation_svg_contains_lines_and_star_colors():
    """The dashboard diagram renderer outputs lightweight inline SVG."""
    points = [
        {"name": "A", "x": 20, "y": 20, "color": STAR_COLORS["red"]},
        {"name": "B", "x": 50, "y": 50, "color": STAR_COLORS["blue-white"]},
    ]
    svg = dashboard.render_constellation_svg(points, [(0, 1)], size=96)

    assert "<svg" in svg
    assert "<line" in svg
    assert STAR_COLORS["red"] in svg
    assert STAR_COLORS["blue-white"] in svg
    print("✓ Constellation SVG renders lines and colored star nodes")


def test_best_sample_requires_three_simultaneously_visible_stars():
    """At least three anchor stars must be visible at the same sampled time."""
    stars = _sample_constellation_with_extra_stars()["stars"][:3]
    unrelated_maxima = [
        [40, 0, 0],
        [0, 40, 0],
        [0, 0, 40],
    ]

    assert _best_collective_sample(stars, unrelated_maxima) is None

    simultaneous = [
        [0, 25, 10],
        [0, 30, 10],
        [0, 35, 10],
    ]
    best = _best_collective_sample(stars, simultaneous)

    assert best is not None
    assert best["sample_index"] == 1
    assert best["visible_star_count"] == 3
    assert best["visible_indices"] == [0, 1, 2]
    print("✓ Best sample requires three simultaneously visible anchor stars")


def test_evaluate_constellation_uses_collective_best_time():
    """best_viewing_time is tied to the constellation's collective placement,
    not one unrelated star's maximum altitude."""
    constellation = _sample_constellation_with_extra_stars()
    sample_times = ["sample-0", "sample-1", "sample-2"]
    altitude_by_token = {
        "star-1.0": [80, 0, 0],
        "star-2.0": [0, 35, 28],
        "star-3.0": [0, 40, 30],
        "star-4.0": [0, 45, 32],
        "star-5.0": [0, 5, 10],
    }
    ephemeris = {"earth": _FakeEarth(altitude_by_token)}

    def fake_star(ra_hours, dec_degrees):
        return f"star-{ra_hours}"

    with patch.object(constellations, "Star", side_effect=fake_star), \
         patch.object(constellations, "_format_local_time", side_effect=lambda sample_time, timezone: sample_time):
        evaluation = _evaluate_constellation(constellation, NASHVILLE, date(2026, 1, 15), sample_times, ephemeris)

    assert evaluation is not None
    assert evaluation["best_sample_index"] == 1
    assert evaluation["best_viewing_time"] == "sample-1"
    assert evaluation["visible_star_count"] == 3
    assert evaluation["visible_star_indices"] == [1, 2, 3]
    print("✓ Evaluator uses collective best time instead of an individual star maximum")


def test_displayed_stars_are_visible_at_chosen_sample_and_capped():
    """Bullet stars are selected from the visible stars at the chosen sample,
    capped at three, and all belong to the featured constellation."""
    constellation = _sample_constellation_with_extra_stars()
    visible_indices = [1, 2, 3, 4]

    displayed = _display_stars(constellation, visible_indices)

    assert len(displayed) == 3
    displayed_names = {star["name"] for star in displayed}
    visible_names = {constellation["stars"][index]["name"] for index in visible_indices}
    constellation_names = {star["name"] for star in constellation["stars"]}
    assert displayed_names <= visible_names
    assert displayed_names <= constellation_names
    assert "Unrelated Bright" not in displayed_names
    assert all("display_color" in star for star in displayed)
    print("✓ Displayed stars are visible at the chosen sample, capped, and in the constellation")


def test_direction_wording_is_approximate():
    """The rendered visibility note avoids implying a precise dynamic bearing."""
    constellation = _sample_constellation("Direction", direction="south to southwest")
    evaluation = {
        "constellation": constellation,
        "score": 80,
        "visible_star_count": 3,
        "visible_star_indices": [0, 1, 2],
        "average_altitude": 40,
        "best_viewing_time": "10:00 PM CDT",
    }

    with patch.object(constellations, "_get_sample_times", side_effect=_fake_sample_times), \
         patch.object(constellations, "CONSTELLATIONS", [constellation]), \
         patch.object(constellations, "_evaluate_constellation", return_value=evaluation):
        signal = get_constellation_signal(NASHVILLE, target_date=date(2026, 1, 15))

    assert "Look generally south to southwest" in signal["best_viewing_note"]
    print("✓ Direction wording is clearly approximate")


if __name__ == "__main__":
    print("Running Constellation Signal tests...\n")
    test_featured_constellation_returns_sane_structure()
    test_selection_depends_on_location_and_date_inputs()
    test_star_color_metadata_is_preserved()
    test_constellation_fallback_when_none_qualify()
    test_score_constellation_requires_enough_visible_stars_and_altitude()
    test_constellation_svg_contains_lines_and_star_colors()
    test_best_sample_requires_three_simultaneously_visible_stars()
    test_evaluate_constellation_uses_collective_best_time()
    test_displayed_stars_are_visible_at_chosen_sample_and_capped()
    test_direction_wording_is_approximate()
    print("\n✓ All tests passed!")