# Night Signal

Night Signal is a location-aware astronomy observing planner that helps users decide what is worth looking at, where, and when.

It combines local sky calculations, weather forecasts, curated observing signals, and an interactive Streamlit dashboard to answer a practical question: what is worth stepping outside for on the selected observing night?

## Features

- Location selection
  - preset observing locations
  - typed location search
  - map click selection
  - saved locations
- Observing date planning
  - Tonight mode
  - See Another Date mode
  - observer-local timezone handling
- Weather conditions
  - current conditions for Tonight
  - forecast matching for supported future dates
  - Fahrenheit temperatures and miles-per-hour wind speeds
- Lunar Signal
  - Moon phase and illumination
  - moonrise and moonset
  - best viewing time and altitude when available
  - compact phase visualization
- Meteor Signal
  - active major meteor showers
  - peak/near-peak status
  - radiant, ZHR, best window, and moon interference
  - next shower signal when no major shower is active
- Constellation Signal
  - one featured constellation for the selected location and observing night
  - curated constellation diagram
  - best collective viewing time
  - notable visible stars with approximate color coding
- Special Signal
  - Near-Earth Object flybys from NASA NeoWs
  - planetary conjunctions / close visual pairings
  - curated solar and lunar eclipse events
  - curated notable comet windows
  - ISS passes when TLE freshness supports reliable prediction
  - Coming Up fallbacks for quiet observing dates
- Transmission Targets
  - prioritized planet targets
  - visibility scores
  - best viewing times, altitude, duration, magnitude, and matched forecast conditions

## Tech Stack

- Python
- Streamlit
- Skyfield
- Open-Meteo
- NASA NeoWs
- CelesTrak ISS TLE data
- Folium
- streamlit-folium
- geopy
- timezonefinder
- NumPy

## How It Works

Night Signal starts with the selected observing location and resolves its IANA timezone. All date-sensitive behavior uses that observer-local timezone, not the server timezone.

Skyfield calculates the dark observing window for the selected night using sunset and astronomical twilight. Planet targets, lunar visibility, planetary conjunctions, ISS pass checks, and Constellation Signal visibility are evaluated against that observing window.

Visibility scoring combines astronomy and forecast conditions where weather data is available. Tonight uses current weather plus hourly forecast matching. Future dates use Open-Meteo forecast data only when the date is inside the supported forecast horizon.

Several V1 signals use curated datasets rather than fragile scrapers: meteor shower definitions, constellation/star data, eclipse events, and notable comet windows. Those curated sources are intentionally small, deterministic, and documented so the dashboard remains responsive and understandable.

## Running Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Optionally create a local `.env` file or export environment variables for API keys. The app can run without a NASA key for limited development use via NASA's public `DEMO_KEY` fallback.

Start the Streamlit dashboard:

```bash
streamlit run dashboard.py
```

Run the command-line smoke check:

```bash
python src/main.py
```

Run the full test suite:

```bash
for f in tests/test_*.py; do python "$f"; done
```

## Environment Variables

- `NASA_API_KEY`: optional NASA API key used for Special Signal Near-Earth Object data from NASA NeoWs.

If `NASA_API_KEY` is not set, Night Signal uses NASA's public `DEMO_KEY`, which can work for limited development but is more tightly rate-limited.

## Limitations

- Eclipse support uses a small curated V1 dataset. Solar eclipse locality is conservative: broad regional relevance and Sun altitude are checked, but exact local eclipse magnitude or totality is not calculated.
- Comet support uses curated notable comet windows with approximate fixed coordinates. Comet best-viewing times and altitudes are approximate, not precision ephemerides.
- ISS predictions depend on fresh TLE data and are limited to a conservative window around the current/TLE date. Night Signal returns no ISS pass predictions outside that validity window.
- Weather forecasts are limited by Open-Meteo's forecast horizon. Past dates and dates beyond the forecast range do not reuse current weather.
- Constellation Signal uses a curated constellation and anchor-star set. It is designed to recommend one recognizable constellation, not replace a full star atlas.
- NEO close approaches are interesting solar-system events, but a close approach does not imply naked-eye or telescope observability.
- The bundled `de421.bsp` ephemeris supports the astronomy calculations used by this project, but it is not an all-purpose long-range ephemeris for every possible sky event.

## Data Sources

- Skyfield and the bundled JPL `de421.bsp` ephemeris for astronomy calculations
- Open-Meteo for current and forecast weather data
- NASA NeoWs for Near-Earth Object close-approach data
- CelesTrak for current ISS TLE data
- OpenStreetMap Nominatim via geopy for forward and reverse geocoding
- timezonefinder for timezone lookup from latitude/longitude
- Curated Night Signal V1 datasets for meteor showers, constellations, eclipses, and notable comet windows

## Screenshots

Screenshots are not included yet. Add V1 dashboard screenshots here before publishing a release page or project listing.