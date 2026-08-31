from weather import get_observing_conditions
from astronomy import get_target_list
from briefing import generate_report


def main():
    print("Night Signal online.")
    print("Listening to the sky...")
    
    # Get sample data
    conditions = get_observing_conditions()
    targets = get_target_list()
    
    # Generate and print report
    report = generate_report(conditions, targets)
    print(report)


if __name__ == "__main__":
    main()
