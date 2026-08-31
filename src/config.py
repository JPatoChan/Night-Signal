"""Shared location configuration for Night Signal."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    name: str
    latitude: float
    longitude: float
    timezone: str


NASHVILLE = Location(
    name="Nashville, Tennessee",
    latitude=36.1627,
    longitude=-86.7816,
    timezone="America/Chicago",
)

NEW_YORK = Location(
    name="New York, New York",
    latitude=40.7128,
    longitude=-74.0060,
    timezone="America/New_York",
)

DENVER = Location(
    name="Denver, Colorado",
    latitude=39.7392,
    longitude=-104.9903,
    timezone="America/Denver",
)

LOS_ANGELES = Location(
    name="Los Angeles, California",
    latitude=34.0522,
    longitude=-118.2437,
    timezone="America/Los_Angeles",
)

# Preset locations available for selection
PRESET_LOCATIONS = [NASHVILLE, NEW_YORK, DENVER, LOS_ANGELES]

# Default location used when none is explicitly selected
DEFAULT_LOCATION = NASHVILLE