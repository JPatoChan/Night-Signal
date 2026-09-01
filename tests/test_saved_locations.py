"""Tests for Night Signal's saved-location logic (pure session-state helpers)."""

import sys
from pathlib import Path

# Add repo root (for dashboard.py) and src/ (for config.Location)
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import dashboard
from config import Location, NASHVILLE, DENVER, LOS_ANGELES


def test_save_location_adds_new_entry():
    """Saving a location for the first time should add it and report success."""
    updated, was_added = dashboard.add_saved_location([], NASHVILLE)
    assert was_added is True
    assert len(updated) == 1
    assert updated[0]["name"] == NASHVILLE.name
    assert updated[0]["latitude"] == NASHVILLE.latitude
    assert updated[0]["longitude"] == NASHVILLE.longitude
    assert updated[0]["timezone"] == NASHVILLE.timezone
    print("✓ Saving a new location adds an entry")


def test_duplicate_prevention_based_on_coordinates():
    """Saving the same coordinates twice should not create a duplicate,
    even if the display name differs."""
    saved_once, _ = dashboard.add_saved_location([], NASHVILLE)

    # Same coordinates, different display name (e.g. from a different source)
    renamed = Location(
        name="Nashville, TN (from search)",
        latitude=NASHVILLE.latitude,
        longitude=NASHVILLE.longitude,
        timezone=NASHVILLE.timezone
    )
    saved_twice, was_added = dashboard.add_saved_location(saved_once, renamed)

    assert was_added is False
    assert len(saved_twice) == 1
    assert saved_twice[0]["name"] == NASHVILLE.name  # original entry untouched
    print("✓ Duplicate prevention is based on coordinates, not name")


def test_activating_saved_location_reconstructs_location():
    """location_from_saved should rebuild a Location matching the saved fields."""
    saved_locations, _ = dashboard.add_saved_location([], DENVER)
    location = dashboard.location_from_saved(saved_locations[0])

    assert isinstance(location, Location)
    assert location.name == DENVER.name
    assert location.latitude == DENVER.latitude
    assert location.longitude == DENVER.longitude
    assert location.timezone == DENVER.timezone
    print("✓ Activating a saved location reconstructs the expected Location")


def test_deleting_one_saved_location_does_not_affect_others():
    """Removing one saved location should leave the others untouched."""
    saved_locations, _ = dashboard.add_saved_location([], NASHVILLE)
    saved_locations, _ = dashboard.add_saved_location(saved_locations, DENVER)
    saved_locations, _ = dashboard.add_saved_location(saved_locations, LOS_ANGELES)

    updated = dashboard.remove_saved_location(saved_locations, DENVER.latitude, DENVER.longitude)

    remaining_names = {entry["name"] for entry in updated}
    assert len(updated) == 2
    assert remaining_names == {NASHVILLE.name, LOS_ANGELES.name}
    print("✓ Deleting one saved location does not affect the others")


def test_deleting_active_saved_location_safely():
    """Deleting the currently active saved location should clear the
    active selection rather than leaving a dangling/stale reference."""
    saved_locations, _ = dashboard.add_saved_location([], NASHVILLE)
    active = saved_locations[0]

    updated_active = dashboard.clear_active_saved_location_if_matching(
        active, NASHVILLE.latitude, NASHVILLE.longitude
    )
    assert updated_active is None

    # A different active location should be unaffected by removing Nashville
    other_active = {"name": DENVER.name, "latitude": DENVER.latitude,
                     "longitude": DENVER.longitude, "timezone": DENVER.timezone}
    unaffected = dashboard.clear_active_saved_location_if_matching(
        other_active, NASHVILLE.latitude, NASHVILLE.longitude
    )
    assert unaffected == other_active
    print("✓ Deleting the active saved location clears it safely without affecting others")


if __name__ == "__main__":
    print("Running saved-location tests...\n")
    test_save_location_adds_new_entry()
    test_duplicate_prevention_based_on_coordinates()
    test_activating_saved_location_reconstructs_location()
    test_deleting_one_saved_location_does_not_affect_others()
    test_deleting_active_saved_location_safely()
    print("\n✓ All tests passed!")
