def agent_get_flights(
    trip_type, dep, arr, dep_date, arr_date=None, currency="USD",
    airline=None, max_price=None, direct_only=False,
    max_duration=None, dep_after=None, dep_before=None
):
    """
    Fetch and summarize flight data (with detailed per-flight information)
    via SerpApi.
    """
    params = {
        "api_key": "5ace04863364568bc6e013757ecaea56d0dc7d3e66401e9553d9e5e21c259453",
        "engine": "google_flights",
        "hl": "en",
        "gl": "us",
        "departure_id": dep,
        "arrival_id": arr,
        "outbound_date": dep_date,
        "currency": currency,
    }

    if trip_type == "round-trip" and arr_date:
        params["return_date"] = arr_date
        params["type"] = 1
    else:
        params["type"] = 2

    search = GoogleSearch(params)
    results = search.get_dict()

    # Extract lists
    best = results.get("best_flights", [])
    others = results.get("other_flights", [])
    price_info = results.get("price_insights", {})
    airports = results.get("airports", [])

    detailed = []

    # Loop through each flight
    for f in best + others:
        legs = f.get("flights", [])
        if not legs:
            continue

        # Core info
        airline_names = ", ".join(sorted({leg.get("airline", "?") for leg in legs}))
        route = f"{legs[0]['departure_airport']['id']} → {legs[-1]['arrival_airport']['id']}"
        price = f.get("price", "N/A")
        total_duration = f.get("total_duration", "N/A")
        carbon = f.get("carbon_emissions", {}).get("this_flight", None)
        layovers = [l.get("name") for l in f.get("layovers", [])] if "layovers" in f else []
        booking_token = f.get("departure_token", None)

        # Extract per-leg amenities
        leg_details = []
        for leg in legs:
            leg_info = {
                "from": leg["departure_airport"]["id"],
                "to": leg["arrival_airport"]["id"],
                "airline": leg.get("airline"),
                "airplane": leg.get("airplane"),
                "duration_mins": leg.get("duration"),
                "legroom": leg.get("legroom"),
                "travel_class": leg.get("travel_class"),
                "flight_number": leg.get("flight_number"),
                "extensions": leg.get("extensions", []),
            }
            leg_details.append(leg_info)

        detailed.append({
            "route": route,
            "airlines": airline_names,
            "price": f"{price} {currency}",
            "duration": total_duration,
            "carbon_kg": int(carbon / 1000) if carbon else None,
            "layovers": layovers,
            "booking_token": booking_token,
            "legs": leg_details,
        })

    return {
        "flights": detailed,
        "price_insights": price_info,
        "airports": airports,
        "search_metadata": results.get("search_metadata", {}),
    }