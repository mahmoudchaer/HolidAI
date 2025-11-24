"""Intelligent result summarization for conversational agent.

This module provides smart summarization of agent results to reduce
context size while maintaining all important information.

No LLM calls needed - just simple field removal and truncation.
"""


def remove_hotel_redundant_fields(hotels: list) -> list:
    """Stage 1: Remove definitely redundant fields from hotel data."""
    cleaned = []
    for hotel in hotels:
        cleaned_hotel = {
            # Keep essential fields
            "name": hotel.get("name"),
            "address": hotel.get("address"),
            "city": hotel.get("city"),
            "country": hotel.get("country"),
            "latitude": hotel.get("latitude"),
            "longitude": hotel.get("longitude"),
            "stars": hotel.get("stars"),
            "rating": hotel.get("rating"),
            "reviewCount": hotel.get("reviewCount"),
            "main_photo": hotel.get("main_photo"),
            "currency": hotel.get("currency"),
            # Include description but will be summarized in stage 2
            "hotelDescription": hotel.get("hotelDescription", ""),
            # Include room types if available (prices!)
            "roomTypes": hotel.get("roomTypes", [])
        }
        # Remove None values
        cleaned_hotel = {k: v for k, v in cleaned_hotel.items() if v is not None}
        cleaned.append(cleaned_hotel)
    
    return cleaned


def remove_flight_redundant_fields(flights: list) -> list:
    """Stage 1: Remove definitely redundant fields from flight data."""
    cleaned = []
    for flight in flights:
        cleaned_flight = {
            # Keep essential fields
            "flights": [],  # Will populate
            "layovers": flight.get("layovers", []),
            "total_duration": flight.get("total_duration"),
            "price": flight.get("price"),
            "type": flight.get("type"),
            "carbon_emissions": flight.get("carbon_emissions", {}),
            # Keep booking links - CRITICAL for user to book flights
            "booking_link": flight.get("booking_link"),
            "google_flights_url": flight.get("google_flights_url"),
            "book_with": flight.get("book_with"),
            "booking_price": flight.get("booking_price"),
            # Note: booking_token removed to reduce JSON size (booking_link is sufficient)
            "direction": flight.get("direction"),  # Keep direction for outbound/return
            "airline_logo": flight.get("airline_logo"),  # Keep top-level airline logo
        }
        
        # Clean each flight segment
        for segment in flight.get("flights", []):
            cleaned_segment = {
                "departure_airport": segment.get("departure_airport", {}),
                "arrival_airport": segment.get("arrival_airport", {}),
                "duration": segment.get("duration"),
                "airline": segment.get("airline"),
                "airline_logo": segment.get("airline_logo"),  # Keep airline logo for UI
                "airplane": segment.get("airplane"),
                "travel_class": segment.get("travel_class"),
                "flight_number": segment.get("flight_number"),
                "legroom": segment.get("legroom"),
                # Skip: extensions (too verbose)
            }
            cleaned_flight["flights"].append(cleaned_segment)
        
        # Remove None values (but keep empty strings for URLs)
        # CRITICAL: Always preserve google_flights_url even if it seems None
        # (it might be set later or we want to ensure it's always present)
        cleaned_flight = {k: v for k, v in cleaned_flight.items() if v is not None}
        
        # Ensure google_flights_url is always present (use fallback if missing)
        if not cleaned_flight.get("google_flights_url"):
            # Try to get it from original flight
            original_url = flight.get("google_flights_url")
            if original_url:
                cleaned_flight["google_flights_url"] = original_url
        
        cleaned.append(cleaned_flight)
    
    return cleaned


def remove_esim_redundant_fields(bundles: list) -> list:
    """Stage 1: eSIM bundles are already clean, just pass through."""
    return bundles


async def summarize_hotel_results(raw_hotels: list, user_message: str, step_context: str) -> dict:
    """Summarize hotel results by removing redundant fields and limiting to 20."""
    if not raw_hotels:
        return {"hotels": [], "count": 0}
    
    # Remove redundant fields and limit to 20
    cleaned_hotels = remove_hotel_redundant_fields(raw_hotels[:20])
    
    return {
        "hotels": cleaned_hotels,
        "count": len(cleaned_hotels),
        "summary": f"Found {len(raw_hotels)} hotels, showing top {len(cleaned_hotels)}"
    }


async def summarize_flight_results(raw_flights: list, user_message: str, step_context: str) -> dict:
    """Summarize flight results by removing redundant fields and limiting to 10."""
    if not raw_flights:
        return {"flights": [], "count": 0}
    
    # Remove redundant fields and limit to 10
    cleaned_flights = remove_flight_redundant_fields(raw_flights[:10])
    
    return {
        "flights": cleaned_flights,
        "count": len(cleaned_flights),
        "summary": f"Found {len(raw_flights)} flights, showing top {len(cleaned_flights)}"
    }


async def summarize_tripadvisor_results(raw_result: dict, user_message: str, step_context: str) -> dict:
    """Summarize TripAdvisor results by limiting to 12 locations."""
    if raw_result.get("error"):
        return raw_result
    
    # Check if this is a location search result
    if "data" in raw_result and isinstance(raw_result["data"], list):
        locations = raw_result["data"]
        if not locations or len(locations) <= 12:
            return raw_result  # Already reasonable size
        
        # Just limit to 12
        raw_result["data"] = locations[:12]
        raw_result["original_count"] = len(locations)
        raw_result["summarized_count"] = 12
        raw_result["summary"] = f"Found {len(locations)} locations, showing top 12"
        return raw_result
    
    # For other result types (reviews, photos, etc.), return as-is
    return raw_result


async def summarize_esim_results(raw_bundles: list, user_message: str, step_context: str) -> dict:
    """Summarize eSIM results by limiting to 30 bundles."""
    if not raw_bundles:
        return {"bundles": [], "count": 0}
    
    # Just limit to 30 bundles
    limited_bundles = raw_bundles[:30]
    
    return {
        "bundles": limited_bundles,
        "count": len(limited_bundles),
        "summary": f"Found {len(raw_bundles)} eSIM bundles, showing top {len(limited_bundles)}"
    }

