"""
Full live API test for flight_agent_tools.py
Verifies:
 - One-way and round-trip searches
 - Filters (airline, price, duration, direct, stopover)
 - Sorting
 - Flexible ±days search
 - Error handling
"""

from flight_agent_tools import agent_get_flights, summarize_flights, agent_get_flights_flexible


# -----------------------------
# BASIC CONFIGURATION
# -----------------------------
DEPARTURE = "BEY"   # Beirut
ARRIVAL = "DXB"     # Dubai
DEP_DATE = "2025-12-10"
RET_DATE = "2025-12-16"
CURRENCY = "USD"

# -----------------------------
# 1️⃣ One-way flight test
# -----------------------------
print("\n========== ONE-WAY FLIGHT TEST ==========")
oneway = agent_get_flights(
    trip_type="one-way",
    dep=DEPARTURE,
    arr=ARRIVAL,
    dep_date=DEP_DATE,
    currency=CURRENCY,
    adults=1,
    travel_class="economy",
    sort_by="price",
)

print(f"\n✅ Found {len(oneway['outbound'])} flights")
print(summarize_flights(oneway, top_n=5, currency=CURRENCY))

# -----------------------------
# 2️⃣ Round-trip flight test
# -----------------------------
print("\n========== ROUND-TRIP FLIGHT TEST ==========")
roundtrip = agent_get_flights(
    trip_type="round-trip",
    dep=DEPARTURE,
    arr=ARRIVAL,
    dep_date=DEP_DATE,
    arr_date=RET_DATE,
    currency=CURRENCY,
    adults=2,
    children=1,
    travel_class="business",
    sort_by="duration",
)

print(f"\n✅ Outbound flights: {len(roundtrip['outbound'])}")
print(f"✅ Return flights: {len(roundtrip['return'])}")

print("\n--- Outbound ---")
print(summarize_flights(roundtrip, top_n=3, currency=CURRENCY))

print("\n--- Return ---")
print(summarize_flights(roundtrip, top_n=3, currency=CURRENCY))

# -----------------------------
# 3️⃣ Filters test
# -----------------------------
print("\n========== FILTER TESTS ==========")

emirates_only = agent_get_flights(
    "one-way", DEPARTURE, ARRIVAL, DEP_DATE,
    airline="Emirates", currency=CURRENCY
)
print(f"\nFlights by Emirates: {len(emirates_only['outbound'])}")

under_800 = agent_get_flights(
    "one-way", DEPARTURE, ARRIVAL, DEP_DATE,
    max_price=800, currency=CURRENCY
)
print(f"Flights under 800 USD: {len(under_800['outbound'])}")

directs = agent_get_flights(
    "one-way", DEPARTURE, ARRIVAL, DEP_DATE,
    direct_only=True, currency=CURRENCY
)
print(f"Direct flights: {len(directs['outbound'])}")

short_flights = agent_get_flights(
    "one-way", DEPARTURE, ARRIVAL, DEP_DATE,
    max_duration=400, currency=CURRENCY
)
print(f"Flights shorter than 400 minutes: {len(short_flights['outbound'])}")

through_DOH = agent_get_flights(
    "one-way", DEPARTURE, ARRIVAL, DEP_DATE,
    stopover="DOH", currency=CURRENCY
)
print(f"Flights connecting through Doha (DOH): {len(through_DOH['outbound'])}")

# -----------------------------
# 4️⃣ Error handling test
# -----------------------------
print("\n========== ERROR HANDLING TEST ==========")
invalid = agent_get_flights(
    "one-way", "XXX", "YYY", DEP_DATE, currency=CURRENCY
)
print(f"Invalid route flights: {len(invalid['outbound'])} (should be 0)")

# -----------------------------
# 5️⃣ Flexible ±3 days test
# -----------------------------
print("\n========== FLEXIBLE ±3 DAYS TEST ==========")
flexible_results = agent_get_flights_flexible(
    trip_type="one-way",
    dep=DEPARTURE,
    arr=ARRIVAL,
    dep_date=DEP_DATE,
    currency=CURRENCY,
    adults=1,
    travel_class="economy",
    sort_by="price",
    days_flex=3
)

all_flights = flexible_results.get("flights", [])
print(f"\n✅ Found {len(all_flights)} flights across ±3 days")
print(summarize_flights(flexible_results, top_n=10, currency=CURRENCY))
