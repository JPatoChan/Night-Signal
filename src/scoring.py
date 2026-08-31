"""Scoring module for evaluating observation quality."""


# Weighted point budget that sums to 100 when conditions are ideal
PRESENCE_BONUS = 25
MAX_ALTITUDE_POINTS = 40
MAX_DURATION_POINTS = 20
MAX_BRIGHTNESS_POINTS = 15
MAX_CLOUD_PENALTY = 20
MAX_VISIBILITY_PENALTY = 15

# Reference values used to normalize each component
FULL_DURATION_HOURS = 6
MIN_GOOD_VISIBILITY_KM = 5


def calculate_visibility_score(target, conditions):
    """Calculate a nighttime visibility score for a target.

    Args:
        target (dict): Target with 'max_altitude' (degrees),
            'observable_duration_hours', and 'apparent_magnitude'
        conditions (dict): Observing conditions with 'cloud_cover' and 'visibility'

    Returns:
        int: Visibility score from 0 to 100
    """
    # Support both the new "max_altitude" key and the legacy "altitude" key
    max_altitude = target.get("max_altitude", target.get("altitude", 0))
    observable_duration_hours = target.get("observable_duration_hours", 0)
    apparent_magnitude = target.get("apparent_magnitude", 0)

    cloud_cover = conditions.get("cloud_cover", 0)
    visibility = conditions.get("visibility", 0)

    # Being observable at all during the window earns a baseline score
    presence_bonus = PRESENCE_BONUS

    # Higher peak altitude is better, capped at 90 degrees (zenith)
    altitude_component = min(MAX_ALTITUDE_POINTS, (max_altitude / 90) * MAX_ALTITUDE_POINTS)

    # Longer observable windows are better, capped at FULL_DURATION_HOURS
    duration_component = min(MAX_DURATION_POINTS, (observable_duration_hours / FULL_DURATION_HOURS) * MAX_DURATION_POINTS)

    # Magnitudes from +2 to -4 scale linearly from zero to full brightness points
    brightness_scale = (2 - apparent_magnitude) / 6
    brightness_component = min(MAX_BRIGHTNESS_POINTS, max(0, brightness_scale * MAX_BRIGHTNESS_POINTS))

    # Cloud cover reduces visibility
    cloud_penalty = (cloud_cover / 100) * MAX_CLOUD_PENALTY

    # Poor atmospheric visibility reduces score
    visibility_penalty = max(0, (MIN_GOOD_VISIBILITY_KM - visibility) / MIN_GOOD_VISIBILITY_KM) * MAX_VISIBILITY_PENALTY

    score = (
        presence_bonus
        + altitude_component
        + duration_component
        + brightness_component
        - cloud_penalty
        - visibility_penalty
    )
    return max(0, min(100, int(round(score))))
