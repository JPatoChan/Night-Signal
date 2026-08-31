"""Scoring module for evaluating observation quality."""


def calculate_visibility_score(target, conditions):
    """Calculate a visibility score for a target based on conditions.
    
    Args:
        target (dict): Target with 'altitude' and 'apparent_magnitude'
        conditions (dict): Observing conditions with 'cloud_cover' and 'visibility'
    
    Returns:
        int: Visibility score from 0 to 100
    """
    # Base score from altitude (higher is better, max at 60+ degrees)
    altitude = target.get("altitude", 0)
    altitude_score = min(100, (altitude / 60) * 100)
    
    # Reduce by cloud cover impact
    cloud_cover = conditions.get("cloud_cover", 0)
    cloud_penalty = (cloud_cover / 100) * 30
    
    # Reduce by visibility impact (visibility < 5km is bad)
    visibility = conditions.get("visibility", 0)
    visibility_penalty = max(0, (5 - visibility) / 5 * 20)
    
    # Brightness bonus (negative magnitude = brighter)
    apparent_magnitude = target.get("apparent_magnitude", 0)
    brightness_bonus = max(0, -apparent_magnitude * 3)
    
    score = altitude_score - cloud_penalty - visibility_penalty + brightness_bonus
    return max(0, min(100, int(score)))
