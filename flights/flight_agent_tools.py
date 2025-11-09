import requests
from datetime import datetime, timedelta

API_KEY = "5ace04863364568bc6e013757ecaea56d0dc7d3e66401e9553d9e5e21c259453"
BASE_URL = "https://serpapi.com/search"
CURRENT_CURRENCY = "USD"


# -------------------------
# Utility helpers
# -------------------------

def fetch_booking_details(
    booking_token,
    departure_id=None,
    arrival_id=None,
    outbound_date=None,
    return_date=None,
    trip_type=2,  # default: one-way
):
    """Fetch detailed booking options using booking_token + flight context."""
    params = {
        "engine": "google_flights",
        "booking_token": booking_token,
        "api_key": API_KEY,
        "type": trip_type,
    }
    if departure_id:
        params["departure_id"] = departure_id
    if arrival_id:
        params["arrival_id"] = arrival_id
    if outbound_date:
        params["outbound_date"] = outbound_date
    if return_date:
        params["return_date"] = return_date

    try:
        resp = requests.get(BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": f"Booking details fetch failed: {e}"}


def _parse_price(text):
    if isinstance(text, (int, float)):
        return float(text)
    try:
        return float("".join(c for c in str(text) if c.isdigit() or c == "."))
    except Exception:
        return float("inf")


def _total_duration(flight_obj):
    try:
        return sum(leg["duration"] for leg in flight_obj["flights"])
    except Exception:
        return 10**9


def _dep_minutes(leg_time_str):
    if not leg_time_str:
        return None
    if "T" in leg_time_str:
        t = leg_time_str.split("T")[-1]
    elif " " in leg_time_str:
        t = leg_time_str.split(" ")[-1]
    else:
        t = leg_time_str
    try:
        h, m = t[:5].split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None


def _to_list(data_or_list):
    """Normalize input to always return a list of flight objects."""
    if isinstance(data_or_list, list):
        return data_or_list

    if not isinstance(data_or_list, dict):
        return []

    out = []
    for k in ("best_flights", "other_flights", "outbound", "return", "flights"):
        if k in data_or_list and isinstance(data_or_list[k], list):
            out.extend(data_or_list[k])

    return out



def normalize_travel_class(user_input):
    """Converts user input (text or number) to SerpAPI numeric travel_class (1–4)."""
    mapping = {
        "economy": 1,
        "eco": 1,
        "premium": 2,
        "premium economy": 2,
        "business": 3,
        "biz": 3,
        "first": 4,
    }
    if isinstance(user_input, int):
        return min(max(user_input, 1), 4)
    try:
        if str(user_input).strip().isdigit():
            return min(max(int(user_input), 1), 4)
    except:
        pass
    return mapping.get(str(user_input).strip().lower(), 1)


def date_range(center_date_str, days_flex=3):
    """Return list of date strings ±days_flex around center_date."""
    base = datetime.strptime(center_date_str, "%Y-%m-%d")
    return [
        (base + timedelta(days=d)).strftime("%Y-%m-%d")
        for d in range(-days_flex, days_flex + 1)
    ]


# -------------------------
# Fetch from SerpAPI
# -------------------------

def fetch_one_way_flights(departure, arrival, date, currency,
                          adults=1, children=0, infants=0, travel_class=1):
    """Fetch one-way flights from SerpApi Google Flights engine."""
    params = {
        "engine": "google_flights",
        "departure_id": departure,
        "arrival_id": arrival,
        "outbound_date": date,
        "currency": currency,
        "type": 2,
        "adults": adults,
        "children": children,
        "infants_in_seat": infants,
        "travel_class": normalize_travel_class(travel_class),
        "show_booking_options": True,
        "api_key": API_KEY,
    }

    resp = requests.get(BASE_URL, params=params)
    data = resp.json()

    if "error" in data:
        return {"outbound": []}

    flights = data.get("best_flights") or data.get("other_flights") or []
    if flights:
        token = flights[0].get("booking_token")
        if token:
            details = fetch_booking_details(
                token,
                departure_id=departure,
                arrival_id=arrival,
                outbound_date=date,
                trip_type=2,
            )
            data["booking_details"] = details
            data["booking_details"]["token"] = token
    return data


def fetch_round_trip_flights(departure, arrival, dep_date, arr_date, currency,
                             adults=1, children=0, infants=0, travel_class=1):
    """Fetch round-trip flights from SerpApi Google Flights engine."""
    params = {
        "engine": "google_flights",
        "departure_id": departure,
        "arrival_id": arrival,
        "outbound_date": dep_date,
        "return_date": arr_date,
        "currency": currency,
        "type": 1,
        "adults": adults,
        "children": children,
        "infants_in_seat": infants,
        "travel_class": normalize_travel_class(travel_class),
        "show_booking_options": True,
        "api_key": API_KEY,
    }

    resp = requests.get(BASE_URL, params=params)
    data = resp.json()

    if "error" in data:
        return {"outbound": [], "return": []}

    outbound = data.get("best_flights") or data.get("other_flights") or []
    inbound = data.get("return_flights") or outbound

    if outbound:
        token = outbound[0].get("booking_token")
        if token:
            details = fetch_booking_details(
                token,
                departure_id=departure,
                arrival_id=arrival,
                outbound_date=dep_date,
                return_date=arr_date,
                trip_type=1,
            )
            data["booking_details"] = details
            data["booking_details"]["token"] = token
    return data, data


# -------------------------
# Filters
# -------------------------

def filter_by_airline(flights_list, airline_name):
    flights = _to_list(flights_list)
    if not airline_name:
        return flights
    target = airline_name.lower()
    return [
        f for f in flights
        if any(target in str(leg.get("airline", "")).lower()
               for leg in f.get("flights", []))
    ]


def filter_by_price(flights_list, max_price):
    flights = _to_list(flights_list)
    if not max_price:
        return flights
    return [f for f in flights if _parse_price(f.get("price")) <= max_price]


def filter_direct_flights(flights_list, direct_only=True):
    flights = _to_list(flights_list)
    if not direct_only:
        return flights
    return [f for f in flights if len(f.get("flights", [])) == 1]


def filter_by_duration(flights_list, max_duration_minutes):
    flights = _to_list(flights_list)
    if not max_duration_minutes:
        return flights
    return [f for f in flights if _total_duration(f) <= max_duration_minutes]


def filter_by_departure_time(flights_list, after=None, before=None):
    flights = _to_list(flights_list)
    after_min = None if not after else _dep_minutes(after)
    before_min = None if not before else _dep_minutes(before)
    return [
        f for f in flights
        if (dep_m := _dep_minutes(f.get("flights", [{}])[0].get("departure_airport", {}).get("time")))
        and (after_min is None or dep_m >= after_min)
        and (before_min is None or dep_m <= before_min)
    ]


def filter_by_arrival_time(flights_list, after=None, before=None):
    flights = _to_list(flights_list)
    after_min = None if not after else _dep_minutes(after)
    before_min = None if not before else _dep_minutes(before)
    return [
        f for f in flights
        if (arr_m := _dep_minutes(f.get("flights", [{}])[-1].get("arrival_airport", {}).get("time")))
        and (after_min is None or arr_m >= after_min)
        and (before_min is None or arr_m <= before_min)
    ]


def filter_by_stopover(flights_list, airport_code):
    flights = _to_list(flights_list)
    if not airport_code:
        return flights
    code = airport_code.lower()
    return [
        f for f in flights
        if any(code == leg.get("arrival_airport", {}).get("id", "").lower()
               for leg in f.get("flights", [])[:-1])
    ]


# -------------------------
# Sorting
# -------------------------

def sort_flights(flights_list, by="price", ascending=True):
    flights = _to_list(flights_list)
    key_fn = {
        "price": lambda f: _parse_price(f.get("price")),
        "duration": _total_duration,
        "departure": lambda f: _dep_minutes(
            f.get("flights", [{}])[0].get("departure_airport", {}).get("time")
        ),
        "arrival": lambda f: _dep_minutes(
            f.get("flights", [{}])[-1].get("arrival_airport", {}).get("time")
        )
    }.get(by, lambda f: 0)
    return sorted(flights, key=key_fn, reverse=not ascending)


# -------------------------
# Analysis & summaries
# -------------------------

def summarize_flights(data_or_list, top_n=3, currency=None):
    if currency is None:
        currency = CURRENT_CURRENCY
    adults = children = infants = 0
    if isinstance(data_or_list, dict) and "_passengers" in data_or_list:
        p = data_or_list["_passengers"]
        adults = p.get("adults", 0)
        children = p.get("children", 0)
        infants = p.get("infants", 0)
    total_passengers = adults + children + infants

    flights = _to_list(data_or_list)
    if not flights:
        return "No flight data available."

    lines = []
    feature_keywords = ["Wi-Fi", "USB", "video", "stream", "seat", "power", "outlet", "legroom", "entertainment"]
    for i, f in enumerate(flights[:top_n], 1):
        legs = f.get("flights", [])
        if not legs:
            continue
        first_leg, last_leg = legs[0], legs[-1]
        route = f"{first_leg.get('departure_airport', {}).get('id', '?')} → {last_leg.get('arrival_airport', {}).get('id', '?')}"
        airlines = ", ".join(sorted({leg.get("airline", "?") for leg in legs}))
        tclass = legs[0].get("travel_class", "N/A").capitalize()
        price = f.get("price", "N/A")
        dur = _total_duration(f)
        lines.append(
            f"\nOption {i}: {route} | {airlines} | 💺 {tclass} | 👥 {total_passengers or 'N/A'} passenger(s)"
            f" | 💰 {price} {currency} | ⏱ Duration: {dur} mins"
        )
        for idx, leg in enumerate(legs, 1):
            dep_air = leg.get("departure_airport", {}).get("name", "?")
            arr_air = leg.get("arrival_airport", {}).get("name", "?")
            dep_time = leg.get("departure_airport", {}).get("time", "?")
            arr_time = leg.get("arrival_airport", {}).get("time", "?")
            flight_no = leg.get("flight_number", "N/A")
            lines.append(f"   🛫 Leg {idx}: {dep_air} → {arr_air}")
            lines.append(f"       Flight: {leg.get('airline', '?')} {flight_no}")
            lines.append(f"       Departure: {dep_time}")
            lines.append(f"       Arrival: {arr_time}")
        features = []
        for leg in legs:
            for ext in leg.get("extensions", []):
                if "emission" in ext.lower() or "carbon" in ext.lower():
                    continue
                if any(k.lower() in ext.lower() for k in feature_keywords):
                    features.append(ext)
        feature_text = " | ".join(sorted(set(features))) if features else "No in-flight features listed"
        lines.append(f"   ✈️ Features: {feature_text}")

    return "\n".join(lines)


# -------------------------
# Error handling
# -------------------------

def explain_error(response_json):
    if "error" in response_json:
        return f"⚠️ API Error: {response_json['error']}"
    if not _to_list(response_json):
        return "No flights found. Try changing the date or route."
    return None


# -------------------------
# Filter pipeline
# -------------------------

def get_filtered_flights(
    data_or_list,
    airline=None, max_price=None, direct_only=False,
    max_duration=None, dep_after=None, dep_before=None,
    arr_after=None, arr_before=None, stopover=None,
    sort_by=None, ascending=True
):
    flights = _to_list(data_or_list)
    if airline:
        flights = filter_by_airline(flights, airline)
    if max_price:
        flights = filter_by_price(flights, max_price)
    if direct_only:
        flights = filter_direct_flights(flights, True)
    if max_duration:
        flights = filter_by_duration(flights, max_duration)
    if dep_after or dep_before:
        flights = filter_by_departure_time(flights, dep_after, dep_before)
    if arr_after or arr_before:
        flights = filter_by_arrival_time(flights, arr_after, arr_before)
    if stopover:
        flights = filter_by_stopover(flights, stopover)
    if sort_by:
        flights = sort_flights(flights, by=sort_by, ascending=ascending)
    return flights


# -------------------------
# Unified agent API
# -------------------------

def agent_get_flights(
    trip_type, dep, arr, dep_date, arr_date=None, currency="USD",
    airline=None, max_price=None, direct_only=False,
    max_duration=None, dep_after=None, dep_before=None,
    arr_after=None, arr_before=None, stopover=None,
    sort_by=None, ascending=True,
    adults=1, children=0, infants=0, travel_class=1
):
    global CURRENT_CURRENCY
    CURRENT_CURRENCY = currency
    result = {"outbound": [], "return": []}

    if trip_type == "one-way":
        raw = fetch_one_way_flights(dep, arr, dep_date, currency,
                                    adults, children, infants, travel_class)
        err = explain_error(raw)
        if err:
            return result
        result["outbound"] = get_filtered_flights(
            raw, airline, max_price, direct_only, max_duration,
            dep_after, dep_before, arr_after, arr_before,
            stopover, sort_by, ascending
        )
        result["_passengers"] = {"adults": adults, "children": children, "infants": infants}
        return result

    if trip_type == "round-trip":
        raw_out, raw_back = fetch_round_trip_flights(
            dep, arr, dep_date, arr_date, currency,
            adults, children, infants, travel_class
        )
        err = explain_error(raw_out)
        if err:
            return result
        result["outbound"] = get_filtered_flights(
            raw_out, airline, max_price, direct_only, max_duration,
            dep_after, dep_before, arr_after, arr_before,
            stopover, sort_by, ascending
        )
        result["return"] = get_filtered_flights(
            raw_back, airline, max_price, direct_only, max_duration,
            dep_after, dep_before, arr_after, arr_before,
            stopover, sort_by, ascending
        )
        result["_passengers"] = {"adults": adults, "children": children, "infants": infants}
        return result

    raise ValueError("trip_type must be 'one-way' or 'round-trip'")


def agent_get_flights_flexible(
    trip_type, dep, arr, dep_date, arr_date=None, currency="USD",
    airline=None, max_price=None, direct_only=False,
    max_duration=None, dep_after=None, dep_before=None,
    arr_after=None, arr_before=None, stopover=None,
    sort_by=None, ascending=True,
    adults=1, children=0, infants=0, travel_class=1,
    days_flex=3
):
    """Perform the same flight search for ±days_flex around dep_date."""
    from copy import deepcopy

    all_flights = []

    for d in date_range(dep_date, days_flex):
        result = agent_get_flights(
            trip_type, dep, arr, d, arr_date, currency,
            airline, max_price, direct_only, max_duration,
            dep_after, dep_before, arr_after, arr_before,
            stopover, sort_by, ascending,
            adults, children, infants, travel_class
        )

        if result["outbound"]:
            for f in result["outbound"]:
                f_copy = deepcopy(f)
                f_copy["search_date"] = d
                all_flights.append(f_copy)

    if sort_by:
        all_flights = sort_flights(all_flights, by=sort_by, ascending=ascending)
    else:
        all_flights = sort_flights(all_flights, by="price", ascending=True)

    # ✅ Attach passenger info for automatic summary
    result_info = {
        "_passengers": {
            "adults": adults,
            "children": children,
            "infants": infants,
        }
    }

    return {"flights": all_flights, **result_info}
