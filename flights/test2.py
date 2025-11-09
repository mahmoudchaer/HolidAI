from serpapi import GoogleSearch

params = {
    "engine": "google_flights",
    "departure_id": "BEY",
    "arrival_id": "DXB",
    "outbound_date": "2025-12-10",
    "return_date": "2025-12-16",
    "type": 1,
    "adults": 2,
    "children": 1,
    "travel_class": 1,
    "sort_by": 2,
    "currency": "USD",
    "api_key": "5ace04863364568bc6e013757ecaea56d0dc7d3e66401e9553d9e5e21c259453",
}

search = GoogleSearch(params)
results = search.get_dict()

print("✅ Top-level keys:", results.keys())

# Combine both best and other flights safely
flights = []
flights.extend(results.get("best_flights", []))
flights.extend(results.get("other_flights", []))

print(f"\n🛫 Total flights found: {len(flights)}")

for i, f in enumerate(flights, 1):
    price = f.get("price", "N/A")
    airline = ", ".join({leg.get("airline", "") for leg in f.get("flights", [])})
    legs = f.get("flights", [])
    legroom = legs[0].get("legroom", "N/A") if legs else "N/A"
    extras = ", ".join(legs[0].get("extensions", [])) if legs else "N/A"
    token = f.get("departure_token", "N/A")

    print(f"""
Option {i}:
  Airline: {airline}
  Price: {price} USD
  Legroom: {legroom}
  Extras: {extras}
  Booking Token: {token[:80]}...
    """)

