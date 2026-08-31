"""Tests for the scoring module."""

import sys
from pathlib import Path

# Add src to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scoring import calculate_visibility_score


def test_score_high_altitude_good_conditions():
    """Test scoring with high altitude and good conditions."""
    target = {"altitude": 60, "apparent_magnitude": -2.0}
    conditions = {"cloud_cover": 10, "visibility": 10}
    score = calculate_visibility_score(target, conditions)
    assert score > 80, f"Expected score > 80, got {score}"
    print(f"✓ High altitude, good conditions: {score}/100")


def test_score_low_altitude_poor_conditions():
    """Test scoring with low altitude and poor conditions."""
    target = {"altitude": 15, "apparent_magnitude": 2.0}
    conditions = {"cloud_cover": 80, "visibility": 2}
    score = calculate_visibility_score(target, conditions)
    assert score < 30, f"Expected score < 30, got {score}"
    print(f"✓ Low altitude, poor conditions: {score}/100")


def test_score_medium_conditions():
    """Test scoring with medium conditions."""
    target = {"altitude": 30, "apparent_magnitude": 0.0}
    conditions = {"cloud_cover": 30, "visibility": 8}
    score = calculate_visibility_score(target, conditions)
    assert 30 <= score <= 80, f"Expected score between 30-80, got {score}"
    print(f"✓ Medium conditions: {score}/100")


def test_score_bright_target():
    """Test that brighter targets get higher scores."""
    conditions = {"cloud_cover": 20, "visibility": 10}
    bright_target = {"altitude": 40, "apparent_magnitude": -3.0}
    dim_target = {"altitude": 40, "apparent_magnitude": 2.0}
    
    bright_score = calculate_visibility_score(bright_target, conditions)
    dim_score = calculate_visibility_score(dim_target, conditions)
    
    assert bright_score > dim_score, f"Bright target ({bright_score}) should score higher than dim ({dim_score})"
    print(f"✓ Bright target (mag -3): {bright_score}/100 > Dim target (mag 2): {dim_score}/100")


if __name__ == "__main__":
    print("Running scoring tests...\n")
    test_score_high_altitude_good_conditions()
    test_score_low_altitude_poor_conditions()
    test_score_medium_conditions()
    test_score_bright_target()
    print("\n✓ All tests passed!")
