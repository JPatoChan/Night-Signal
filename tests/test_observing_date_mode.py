"""Tests for Night Signal's Tonight / See Another Date sidebar controls (Phase 2B)."""

import sys
from pathlib import Path
from datetime import date

# Add repo root (for dashboard.py) and src/ (for config.Location)
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import dashboard


def test_tonight_mode_resolves_to_no_explicit_target_date():
    """Tonight mode should always resolve to None, regardless of any
    leftover selected_date value from a prior "See Another Date" session."""
    assert dashboard.resolve_target_date("Tonight", None) is None
    assert dashboard.resolve_target_date("Tonight", date(2026, 10, 21)) is None
    print("✓ Tonight mode resolves to no explicit target date")


def test_see_another_date_mode_returns_the_chosen_date():
    """See Another Date mode should return exactly the selected date."""
    chosen = date(2026, 10, 21)
    assert dashboard.resolve_target_date("See Another Date", chosen) == chosen
    print("✓ See Another Date mode returns the chosen date")


def test_see_another_date_mode_with_no_selection_yet_resolves_to_none():
    """If the date picker hasn't produced a value yet, gracefully fall
    back to None rather than crashing or fabricating a date."""
    assert dashboard.resolve_target_date("See Another Date", None) is None
    print("✓ See Another Date mode with no selection yet resolves to None")


def test_formatted_selected_date_label():
    """format_selected_date and get_observing_plan_label should produce
    the documented readable format."""
    target_date = date(2026, 10, 21)
    assert dashboard.format_selected_date(target_date) == "October 21, 2026"
    assert dashboard.get_observing_plan_label(target_date) == "Observing plan for October 21, 2026"
    print("✓ Formatted selected-date label matches the expected format")


def test_alternate_date_mode_does_not_use_live_weather():
    """should_use_live_weather must be False whenever a target_date is
    set, and True only for Tonight (target_date is None)."""
    assert dashboard.should_use_live_weather(None) is True
    assert dashboard.should_use_live_weather(date(2026, 10, 21)) is False
    print("✓ Alternate-date mode does not use current weather for target scoring")


def test_switching_modes_preserves_sane_state():
    """Simulate a user flipping Tonight -> See Another Date -> Tonight;
    each resolution should be correct and independent of prior calls."""
    chosen = date(2026, 10, 21)

    # Start on Tonight
    assert dashboard.resolve_target_date("Tonight", None) is None

    # Switch to See Another Date and pick a date
    assert dashboard.resolve_target_date("See Another Date", chosen) == chosen

    # Switch back to Tonight; the leftover chosen date must not leak through
    assert dashboard.resolve_target_date("Tonight", chosen) is None
    print("✓ Switching modes preserves sane state with no leakage between modes")


def test_lunar_horizon_wording_in_tonight_mode():
    """Tonight mode should keep the original 'tonight's dark window' wording."""
    assert dashboard.format_lunar_horizon_line(True, None) == "Above horizon during tonight's dark window"
    assert dashboard.format_lunar_horizon_line(False, None) == "Below horizon during tonight's dark window"
    print("✓ Lunar Signal wording is correct in Tonight mode")


def test_lunar_horizon_wording_in_alternate_date_mode():
    """Alternate-date mode should avoid saying 'tonight' and instead
    reference 'this observing window'."""
    target_date = date(2026, 10, 21)
    assert dashboard.format_lunar_horizon_line(True, target_date) == "Above horizon during this observing window"
    assert dashboard.format_lunar_horizon_line(False, target_date) == "Below horizon during this observing window"
    print("✓ Lunar Signal wording is correct in alternate-date mode")


def test_meteor_status_peak_tonight_in_tonight_mode():
    """Tonight mode should keep displaying 'Peak Tonight' unchanged."""
    assert dashboard.format_shower_status_for_display("Peak Tonight", None) == "Peak Tonight"
    print("✓ Meteor Signal displays 'Peak Tonight' in Tonight mode")


def test_meteor_status_peak_night_in_alternate_date_mode():
    """Alternate-date mode should display 'Peak Night' instead of 'Peak
    Tonight', while other statuses pass through unchanged (display only;
    classification itself is untouched)."""
    target_date = date(2026, 10, 21)
    assert dashboard.format_shower_status_for_display("Peak Tonight", target_date) == "Peak Night"
    assert dashboard.format_shower_status_for_display("Near Peak", target_date) == "Near Peak"
    assert dashboard.format_shower_status_for_display("Active", target_date) == "Active"
    print("✓ Meteor Signal displays 'Peak Night' in alternate-date mode")


def test_meteor_signal_no_longer_depends_on_sidebar_rendering():
    """Meteor Signal should now be rendered via a main-dashboard function,
    not the old sidebar-specific one."""
    assert hasattr(dashboard, "render_meteor_main")
    assert not hasattr(dashboard, "render_meteor_sidebar")
    print("✓ Meteor Signal no longer depends on sidebar rendering")


if __name__ == "__main__":
    print("Running Tonight / See Another Date tests...\n")
    test_tonight_mode_resolves_to_no_explicit_target_date()
    test_see_another_date_mode_returns_the_chosen_date()
    test_see_another_date_mode_with_no_selection_yet_resolves_to_none()
    test_formatted_selected_date_label()
    test_alternate_date_mode_does_not_use_live_weather()
    test_switching_modes_preserves_sane_state()
    test_lunar_horizon_wording_in_tonight_mode()
    test_lunar_horizon_wording_in_alternate_date_mode()
    test_meteor_status_peak_tonight_in_tonight_mode()
    test_meteor_status_peak_night_in_alternate_date_mode()
    test_meteor_signal_no_longer_depends_on_sidebar_rendering()
    print("\n✓ All tests passed!")
