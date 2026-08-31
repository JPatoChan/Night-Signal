"""Night Signal Dashboard - A cute space-themed viewer for observation reports."""

import streamlit as st
import sys
from pathlib import Path

import folium
from streamlit_folium import st_folium
from timezonefinder import TimezoneFinder
from geopy.geocoders import Nominatim
import logging

# Suppress verbose geopy logging
logging.getLogger('geopy.geocoders').setLevel(logging.WARNING)

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from weather import get_observing_conditions, get_hourly_forecast, get_conditions_for_time
from astronomy import get_target_list, get_observing_window
from scoring import calculate_visibility_score
from config import PRESET_LOCATIONS, DEFAULT_LOCATION, Location


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


def celsius_to_fahrenheit(celsius):
    """Convert a Celsius temperature to Fahrenheit for display."""
    return (celsius * 9 / 5) + 32


def km_to_miles(km):
    """Convert kilometers to miles for display."""
    return km * 0.621371


def get_timezone_from_coordinates(latitude, longitude):
    """Resolve IANA timezone name from latitude/longitude coordinates.

    Args:
        latitude (float): Latitude in decimal degrees.
        longitude (float): Longitude in decimal degrees.

    Returns:
        str: IANA timezone name, or 'UTC' if resolution fails.
    """
    try:
        tf = TimezoneFinder()
        tz = tf.timezone_at(lat=latitude, lng=longitude)
        return tz if tz else "UTC"
    except Exception:
        return "UTC"


def get_location_name_from_coordinates(latitude, longitude):
    """Resolve human-readable location name from coordinates using reverse geocoding.

    Uses OpenStreetMap Nominatim service. Prefers city/town/village/municipality
    names, includes state/region when available, and falls back gracefully.

    Args:
        latitude (float): Latitude in decimal degrees.
        longitude (float): Longitude in decimal degrees.

    Returns:
        str: Human-readable location name, or fallback if resolution fails.
    """
    try:
        # Initialize Nominatim geocoder with Night Signal user agent (required by OSM)
        geolocator = Nominatim(user_agent="night-signal-observatory")

        # Reverse geocode with timeout to avoid hanging Streamlit
        location = geolocator.reverse(f"{latitude}, {longitude}", timeout=5, language="en")

        if not location or not location.raw:
            return f"Selected location ({latitude:.4f}, {longitude:.4f})"

        # Use Nominatim's structured address fields rather than splitting the
        # free-form display string, so a street/neighborhood/county isn't
        # mistaken for the locality name
        address = location.raw.get("address", {})

        # Prefer the most specific locality field available
        locality = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
            or address.get("hamlet")
            or address.get("suburb")
        )

        # Prefer state, fall back to region or state_district
        region = address.get("state") or address.get("region") or address.get("state_district")

        country = address.get("country")

        if locality and region:
            return f"{locality}, {region}"
        if locality:
            return locality
        if region and country:
            return f"{region}, {country}"
        if country:
            return country

        # Ultimate fallback: coordinates
        return f"Selected location ({latitude:.4f}, {longitude:.4f})"

    except Exception:
        # Fail gracefully: astronomy/weather still work using coordinates
        return f"Selected location ({latitude:.4f}, {longitude:.4f})"


def render_map_picker():
    """Render an interactive map for location selection.

    Returns:
        dict: Map data from the last interaction, or None if no interaction.
    """
    st.markdown("### 🗺️ Click a location on the map")

    # Create the map with dark USGS satellite imagery
    center_lat, center_lon = 39.8283, -98.5795  # Center of USA
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=4,
        tiles="USGS.USImagery"
    )

    # Add reference layer with boundaries and place labels on top
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
        attr='Tiles &copy; Esri',
        name='Reference Labels',
        overlay=True,
        control=False,
        opacity=0.7
    ).add_to(m)

    # Add a marker for the current clicked location if available in session
    if "clicked_location" in st.session_state and st.session_state.clicked_location:
        clicked = st.session_state.clicked_location
        folium.Marker(
            location=[clicked["latitude"], clicked["longitude"]],
            popup=f"{clicked['latitude']:.4f}, {clicked['longitude']:.4f}",
            icon=folium.Icon(color="violet", icon="star", prefix="fa")
        ).add_to(m)

    # Render map with responsive width (uses full container width)
    map_data = st_folium(m, width=None, height=500)

    return map_data


def handle_map_click(map_data):
    """Handle map click events and update session state.

    Args:
        map_data (dict): Data from st_folium interaction.

    Returns:
        Location: Temporary Location object from clicked coordinates, or None if no click.
    """
    if map_data and map_data.get("last_clicked"):
        clicked = map_data["last_clicked"]
        lat = clicked["lat"]
        lng = clicked["lng"]

        # Store in session state
        st.session_state.clicked_location = {"latitude": lat, "longitude": lng}

        # Resolve timezone
        tz = get_timezone_from_coordinates(lat, lng)

        # Resolve location name via reverse geocoding
        # Store the resolved name in session state so we don't re-geocode on every rerun
        if "clicked_location_name" not in st.session_state or st.session_state.get("clicked_location_name_coords") != (lat, lng):
            location_name = get_location_name_from_coordinates(lat, lng)
            st.session_state.clicked_location_name = location_name
            st.session_state.clicked_location_name_coords = (lat, lng)
        else:
            location_name = st.session_state.clicked_location_name

        return Location(
            name=location_name,
            latitude=lat,
            longitude=lng,
            timezone=tz
        )

    return None


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
            <div style="font-size: 1.5rem; color: #60a5fa; font-weight: bold;">{km_to_miles(conditions['visibility']):.1f} mi</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 0.8rem; color: #a0aec0;">TEMPERATURE</div>
            <div style="font-size: 1.5rem; color: #f0abfc; font-weight: bold;">{celsius_to_fahrenheit(conditions['temperature']):.1f}°F</div>
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


def render_targets_section(targets, window):
    """Render the targets section with priority target and list.

    Each target is expected to carry a "forecast_conditions" key (dict or
    None) with the hourly forecast nearest to its own best viewing time.
    """
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

    scored_targets = []
    for target in targets:
        forecast_conditions = target.get("forecast_conditions")
        score = calculate_visibility_score(target, forecast_conditions) if forecast_conditions is not None else None
        scored_targets.append({
            **target,
            "visibility_score": score
        })

    # Targets with a score sort to the top (highest first); unscored targets follow
    scored_targets.sort(key=lambda target: (target["visibility_score"] is None, -(target["visibility_score"] or 0)))

    have_any_score = any(target["visibility_score"] is not None for target in scored_targets)

    # Show priority target only when its own forecast-based score is available
    if have_any_score and scored_targets[0]["visibility_score"] is not None:
        priority = scored_targets[0]
        forecast = priority.get("forecast_conditions")
        forecast_line = (
            f"""<div style="font-size: 0.9rem; color: #a0aec0;">
                Forecast near best time: {forecast['cloud_cover']:.0f}% clouds | {km_to_miles(forecast['visibility']):.1f} mi visibility | {celsius_to_fahrenheit(forecast['temperature']):.1f}°F
            </div>"""
            if forecast else ""
        )
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
            {forecast_line}
        </div>
        """, unsafe_allow_html=True)

    # Show all targets
    st.markdown("#### All Observable Targets")
    for target in scored_targets:
        score_display = (
            f"{target['visibility_score']}/100"
            if target["visibility_score"] is not None
            else "Visibility score unavailable"
        )
        forecast = target.get("forecast_conditions")
        forecast_line = (
            f"""<div style="font-size: 0.85rem; color: #a0aec0;">
                Forecast near best time: {forecast['cloud_cover']:.0f}% clouds | {km_to_miles(forecast['visibility']):.1f} mi visibility | {celsius_to_fahrenheit(forecast['temperature']):.1f}°F
            </div>"""
            if forecast else ""
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
            {forecast_line}
        </div>
        """, unsafe_allow_html=True)


def main():
    """Main dashboard application."""
    # Page config
    st.set_page_config(
        page_title="Night Signal",
        page_icon="🌌",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Initialize session state for map clicks
    if "clicked_location" not in st.session_state:
        st.session_state.clicked_location = None
    if "clicked_location_name" not in st.session_state:
        st.session_state.clicked_location_name = None
    if "clicked_location_name_coords" not in st.session_state:
        st.session_state.clicked_location_name_coords = None

    # Set custom theme
    set_custom_theme()

    # Location selector (sidebar, preset or map-based)
    with st.sidebar:
        st.markdown("## 📍 Observing Location")

        location_source = st.radio(
            "Choose location:",
            ["Preset", "Click Map"],
            horizontal=False
        )

        if location_source == "Preset":
            location_names = [location.name for location in PRESET_LOCATIONS]
            default_index = PRESET_LOCATIONS.index(DEFAULT_LOCATION)
            selected_name = st.selectbox("Select preset:", location_names, index=default_index)
            location = PRESET_LOCATIONS[location_names.index(selected_name)]
            # Clear any prior map click when switching to preset
            st.session_state.clicked_location = None
        else:
            st.markdown("**Using map below — click to select a location**")
            location = None  # Will be set after map interaction

    # Render map in main area
    if location_source == "Click Map":
        map_data = render_map_picker()
        clicked_location = handle_map_click(map_data)
        if clicked_location:
            location = clicked_location
            st.sidebar.success(f"✓ Location: {location.latitude:.4f}, {location.longitude:.4f}\nTimezone: {location.timezone}")
        elif st.session_state.clicked_location:
            # Restore from session state if map hasn't been clicked again
            clicked = st.session_state.clicked_location
            tz = get_timezone_from_coordinates(clicked["latitude"], clicked["longitude"])
            # Use cached location name if available, otherwise use fallback
            location_name = st.session_state.clicked_location_name or f"Selected location ({clicked['latitude']:.4f}, {clicked['longitude']:.4f})"
            location = Location(
                name=location_name,
                latitude=clicked["latitude"],
                longitude=clicked["longitude"],
                timezone=tz
            )
            st.sidebar.success(f"✓ Location: {location.latitude:.4f}, {location.longitude:.4f}\nTimezone: {location.timezone}")
        else:
            # No location selected yet; show warning and stop
            st.warning("👆 Click a location on the map to begin")
            return

    # Header
    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 2rem;">
        <div style="font-size: 3rem; margin-bottom: 0.5rem;">🌌 Night Signal</div>
        <div style="font-size: 1.2rem; color: #60a5fa;">{location.name}</div>
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
            targets = get_target_list(location)
            window = get_observing_window(location)

        try:
            conditions = get_observing_conditions(location)
        except Exception as error:
            conditions = None
            st.warning(f"Weather signal unavailable. Astronomy data is still available. ({error})")

        # Fetch the hourly forecast once and match each target to the nearest
        # hour around its own best viewing time, rather than scoring every
        # target with a single current-conditions snapshot
        try:
            hourly_forecast = get_hourly_forecast(location)
        except Exception:
            hourly_forecast = None

        for target in targets:
            target["forecast_conditions"] = (
                get_conditions_for_time(location, target.get("best_viewing_time_utc"), forecast=hourly_forecast)
                if hourly_forecast is not None
                else None
            )

        if conditions is not None:
            render_weather_section(conditions)
            st.divider()
        render_targets_section(targets, window)

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
