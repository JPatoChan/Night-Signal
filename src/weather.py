"""Weather module for sky conditions monitoring."""

import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone


class WeatherFetchError(Exception):
    """Raised when Open-Meteo cannot provide current weather data."""


def get_observing_conditions(location):
    """Fetch current observing conditions from Open-Meteo Forecast API.

    Args:
        location (Location): Observer location to fetch conditions for.

    Returns:
        dict: Contains cloud_cover (%), visibility (km), and temperature (°C)
        
    Raises:
        Exception: If API request fails or response is malformed
    """
    try:
        # Build API request
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "current": "cloud_cover,visibility,temperature",
            "timezone": "UTC"
        }
        
        param_string = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"https://api.open-meteo.com/v1/forecast?{param_string}"
        
        for attempt in range(2):
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())
                break
            except (TimeoutError, urllib.error.URLError) as error:
                if attempt == 1:
                    raise WeatherFetchError(
                        f"Failed to fetch weather data after 2 attempts: {error}"
                    ) from error
                time.sleep(1)
        
        # Extract current weather values
        current = data.get("current", {})
        
        cloud_cover = current.get("cloud_cover", 0)
        temperature = current.get("temperature", 0)
        
        # Visibility comes in meters from API, convert to kilometers
        visibility_meters = current.get("visibility", 10000)
        visibility = visibility_meters / 1000  # Convert to km
        
        return {
            "cloud_cover": cloud_cover,
            "visibility": visibility,
            "temperature": temperature
        }
        
    except WeatherFetchError:
        raise
    except urllib.error.URLError as e:
        raise Exception(f"Failed to fetch weather data: Network error - {e}")
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse weather data: Invalid JSON - {e}")
    except KeyError as e:
        raise Exception(f"Failed to parse weather data: Missing field - {e}")
    except Exception as e:
        raise Exception(f"Unexpected error fetching weather: {e}")


def get_hourly_forecast(location):
    """Fetch hourly forecast data from Open-Meteo for the given location.

    Args:
        location (Location): Observer location to fetch forecast for.

    Returns:
        dict: Contains "times" (list of timezone-aware UTC datetimes),
        "cloud_cover" (list of %), "visibility" (list of km), and
        "temperature" (list of °C), aligned by index.

    Raises:
        WeatherFetchError: If the API request fails after retries or the
        response is malformed.
    """
    try:
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "hourly": "cloud_cover,visibility,temperature_2m",
            "timezone": "UTC",
            "forecast_days": 2
        }

        param_string = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"https://api.open-meteo.com/v1/forecast?{param_string}"

        for attempt in range(2):
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())
                break
            except (TimeoutError, urllib.error.URLError) as error:
                if attempt == 1:
                    raise WeatherFetchError(
                        f"Failed to fetch hourly forecast after 2 attempts: {error}"
                    ) from error
                time.sleep(1)

        hourly = data.get("hourly", {})
        raw_times = hourly.get("time", [])
        if not raw_times:
            raise WeatherFetchError("Hourly forecast response contained no timestamps")

        # Open-Meteo returns naive ISO timestamps when timezone=UTC is requested
        times = [datetime.fromisoformat(t).replace(tzinfo=timezone.utc) for t in raw_times]
        cloud_cover = hourly.get("cloud_cover", [])
        temperature = hourly.get("temperature_2m", [])

        # Visibility comes in meters from the API, convert to kilometers
        visibility = [v / 1000 if v is not None else None for v in hourly.get("visibility", [])]

        return {
            "times": times,
            "cloud_cover": cloud_cover,
            "visibility": visibility,
            "temperature": temperature
        }

    except WeatherFetchError:
        raise
    except urllib.error.URLError as e:
        raise WeatherFetchError(f"Failed to fetch hourly forecast: Network error - {e}")
    except json.JSONDecodeError as e:
        raise WeatherFetchError(f"Failed to parse hourly forecast: Invalid JSON - {e}")
    except (KeyError, ValueError) as e:
        raise WeatherFetchError(f"Failed to parse hourly forecast: {e}")


def find_nearest_forecast(forecast, target_time):
    """Find the hourly forecast entry nearest to a target UTC datetime.

    Args:
        forecast (dict): Hourly forecast data from get_hourly_forecast().
        target_time (datetime): Timezone-aware UTC datetime to match, such
            as a target's best_viewing_time_utc.

    Returns:
        dict: Contains cloud_cover, visibility, temperature, and
        forecast_time for the nearest hourly entry, or None if the
        forecast or target_time is unusable, the nearest point is too far
        away, or any required value is missing.
    """
    if not forecast or target_time is None:
        return None

    times = forecast.get("times", [])
    if not times:
        return None

    nearest_index = min(
        range(len(times)),
        key=lambda i: abs((times[i] - target_time).total_seconds())
    )

    # Reject matches too far from target_time to be meaningful for hourly data
    if abs((times[nearest_index] - target_time).total_seconds()) > 90 * 60:
        return None

    cloud_cover = forecast.get("cloud_cover", [])
    visibility = forecast.get("visibility", [])
    temperature = forecast.get("temperature", [])

    if nearest_index >= len(cloud_cover) or nearest_index >= len(visibility) or nearest_index >= len(temperature):
        return None

    nearest_cloud_cover = cloud_cover[nearest_index]
    nearest_visibility = visibility[nearest_index]
    nearest_temperature = temperature[nearest_index]

    if nearest_cloud_cover is None or nearest_visibility is None or nearest_temperature is None:
        return None

    return {
        "cloud_cover": nearest_cloud_cover,
        "visibility": nearest_visibility,
        "temperature": nearest_temperature,
        "forecast_time": times[nearest_index]
    }


def get_conditions_for_time(location, target_time, forecast=None):
    """Get forecast conditions nearest to a target UTC datetime.

    Args:
        location (Location): Observer location to fetch forecast for. Only
            used when `forecast` is not already provided.
        target_time (datetime): Timezone-aware UTC datetime to match, such
            as a target's best_viewing_time_utc.
        forecast (dict, optional): Pre-fetched hourly forecast from
            get_hourly_forecast(), to avoid refetching for every target
            scored against the same location.

    Returns:
        dict: Nearest hourly conditions (cloud_cover, visibility,
        temperature, forecast_time), or None if forecast data is
        unavailable. Never fabricates values.
    """
    try:
        if forecast is None:
            forecast = get_hourly_forecast(location)
        return find_nearest_forecast(forecast, target_time)
    except Exception:
        return None
