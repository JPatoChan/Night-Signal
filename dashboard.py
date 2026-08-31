"""Night Signal Dashboard - A cute space-themed viewer for observation reports."""

import streamlit as st
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from weather import get_observing_conditions
from astronomy import get_target_list, get_observing_window
from scoring import calculate_visibility_score


# Custom CSS for dark space theme
def set_custom_theme():
    """Apply custom CSS styling for space theme."""
    st.markdown("""
    <style>
    /* Import Montserrat font family from Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800&display=swap');
    
    /* Dark space background */
    .stApp {
        background: linear-gradient(135deg, #0a0e27 0%, #16213e 100%);
        color: #e0e6ff;
        font-family: 'Montserrat', sans-serif;
    }
    
    /* Main container */
    [data-testid="stMainBlockContainer"] {
        padding: 2rem;
        background: transparent;
    }
    
    /* Headers and text - Montserrat for all */
    h1, h2, h3 {
        color: #b4d7ff;
        text-shadow: 0 0 10px rgba(180, 215, 255, 0.3);
        font-family: 'Montserrat', sans-serif;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    
    /* Body text - Montserrat */
    p, span, div {
        font-family: 'Montserrat', sans-serif;
    }
    
    /* Custom card styling using columns */
    .stContainer {
        background-color: rgba(22, 33, 62, 0.6);
        border: 1px solid rgba(180, 215, 255, 0.2);
        border-radius: 10px;
        padding: 1rem;
        backdrop-filter: blur(10px);
        font-family: 'Montserrat', sans-serif;
    }
    
    /* Button styling - Montserrat */
    .stButton > button {
        background: linear-gradient(90deg, #6366f1 0%, #a78bfa 100%);
        color: white;
        border: 1px solid rgba(180, 215, 255, 0.3);
        border-radius: 8px;
        font-weight: 600;
        font-family: 'Montserrat', sans-serif;
        text-shadow: 0 0 5px rgba(99, 102, 241, 0.5);
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        box-shadow: 0 0 20px rgba(99, 102, 241, 0.8);
        transform: scale(1.05);
    }
    
    /* Metric cards - Montserrat for labels and values */
    .metric-card {
        background-color: rgba(99, 102, 241, 0.1);
        border: 1px solid rgba(167, 139, 250, 0.3);
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        backdrop-filter: blur(10px);
        text-align: center;
        font-family: 'Montserrat', sans-serif;
    }
    
    /* Priority target highlight - Montserrat for all */
    .priority-card {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(167, 139, 250, 0.15) 100%);
        border: 2px solid #a78bfa;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 0 20px rgba(167, 139, 250, 0.2);
        backdrop-filter: blur(10px);
        font-family: 'Montserrat', sans-serif;
    }
    
    .priority-card > div:first-child {
        font-family: 'Montserrat', sans-serif;
        font-weight: 700;
    }
    
    .priority-card > div:nth-child(2) {
        font-family: 'Montserrat', sans-serif;
        font-weight: 700;
    }
    
    .priority-card > div:nth-child(n+3) {
        font-family: 'Montserrat', sans-serif;
    }
    
    /* Target list items - Montserrat */
    .target-item {
        background-color: rgba(34, 211, 238, 0.08);
        border-left: 3px solid #22d3ee;
        border-radius: 4px;
        padding: 1rem;
        margin: 0.5rem 0;
        font-family: 'Montserrat', sans-serif;
    }
    
    /* Conditions display */
    .condition-excellent {
        color: #4ade80;
        text-shadow: 0 0 10px rgba(74, 222, 128, 0.5);
        font-family: 'Montserrat', sans-serif;
        font-weight: 600;
    }
    
    .condition-good {
        color: #60a5fa;
        text-shadow: 0 0 10px rgba(96, 165, 250, 0.5);
        font-family: 'Montserrat', sans-serif;
        font-weight: 600;
    }
    
    .condition-poor {
        color: #f87171;
        text-shadow: 0 0 10px rgba(248, 113, 113, 0.5);
        font-family: 'Montserrat', sans-serif;
        font-weight: 600;
    }
    
    /* Sparkle/star decorations - Montserrat */
    .stars {
        color: #fde047;
        text-shadow: 0 0 5px rgba(253, 224, 71, 0.6);
        font-family: 'Montserrat', sans-serif;
        font-weight: 700;
    }
    
    /* Caption and subtitle - Montserrat */
    .stCaption {
        color: #a0aec0;
        font-style: italic;
        font-family: 'Montserrat', sans-serif;
    }
    </style>
    """, unsafe_allow_html=True)


def render_weather_section(conditions):
    """Render the weather conditions section."""
    st.markdown("### 🌌 Tonight's Conditions")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 0.8rem; color: #a0aec0;">CLOUD COVER</div>
            <div style="font-size: 1.5rem; color: #fde047; font-weight: bold;">{conditions['cloud_cover']:.0f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 0.8rem; color: #a0aec0;">VISIBILITY</div>
            <div style="font-size: 1.5rem; color: #60a5fa; font-weight: bold;">{conditions['visibility']:.1f} km</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 0.8rem; color: #a0aec0;">TEMPERATURE</div>
            <div style="font-size: 1.5rem; color: #f0abfc; font-weight: bold;">{conditions['temperature']:.1f}°C</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        # Determine condition quality
        cloud_cover = conditions.get("cloud_cover", 0)
        if cloud_cover < 20:
            condition = "EXCELLENT"
            color = "condition-excellent"
        elif cloud_cover < 50:
            condition = "GOOD"
            color = "condition-good"
        else:
            condition = "POOR"
            color = "condition-poor"
        
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 0.8rem; color: #a0aec0;">CONDITIONS</div>
            <div style="font-size: 1.5rem; font-weight: bold;" class="{color}">{condition}</div>
        </div>
        """, unsafe_allow_html=True)


def render_targets_section(conditions, targets, window):
    """Render the targets section with priority target and list."""
    st.markdown("### 🛸 Transmission Targets")
    
    if window.get("evening_twilight_end") and window.get("morning_twilight_begin"):
        sunset_line = f"Sunset: <span style=\"color: #b4d7ff;\">{window['sunset']}</span> | " if window.get("sunset") else ""
        st.markdown(f"""
        <div style="font-size: 0.9rem; color: #a0aec0; margin-bottom: 1rem;">
            {sunset_line}Dark observing window: <span style="color: #b4d7ff;">{window['evening_twilight_end']}</span> → <span style="color: #b4d7ff;">{window['morning_twilight_begin']}</span>
        </div>
        """, unsafe_allow_html=True)

    if not targets:
        st.warning("⚠️ No suspicious extraterrestrial activity detected. No planets are observable during tonight's dark window.")
        return
    
    if conditions is not None:
        scored_targets = []
        for target in targets:
            score = calculate_visibility_score(target, conditions)
            scored_targets.append({
                **target,
                "visibility_score": score
            })
        scored_targets.sort(key=lambda target: target["visibility_score"], reverse=True)
    else:
        scored_targets = targets

    # Show priority target only when weather-dependent scores are available
    if conditions is not None and scored_targets:
        priority = scored_targets[0]
        st.markdown(f"""
        <div class="priority-card">
            <div style="font-size: 0.9rem; color: #a78bfa; text-transform: uppercase; letter-spacing: 2px;">📡 Priority Transmission</div>
            <div style="font-size: 2rem; color: #fde047; font-weight: bold; margin: 0.5rem 0;">{priority['name']}</div>
            <div style="font-size: 1.2rem; color: #b4d7ff;">
                Visibility: <span style="color: #4ade80; font-weight: bold;">{priority['visibility_score']}/100</span>
            </div>
            <div style="font-size: 0.9rem; color: #a0aec0; margin-top: 0.5rem;">
                Best viewing time: {priority['best_viewing_time']} | Max altitude: {priority['max_altitude']}°
            </div>
            <div style="font-size: 0.9rem; color: #a0aec0;">
                Observable for: {priority['observable_duration_hours']} hrs | Magnitude: {priority['apparent_magnitude']}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Show all targets
    st.markdown("#### All Observable Targets")
    for target in scored_targets:
        score_display = (
            f"{target['visibility_score']}/100"
            if conditions is not None
            else "Visibility score unavailable"
        )
        st.markdown(f"""
        <div class="target-item">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="font-size: 1.1rem; color: #b4d7ff; font-weight: bold;">✦ {target['name']}</span>
                </div>
                <div style="text-align: right;">
                    <span style="color: #4ade80; font-weight: bold; font-size: 1rem;">{score_display}</span>
                </div>
            </div>
            <div style="font-size: 0.85rem; color: #a0aec0; margin-top: 0.3rem;">
                Best viewing time: {target['best_viewing_time']} | Max altitude: {target['max_altitude']}°
            </div>
            <div style="font-size: 0.85rem; color: #a0aec0;">
                Observable for: {target['observable_duration_hours']} hrs | Magnitude: {target['apparent_magnitude']}
            </div>
        </div>
        """, unsafe_allow_html=True)


def main():
    """Main dashboard application."""
    # Page config
    st.set_page_config(
        page_title="Night Signal",
        page_icon="🌌",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Set custom theme
    set_custom_theme()
    
    # Header
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <div style="font-size: 3rem; margin-bottom: 0.5rem;">🌌 Night Signal</div>
        <div style="font-size: 1.2rem; color: #60a5fa;">Nashville, Tennessee</div>
        <div style="font-size: 0.95rem; color: #a0aec0; margin-top: 0.5rem; font-style: italic;">Listening to the sky...</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Status indicator
    st.markdown('<div class="stars">✦ Night Signal online ✦</div>', unsafe_allow_html=True)
    
    # Refresh button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Refresh Signal", use_container_width=True):
            st.rerun()
    
    st.divider()
    
    try:
        with st.spinner("📡 Listening to the sky..."):
            targets = get_target_list()
            window = get_observing_window()

        try:
            conditions = get_observing_conditions()
        except Exception as error:
            conditions = None
            st.warning(f"Weather signal unavailable. Astronomy data is still available. ({error})")

        if conditions is not None:
            render_weather_section(conditions)
            st.divider()
        render_targets_section(conditions, targets, window)

        st.markdown("""
        ---
        <div style="text-align: center; font-size: 0.85rem; color: #7c8ba8;">
            <div class="stars">✦ ✦ ✦</div>
            <p>Night Signal • Powered by Skyfield & Open-Meteo</p>
        </div>
        """, unsafe_allow_html=True)
        
    except Exception as e:
        st.error(f"""
        ⚠️ **Transmission Error**
        
        Could not retrieve signal data: {str(e)}
        
        Please check your internet connection and try refreshing.
        """)


if __name__ == "__main__":
    main()
