"""Weather module for sky conditions monitoring."""


def get_observing_conditions():
    """Return sample observing conditions.
    
    Returns:
        dict: Contains cloud_cover (%), visibility (km), and temperature (°C)
    """
    return {
        "cloud_cover": 10,
        "visibility": 10,
        "temperature": -5
    }
