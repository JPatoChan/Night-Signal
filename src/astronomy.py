"""Astronomy module for celestial observations."""

from skyfield.api import Topos, load


# Nashville, Tennessee observer location
NASHVILLE = Topos(latitude_degrees=36.1627, longitude_degrees=-86.7816)

# Planet identifiers in Skyfield ephemeris
PLANET_NAMES = ["mercury barycenter", "venus barycenter", "mars barycenter", 
                "jupiter barycenter", "saturn barycenter"]

# Approximate apparent magnitudes (placeholders, not calculated from orbital position)
# These are typical values but vary with Earth-planet distance and phase angle
APPROXIMATE_MAGNITUDES = {
    "mercury barycenter": 0.0,
    "venus barycenter": -4.0,
    "mars barycenter": 0.5,
    "jupiter barycenter": -2.0,
    "saturn barycenter": 0.5
}

# Display names
DISPLAY_NAMES = {
    "mercury barycenter": "Mercury",
    "venus barycenter": "Venus",
    "mars barycenter": "Mars",
    "jupiter barycenter": "Jupiter",
    "saturn barycenter": "Saturn"
}


def get_target_list():
    """Calculate and return observable astronomical targets for Nashville.
    
    Uses Skyfield to calculate current planetary positions and altitudes.
    Only includes planets currently above the horizon (altitude > 0).
    
    Apparent magnitudes are approximate placeholders and do not account for
    orbital distance or phase angle variations.
    
    Returns:
        list: List of dicts with name, altitude (degrees), and apparent magnitude
    """
    try:
        # Load ephemeris data (will be cached after first download)
        ephemeris = load("de421.bsp")
        earth = ephemeris["earth"]
        observer = earth + NASHVILLE
        
        # Get current time
        ts = load.timescale()
        now = ts.now()
        
        targets = []
        
        for planet_id in PLANET_NAMES:
            try:
                # Get planet position
                planet = ephemeris[planet_id]
                astrometric = observer.at(now).observe(planet)
                apparent = astrometric.apparent()
                
                # Get altitude and azimuth in horizontal coordinates
                alt, az, distance = apparent.altaz()
                altitude_degrees = alt.degrees
                
                # Only include planets above horizon
                if altitude_degrees > 0:
                    targets.append({
                        "name": DISPLAY_NAMES[planet_id],
                        "altitude": round(altitude_degrees, 2),
                        "apparent_magnitude": APPROXIMATE_MAGNITUDES[planet_id]
                    })
            except Exception as e:
                # Print warning but continue to next planet
                print(f"Warning: Could not calculate position for {DISPLAY_NAMES[planet_id]}: {e}")
                continue
        
        return targets
        
    except Exception as e:
        raise Exception(f"Failed to calculate planetary positions: {e}")
