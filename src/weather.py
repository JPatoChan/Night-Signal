"""Weather module for sky conditions monitoring."""

import json
import urllib.request
import urllib.error


# Hard-coded location for forecast (Nashville, Tennessee)
LATITUDE = 36.1627
LONGITUDE = -86.7816


def get_observing_conditions():
    """Fetch current observing conditions from Open-Meteo Forecast API.
    
    Returns:
        dict: Contains cloud_cover (%), visibility (km), and temperature (°C)
        
    Raises:
        Exception: If API request fails or response is malformed
    """
    try:
        # Build API request
        params = {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "current": "cloud_cover,visibility,temperature",
            "timezone": "UTC"
        }
        
        param_string = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"https://api.open-meteo.com/v1/forecast?{param_string}"
        
        # Make HTTP request
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())
        
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
        
    except urllib.error.URLError as e:
        raise Exception(f"Failed to fetch weather data: Network error - {e}")
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse weather data: Invalid JSON - {e}")
    except KeyError as e:
        raise Exception(f"Failed to parse weather data: Missing field - {e}")
    except Exception as e:
        raise Exception(f"Unexpected error fetching weather: {e}")
