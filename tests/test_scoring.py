"""Tests for the scoring module."""

import sys
from pathlib import Path

# Add src to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scoring import calculate_visibility_score


def test_score_high_altitude_good_conditions():
    """Test scoring with high peak altitude, long duration, and good conditions."""
    target = {"max_altitude": 80, "apparent_magnitude": -2.0, "observable_duration_hours": 5}
    conditions = {"cloud_cover": 10, "visibility": 10}
    score = calculate_visibility_score(target, conditions)
    assert score > 80, f"Expected score > 80, got {score}"
    print(f"✓ High altitude, good conditions: {score}/100")


def test_score_low_altitude_poor_conditions():
    """Test scoring with low altitude, short duration, and poor conditions."""
    target = {"max_altitude": 10, "apparent_magnitude": 2.0, "observable_duration_hours": 0.5}
    conditions = {"cloud_cover": 80, "visibility": 2}
    score = calculate_visibility_score(target, conditions)
    assert score < 40, f"Expected score < 40, got {score}"
    print(f"✓ Low altitude, poor conditions: {score}/100")


def test_score_medium_conditions():
    """Test scoring with medium altitude, duration, and conditions."""
    target = {"max_altitude": 30, "apparent_magnitude": 0.0, "observable_duration_hours": 2}
    conditions = {"cloud_cover": 30, "visibility": 8}
    score = calculate_visibility_score(target, conditions)
    assert 30 <= score <= 90, f"Expected score between 30-90, got {score}"
    print(f"✓ Medium conditions: {score}/100")


def test_score_bright_target():
    """Test that brighter targets get higher scores."""
    conditions = {"cloud_cover": 20, "visibility": 10}
    bright_target = {"max_altitude": 40, "apparent_magnitude": -3.0, "observable_duration_hours": 2}
    dim_target = {"max_altitude": 40, "apparent_magnitude": 2.0, "observable_duration_hours": 2}

    bright_score = calculate_visibility_score(bright_target, conditions)
    dim_score = calculate_visibility_score(dim_target, conditions)

    assert bright_score > dim_score, f"Bright target ({bright_score}) should score higher than dim ({dim_score})"
    print(f"✓ Bright target (mag -3): {bright_score}/100 > Dim target (mag 2): {dim_score}/100")


def test_smooth_brightness_scaling():
    """Test smooth brightness scaling ranks identical targets by magnitude."""
    conditions = {"cloud_cover": 20, "visibility": 10}
    bright_target = {"max_altitude": 40, "apparent_magnitude": -3.0, "observable_duration_hours": 2}
    medium_target = {"max_altitude": 40, "apparent_magnitude": 0.5, "observable_duration_hours": 2}
    dim_target = {"max_altitude": 40, "apparent_magnitude": 2.0, "observable_duration_hours": 2}

    bright_score = calculate_visibility_score(bright_target, conditions)
    medium_score = calculate_visibility_score(medium_target, conditions)
    dim_score = calculate_visibility_score(dim_target, conditions)

    assert bright_score > medium_score > dim_score
    print(f"✓ Smooth brightness scaling: {bright_score} > {medium_score} > {dim_score}")


def test_score_longer_duration_scores_higher():
    """Test that a longer observable duration increases the score."""
    conditions = {"cloud_cover": 10, "visibility": 10}
    long_duration = {"max_altitude": 40, "apparent_magnitude": 0.0, "observable_duration_hours": 6}
    short_duration = {"max_altitude": 40, "apparent_magnitude": 0.0, "observable_duration_hours": 0.5}

    long_score = calculate_visibility_score(long_duration, conditions)
    short_score = calculate_visibility_score(short_duration, conditions)

    assert long_score > short_score, f"Longer duration ({long_score}) should score higher than shorter ({short_score})"
    print(f"✓ Long duration (6h): {long_score}/100 > Short duration (0.5h): {short_score}/100")


def test_score_stays_within_bounds():
    """Test that the score never leaves the 0-100 range even at extremes."""
    conditions = {"cloud_cover": 100, "visibility": 0}
    target = {"max_altitude": 0, "apparent_magnitude": 5.0, "observable_duration_hours": 0}
    score = calculate_visibility_score(target, conditions)
    assert 0 <= score <= 100, f"Expected score within 0-100, got {score}"
    print(f"✓ Extreme low-end conditions stay in bounds: {score}/100")

    conditions = {"cloud_cover": 0, "visibility": 50}
    target = {"max_altitude": 90, "apparent_magnitude": -5.0, "observable_duration_hours": 10}
    score = calculate_visibility_score(target, conditions)
    assert 0 <= score <= 100, f"Expected score within 0-100, got {score}"
    print(f"✓ Extreme high-end conditions stay in bounds: {score}/100")


if __name__ == "__main__":
    print("Running scoring tests...\n")
    test_score_high_altitude_good_conditions()
    test_score_low_altitude_poor_conditions()
    test_score_medium_conditions()
    test_score_bright_target()
    test_smooth_brightness_scaling()
    test_score_longer_duration_scores_higher()
    test_score_stays_within_bounds()
    print("\n✓ All tests passed!")
