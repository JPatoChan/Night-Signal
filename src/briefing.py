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
            "score": score
        })
    
    # Sort by score descending
    scored_targets.sort(key=lambda x: x["score"], reverse=True)
    
    # Build report
    report = f"\nTonight's conditions: {condition_quality}\n\n"
    
    if scored_targets:
        priority = scored_targets[0]
        report += f"Priority target: {priority['name']}\n"
        report += f"Visibility score: {priority['score']}/100\n"
    
    if len(scored_targets) > 1:
        secondary = scored_targets[1]
        report += f"\nSecondary target: {secondary['name']}\n"
        report += f"Visibility score: {secondary['score']}/100\n"
    
    return report
