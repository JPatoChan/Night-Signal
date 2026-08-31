"""Briefing module for observation reports."""

from scoring import calculate_visibility_score


def generate_report(conditions, targets):
    """Generate a Night Signal briefing report.
    
    Args:
        conditions (dict): Observing conditions
        targets (list): List of astronomical targets
    
    Returns:
        str: Formatted briefing report
    """
    # Determine condition quality
    cloud_cover = conditions.get("cloud_cover", 0)
    if cloud_cover < 20:
        condition_quality = "Excellent"
    elif cloud_cover < 50:
        condition_quality = "Good"
    else:
        condition_quality = "Poor"

    # Score all targets
    scored_targets = []
    for target in targets:
        score = calculate_visibility_score(target, conditions)
        scored_targets.append({
            "name": target["name"],
            "score": score,
            "best_viewing_time": target.get("best_viewing_time"),
            "max_altitude": target.get("max_altitude"),
            "observable_duration_hours": target.get("observable_duration_hours")
        })
    
    # Sort by score descending
    scored_targets.sort(key=lambda x: x["score"], reverse=True)
    
    # Build report
    report = f"\nTonight's conditions: {condition_quality}\n\n"
    
    if not scored_targets:
        report += "No suspicious extraterrestrial activity detected.\n"
        report += "No planets are observable during tonight's dark window.\n"
        return report

    priority = scored_targets[0]
    report += f"Priority target: {priority['name']}\n"
    report += f"Visibility score: {priority['score']}/100\n"
    report += f"Best viewing time: {priority['best_viewing_time']}\n"
    report += f"Max altitude: {priority['max_altitude']}°\n"
    report += f"Observable duration: {priority['observable_duration_hours']} hours\n"
    
    if len(scored_targets) > 1:
        secondary = scored_targets[1]
        report += f"\nSecondary target: {secondary['name']}\n"
        report += f"Visibility score: {secondary['score']}/100\n"
        report += f"Best viewing time: {secondary['best_viewing_time']}\n"
        report += f"Max altitude: {secondary['max_altitude']}°\n"
        report += f"Observable duration: {secondary['observable_duration_hours']} hours\n"
    
    return report
