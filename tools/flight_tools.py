"""
Flight search and booking tools using SerpApi.
Provides comprehensive flight search capabilities.
"""

import os
import requests
import json
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from datetime import datetime, timedelta


def get_serpapi_key():
    """Get SerpApi key from environment variables."""
    return os.getenv('SERPAPI_API_KEY')


@tool
def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    passengers: int = 1,
    cabin_class: str = "economy"
) -> Dict[str, Any]:
    """
    Search for flights using SerpApi Google Flights.
    
    Args:
        origin: Departure city/airport code (e.g., "NYC", "New York", "JFK")
        destination: Arrival city/airport code (e.g., "LAX", "Los Angeles", "LHR")
        departure_date: Departure date in YYYY-MM-DD format
        return_date: Return date in YYYY-MM-DD format (optional for one-way)
        passengers: Number of passengers (default: 1)
        cabin_class: Cabin class - "economy", "premium_economy", "business", "first"
    
    Returns:
        Dictionary containing flight search results
    """
    api_key = get_serpapi_key()
    if not api_key:
        return {"error": "SerpApi key not found. Please configure SERPAPI_API_KEY."}
    
    try:
        # Prepare search parameters
        params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": departure_date,
            "api_key": api_key
        }
        
        # Add return date for round-trip flights
        if return_date:
            params["return_date"] = return_date
        
        # Add passenger count
        if passengers > 1:
            params["adults"] = passengers
        
        # Add cabin class
        if cabin_class != "economy":
            cabin_mapping = {
                "premium_economy": "premium_economy",
                "business": "business",
                "first": "first"
            }
            if cabin_class in cabin_mapping:
                params["cabin_class"] = cabin_mapping[cabin_class]
        
        # Make API request
        response = requests.get("https://serpapi.com/search", params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract flight information
        flights = []
        if "flights" in data:
            for flight in data["flights"]:
                flight_info = {
                    "airline": flight.get("airline", "Unknown"),
                    "departure_time": flight.get("departure_time", ""),
                    "arrival_time": flight.get("arrival_time", ""),
                    "duration": flight.get("duration", ""),
                    "price": flight.get("price", ""),
                    "stops": flight.get("stops", "Non-stop"),
                    "aircraft": flight.get("aircraft", ""),
                    "booking_url": flight.get("booking_url", ""),
                    "flight_number": flight.get("flight_number", "")
                }
                flights.append(flight_info)
        
        return {
            "success": True,
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "return_date": return_date,
            "passengers": passengers,
            "cabin_class": cabin_class,
            "flights": flights,
            "total_results": len(flights),
            "search_url": data.get("search_metadata", {}).get("google_flights_url", "")
        }
        
    except requests.exceptions.RequestException as e:
        return {"error": f"API request failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}


@tool
def search_flights_by_price(
    origin: str,
    destination: str,
    departure_date: str,
    max_price: float,
    return_date: Optional[str] = None,
    passengers: int = 1
) -> Dict[str, Any]:
    """
    Search for flights under a specific price limit.
    
    Args:
        origin: Departure city/airport code
        destination: Arrival city/airport code
        departure_date: Departure date in YYYY-MM-DD format
        max_price: Maximum price per passenger
        return_date: Return date for round-trip (optional)
        passengers: Number of passengers
    
    Returns:
        Dictionary containing filtered flight results
    """
    # First get all flights
    all_flights = search_flights(origin, destination, departure_date, return_date, passengers)
    
    if "error" in all_flights:
        return all_flights
    
    # Filter by price
    filtered_flights = []
    for flight in all_flights.get("flights", []):
        try:
            # Extract price (remove currency symbols and convert to float)
            price_str = flight.get("price", "").replace("$", "").replace(",", "").replace("USD", "").strip()
            if price_str and price_str.replace(".", "").isdigit():
                price = float(price_str)
                if price <= max_price:
                    filtered_flights.append(flight)
        except (ValueError, TypeError):
            # Skip flights with invalid price format
            continue
    
    return {
        "success": True,
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "return_date": return_date,
        "max_price": max_price,
        "passengers": passengers,
        "flights": filtered_flights,
        "total_results": len(filtered_flights),
        "filtered_from": all_flights.get("total_results", 0)
    }


@tool
def search_flights_by_airline(
    origin: str,
    destination: str,
    departure_date: str,
    airline: str,
    return_date: Optional[str] = None,
    passengers: int = 1
) -> Dict[str, Any]:
    """
    Search for flights with a specific airline.
    
    Args:
        origin: Departure city/airport code
        destination: Arrival city/airport code
        departure_date: Departure date in YYYY-MM-DD format
        airline: Airline name (e.g., "American Airlines", "Delta", "United")
        return_date: Return date for round-trip (optional)
        passengers: Number of passengers
    
    Returns:
        Dictionary containing airline-specific flight results
    """
    # Get all flights first
    all_flights = search_flights(origin, destination, departure_date, return_date, passengers)
    
    if "error" in all_flights:
        return all_flights
    
    # Filter by airline
    filtered_flights = []
    airline_lower = airline.lower()
    
    for flight in all_flights.get("flights", []):
        flight_airline = flight.get("airline", "").lower()
        if airline_lower in flight_airline or flight_airline in airline_lower:
            filtered_flights.append(flight)
    
    return {
        "success": True,
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "return_date": return_date,
        "airline": airline,
        "passengers": passengers,
        "flights": filtered_flights,
        "total_results": len(filtered_flights),
        "filtered_from": all_flights.get("total_results", 0)
    }


@tool
def search_flights_by_duration(
    origin: str,
    destination: str,
    departure_date: str,
    max_duration_hours: float,
    return_date: Optional[str] = None,
    passengers: int = 1
) -> Dict[str, Any]:
    """
    Search for flights under a specific duration limit.
    
    Args:
        origin: Departure city/airport code
        destination: Arrival city/airport code
        departure_date: Departure date in YYYY-MM-DD format
        max_duration_hours: Maximum flight duration in hours
        return_date: Return date for round-trip (optional)
        passengers: Number of passengers
    
    Returns:
        Dictionary containing duration-filtered flight results
    """
    # Get all flights first
    all_flights = search_flights(origin, destination, departure_date, return_date, passengers)
    
    if "error" in all_flights:
        return all_flights
    
    # Filter by duration
    filtered_flights = []
    
    for flight in all_flights.get("flights", []):
        duration_str = flight.get("duration", "")
        try:
            # Parse duration (e.g., "2h 30m", "5h 15m")
            if "h" in duration_str and "m" in duration_str:
                hours_part = duration_str.split("h")[0]
                minutes_part = duration_str.split("h")[1].split("m")[0]
                total_hours = float(hours_part) + float(minutes_part) / 60
            elif "h" in duration_str:
                total_hours = float(duration_str.split("h")[0])
            else:
                continue
            
            if total_hours <= max_duration_hours:
                filtered_flights.append(flight)
        except (ValueError, IndexError):
            # Skip flights with invalid duration format
            continue
    
    return {
        "success": True,
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "return_date": return_date,
        "max_duration_hours": max_duration_hours,
        "passengers": passengers,
        "flights": filtered_flights,
        "total_results": len(filtered_flights),
        "filtered_from": all_flights.get("total_results", 0)
    }


@tool
def get_flight_deals(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    passengers: int = 1
) -> Dict[str, Any]:
    """
    Get the best flight deals and price alerts.
    
    Args:
        origin: Departure city/airport code
        destination: Arrival city/airport code
        departure_date: Departure date in YYYY-MM-DD format
        return_date: Return date for round-trip (optional)
        passengers: Number of passengers
    
    Returns:
        Dictionary containing flight deals and recommendations
    """
    # Get all flights
    all_flights = search_flights(origin, destination, departure_date, return_date, passengers)
    
    if "error" in all_flights:
        return all_flights
    
    flights = all_flights.get("flights", [])
    if not flights:
        return {
            "success": True,
            "message": "No flights found",
            "deals": [],
            "recommendations": []
        }
    
    # Sort flights by price
    try:
        sorted_flights = sorted(flights, key=lambda x: float(x.get("price", "999999").replace("$", "").replace(",", "")))
    except (ValueError, TypeError):
        sorted_flights = flights
    
    # Get cheapest flights
    cheapest_flights = sorted_flights[:3] if len(sorted_flights) >= 3 else sorted_flights
    
    # Get fastest flights (non-stop)
    fastest_flights = [f for f in flights if f.get("stops", "").lower() == "non-stop"][:3]
    
    # Calculate average price
    try:
        prices = [float(f.get("price", "0").replace("$", "").replace(",", "")) for f in flights if f.get("price")]
        avg_price = sum(prices) / len(prices) if prices else 0
    except (ValueError, TypeError):
        avg_price = 0
    
    return {
        "success": True,
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "return_date": return_date,
        "passengers": passengers,
        "total_flights": len(flights),
        "average_price": f"${avg_price:.2f}" if avg_price > 0 else "N/A",
        "cheapest_flights": cheapest_flights,
        "fastest_flights": fastest_flights,
        "deals": cheapest_flights,
        "recommendations": [
            f"Best price: ${cheapest_flights[0].get('price', 'N/A')}" if cheapest_flights else "No deals found",
            f"Fastest option: {fastest_flights[0].get('duration', 'N/A')}" if fastest_flights else "No direct flights",
            f"Average price: ${avg_price:.2f}" if avg_price > 0 else "Price data unavailable"
        ]
    }


@tool
def compare_flight_options(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    passengers: int = 1
) -> Dict[str, Any]:
    """
    Compare different flight options with detailed analysis.
    
    Args:
        origin: Departure city/airport code
        destination: Arrival city/airport code
        departure_date: Departure date in YYYY-MM-DD format
        return_date: Return date for round-trip (optional)
        passengers: Number of passengers
    
    Returns:
        Dictionary containing comprehensive flight comparison
    """
    # Get all flights
    all_flights = search_flights(origin, destination, departure_date, return_date, passengers)
    
    if "error" in all_flights:
        return all_flights
    
    flights = all_flights.get("flights", [])
    if not flights:
        return {
            "success": True,
            "message": "No flights found for comparison",
            "comparison": {}
        }
    
    # Analyze flights
    analysis = {
        "total_options": len(flights),
        "price_range": {"min": 0, "max": 0, "avg": 0},
        "duration_range": {"min": 0, "max": 0, "avg": 0},
        "airlines": [],
        "stop_options": {"non_stop": 0, "one_stop": 0, "multiple_stops": 0},
        "best_value": None,
        "fastest": None,
        "cheapest": None
    }
    
    # Extract prices and durations
    prices = []
    durations = []
    airlines = set()
    
    for flight in flights:
        # Price analysis
        try:
            price_str = flight.get("price", "").replace("$", "").replace(",", "").replace("USD", "").strip()
            if price_str and price_str.replace(".", "").isdigit():
                price = float(price_str)
                prices.append(price)
        except (ValueError, TypeError):
            pass
        
        # Duration analysis
        duration_str = flight.get("duration", "")
        try:
            if "h" in duration_str and "m" in duration_str:
                hours_part = duration_str.split("h")[0]
                minutes_part = duration_str.split("h")[1].split("m")[0]
                total_hours = float(hours_part) + float(minutes_part) / 60
                durations.append(total_hours)
        except (ValueError, IndexError):
            pass
        
        # Airline analysis
        airline = flight.get("airline", "")
        if airline:
            airlines.add(airline)
        
        # Stop analysis
        stops = flight.get("stops", "").lower()
        if "non-stop" in stops:
            analysis["stop_options"]["non_stop"] += 1
        elif "1 stop" in stops or "one stop" in stops:
            analysis["stop_options"]["one_stop"] += 1
        else:
            analysis["stop_options"]["multiple_stops"] += 1
    
    # Calculate ranges
    if prices:
        analysis["price_range"]["min"] = min(prices)
        analysis["price_range"]["max"] = max(prices)
        analysis["price_range"]["avg"] = sum(prices) / len(prices)
    
    if durations:
        analysis["duration_range"]["min"] = min(durations)
        analysis["duration_range"]["max"] = max(durations)
        analysis["duration_range"]["avg"] = sum(durations) / len(durations)
    
    analysis["airlines"] = list(airlines)
    
    # Find best options
    if flights:
        # Cheapest
        try:
            cheapest = min(flights, key=lambda x: float(x.get("price", "999999").replace("$", "").replace(",", "")))
            analysis["cheapest"] = cheapest
        except (ValueError, TypeError):
            pass
        
        # Fastest (non-stop)
        fastest = [f for f in flights if f.get("stops", "").lower() == "non-stop"]
        if fastest:
            analysis["fastest"] = fastest[0]
        
        # Best value (cheapest non-stop)
        best_value = [f for f in flights if f.get("stops", "").lower() == "non-stop"]
        if best_value:
            try:
                analysis["best_value"] = min(best_value, key=lambda x: float(x.get("price", "999999").replace("$", "").replace(",", "")))
            except (ValueError, TypeError):
                analysis["best_value"] = best_value[0]
    
    return {
        "success": True,
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "return_date": return_date,
        "passengers": passengers,
        "analysis": analysis,
        "all_flights": flights
    }
