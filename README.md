# Night Signal

Night Signal is a location-aware night-sky planning dashboard that combines astronomy calculations, weather forecasts, and an interactive map to help identify the best astronomical observation opportunities for a given night.

## Features

- Interactive map-based observing location selection
- Preset observing locations
- Automatic timezone detection
- Reverse geocoding for human-readable location names
- Astronomical dark-window calculation using sunset and astronomical twilight
- Planet visibility calculations for Mercury, Venus, Mars, Jupiter, and Saturn
- Best viewing time, maximum altitude, observable duration, and apparent magnitude
- Hourly weather forecast matching for each target's best viewing time
- Visibility scoring based on target position, brightness, duration, and forecast conditions
- Current weather conditions shown in Fahrenheit and miles
- Lunar Signal panel with:
  - Moon phase
  - Illumination percentage
  - Moonrise and moonset
  - Best viewing time
  - Maximum altitude
  - Dynamic moon-phase visualization
- Graceful fallback behavior when weather or geocoding services are unavailable

## Tech Stack

- Python
- Streamlit
- Skyfield
- Open-Meteo
- Folium
- streamlit-folium
- timezonefinder
- geopy
- NumPy

## Running the App

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the Streamlit dashboard:

```bash
streamlit run dashboard.py
```

Then open the forwarded Streamlit port in your browser.

## Testing

Run the current test suite:

```bash
python tests/test_scoring.py
python tests/test_weather_forecast.py
python tests/test_lunar.py
```

## Project Structure

```text
Night-Signal/
├── dashboard.py
├── requirements.txt
├── src/
│   ├── astronomy.py
│   ├── briefing.py
│   ├── config.py
│   ├── main.py
│   ├── scoring.py
│   └── weather.py
└── tests/
    ├── test_lunar.py
    ├── test_scoring.py
    └── test_weather_forecast.py
```

## About

Night Signal started as a simple astronomy-monitoring project and has grown into a location-aware observing assistant that combines real astronomical calculations with forecast conditions to help answer a practical question:

**What is actually worth looking at tonight, and when should I look?**