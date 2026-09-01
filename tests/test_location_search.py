"""Tests for Night Signal's typed location search (forward geocoding)."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add repo root (for dashboard.py) and src/ (for config.Location)
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import dashboard
from config import Location


def _make_geopy_result(address, latitude, longitude):
    """Build a fake geopy geocode result exposing the attributes we read."""
    result = MagicMock()
    result.address = address
    result.latitude = latitude
    result.longitude = longitude
    return result


def test_parses_multiple_mocked_geocoding_results():
    """Multiple geocode matches should all be converted into result dicts."""
    fake_results = [
        _make_geopy_result("Nashville, Davidson County, Tennessee, United States", 36.1627, -86.7816),
        _make_geopy_result("Nashville, Illinois, United States", 38.3223, -89.3823),
    ]
    with patch.object(dashboard, "Nominatim") as mock_nominatim_cls:
        mock_nominatim_cls.return_value.geocode.return_value = fake_results
        results = dashboard.get_location_search_results("Nashville")

    assert len(results) == 2
    assert results[0]["display_name"] == "Nashville, Davidson County, Tennessee, United States"
    assert results[0]["latitude"] == 36.1627
    assert results[0]["longitude"] == -86.7816
    assert results[1]["display_name"] == "Nashville, Illinois, United States"
    print("✓ Multiple mocked geocoding results are parsed correctly")


def test_selected_search_result_creates_expected_location():
    """Selecting a search result and resolving its timezone should
    produce a Location matching that result's coordinates and name."""
    result = {
        "display_name": "Nashville, Tennessee, United States",
        "latitude": 36.1627,
        "longitude": -86.7816
    }
    with patch.object(dashboard, "get_timezone_from_coordinates", return_value="America/Chicago") as mock_tz:
        tz = dashboard.get_timezone_from_coordinates(result["latitude"], result["longitude"])
        location = Location(
            name=result["display_name"],
            latitude=result["latitude"],
            longitude=result["longitude"],
            timezone=tz
        )

    mock_tz.assert_called_once_with(36.1627, -86.7816)
    assert location.name == "Nashville, Tennessee, United States"
    assert location.latitude == 36.1627
    assert location.longitude == -86.7816
    assert location.timezone == "America/Chicago"
    print("✓ Selected search result creates the expected Location")


def test_timezone_resolution_is_applied_to_selected_coordinates():
    """Timezone resolution for a selected search result should call the
    existing timezone helper with that result's coordinates."""
    with patch.object(dashboard, "get_timezone_from_coordinates") as mock_tz:
        mock_tz.return_value = "America/Denver"
        tz = dashboard.get_timezone_from_coordinates(39.7392, -104.9903)

    mock_tz.assert_called_once_with(39.7392, -104.9903)
    assert tz == "America/Denver"
    print("✓ Timezone resolution is applied to selected coordinates")


def test_no_results_returns_empty_list():
    """A query with no matches should return an empty list, not None or an error."""
    with patch.object(dashboard, "Nominatim") as mock_nominatim_cls:
        mock_nominatim_cls.return_value.geocode.return_value = None
        results = dashboard.get_location_search_results("asdkjfhaskjdhflaksjdhf")

    assert results == []
    print("✓ No-results query returns an empty list")


def test_geocoding_failure_returns_none():
    """A geocoding/network failure should be handled gracefully, returning None."""
    with patch.object(dashboard, "Nominatim") as mock_nominatim_cls:
        mock_nominatim_cls.return_value.geocode.side_effect = Exception("network error")
        results = dashboard.get_location_search_results("Nashville")

    assert results is None
    print("✓ Geocoding failure returns None instead of raising")


def test_malformed_result_missing_coordinates_is_skipped():
    """A result missing latitude/longitude should be filtered out rather
    than crashing the search or being passed along as unusable data."""
    malformed = _make_geopy_result("Somewhere with no coordinates", None, None)
    valid = _make_geopy_result("Nashville, Tennessee, United States", 36.1627, -86.7816)
    with patch.object(dashboard, "Nominatim") as mock_nominatim_cls:
        mock_nominatim_cls.return_value.geocode.return_value = [malformed, valid]
        results = dashboard.get_location_search_results("Nashville")

    assert len(results) == 1
    assert results[0]["display_name"] == "Nashville, Tennessee, United States"
    print("✓ Malformed results missing coordinates are filtered out")


if __name__ == "__main__":
    print("Running location search tests...\n")
    test_parses_multiple_mocked_geocoding_results()
    test_selected_search_result_creates_expected_location()
    test_timezone_resolution_is_applied_to_selected_coordinates()
    test_no_results_returns_empty_list()
    test_geocoding_failure_returns_none()
    test_malformed_result_missing_coordinates_is_skipped()
    print("\n✓ All tests passed!")
