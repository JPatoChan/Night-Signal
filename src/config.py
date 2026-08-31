"""Shared location configuration for Night Signal."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    name: str
    latitude: float
    longitude: float
    timezone: str


LOCATION = Location(
    name="Nashville, Tennessee",
    latitude=36.1627,
    longitude=-86.7816,
    timezone="America/Chicago",
)