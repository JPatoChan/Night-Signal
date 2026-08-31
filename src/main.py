from weather import get_observing_conditions
from astronomy import get_observing_window, get_target_list
from briefing import generate_report
from config import DEFAULT_LOCATION


def main():
    print("Night Signal online.")
    print("Listening to the sky...")

    location = DEFAULT_LOCATION
    targets = get_target_list(location)
    window = get_observing_window(location)

    print(f"Sunset: {window['sunset']}")
    print(
        "Dark observing window: "
        f"{window['evening_twilight_end']} -> {window['morning_twilight_begin']}"
    )

    try:
        conditions = get_observing_conditions(location)
    except Exception as error:
        print(f"\nWeather signal unavailable: {error}")
        print("Weather-dependent visibility scoring is unavailable.\n")
        if not targets:
            print("No planets are observable during tonight's dark window.")
            return

        print("Observable targets:")
        for target in targets:
            print(f"\nTarget: {target['name']}")
            print(f"Best viewing time: {target['best_viewing_time']}")
            print(f"Max altitude: {target['max_altitude']}°")
            print(f"Observable duration: {target['observable_duration_hours']} hours")
            print(f"Apparent magnitude: {target['apparent_magnitude']}")
        return

    report = generate_report(conditions, targets)
    print(report)


if __name__ == "__main__":
    main()
