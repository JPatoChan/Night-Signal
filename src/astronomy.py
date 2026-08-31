"""Astronomy module for celestial observations."""


def get_target_list():
    """Return sample astronomical targets.
    
    Returns:
        list: List of dicts with name, altitude (degrees), and apparent magnitude
    """
    return [
        {
            "name": "Jupiter",
            "altitude": 45,
            "apparent_magnitude": -2.5
        },
        {
            "name": "Saturn",
            "altitude": 30,
            "apparent_magnitude": 0.5
        }
    ]
