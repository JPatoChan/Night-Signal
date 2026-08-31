"""Weather module for sky conditions monitoring."""

import json
import time
import urllib.request
import urllib.error


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
