import requests

API_KEY = "5ace04863364568bc6e013757ecaea56d0dc7d3e66401e9553d9e5e21c259453"

# --- Fetch data ---
def fetch_flights(departure, arrival, date, currency):
    params = {
        "engine": "google_flights",
        "departure_id": departure,
        "arrival_id": arrival,
        "outbound_date": date,
        "currency": currency,
        "api_key": API_KEY,
        "type": 2
    }
    response = requests.get("https://serpapi.com/search", params=params)
    return response.json()

# --- Print one option ---
def print_flight_option(i, flight, currency):
    print(f"\nOption {i}:")
    for leg in flight["flights"]:
        print(f"  {leg['departure_airport']['id']} → {leg['arrival_airport']['id']}")
        print(f"    Airline: {leg['airline']}")
        print(f"    Departure: {leg['departure_airport']['time']}")
        print(f"    Arrival: {leg['arrival_airport']['time']}")
        print(f"    Duration: {leg['duration']} minutes")
        print("    ---")
    print(f" Price: {flight['price']} {currency}")
    print(f" Link: {flight.get('link', 'N/A')}")
    print("-" * 80)

# --- Print all flights (with filtering) ---
def print_flights(title, data, currency, airline_filter=None, max_price=None, direct_only=False):
    print(f"\n {title}\n" + "-" * 80)
    found = False

    def matches_filters(f):
        try:
            price_value = float(''.join([c for c in f["price"] if c.isdigit() or c == "."]))
        except:
            price_value = 0

        if airline_filter:
            airline_names = [leg["airline"].lower() for leg in f["flights"]]
            if not any(airline_filter.lower() in a for a in airline_names):
                return False

        if max_price and price_value > max_price:
            return False

        if direct_only and len(f["flights"]) > 1:
            return False

        return True

    for key in ["best_flights", "other_flights"]:
        if key in data and data[key]:
            flights = [f for f in data[key] if matches_filters(f)]
            if flights:
                found = True
                print(f"\n{'BEST' if key=='best_flights' else ' OTHER'} FLIGHT OPTIONS:")
                for i, flight in enumerate(flights, 1):
                    print_flight_option(i, flight, currency)

    if not found:
        print("No flights matched your filters.")
        print("-" * 80)

# --- Main ---
if __name__ == "__main__":
    dep = input("Enter departure city code (e.g. BEY): ")
    arr = input("Enter arrival city code (e.g. DXB): ")

    trip_type = input("Enter 1 for one-way, 2 for round-trip: ").strip()
    dep_date = input("Enter date of departure (YYYY-MM-DD): ")

    arr_date = None
    if trip_type == "2":
        arr_date = input("Enter date of return (YYYY-MM-DD): ")

    currency = input("Enter currency (e.g. USD): ")

    # Filters
    airline_filter = input("Filter by airline (or press Enter for all): ").strip()
    max_price = input("Max price (or press Enter for no limit): ").strip()
    direct_only = input("Show only direct flights? (y/n): ").strip().lower() == "y"
    max_price = float(max_price) if max_price else None

    # Fetch and print flights
    outbound = fetch_flights(dep, arr, dep_date, currency)
    print_flights(f"OUTBOUND FLIGHTS ({dep} → {arr})", outbound, currency,
                  airline_filter, max_price, direct_only)

    if trip_type == "2":
        return_leg = fetch_flights(arr, dep, arr_date, currency)
        print_flights(f"RETURN FLIGHTS ({arr} → {dep})", return_leg, currency,
                      airline_filter, max_price, direct_only)
