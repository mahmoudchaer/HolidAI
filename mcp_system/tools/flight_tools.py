"""Flight-related tools for the MCP server."""

import sys
import os
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from dotenv import load_dotenv
from tools.doc_loader import get_doc

# Add flights folder to path to import flight_agent_tools
project_root = Path(__file__).parent.parent.parent
flights_path = project_root / "flights"
sys.path.insert(0, str(flights_path))

try:
    from flight_agent_tools import agent_get_flights, agent_get_flights_flexible, summarize_flights
except ImportError:
    # Fallback if import fails
    def agent_get_flights(*args, **kwargs):
        raise ImportError("Could not import flight_agent_tools module. Please ensure flights/flight_agent_tools.py exists.")
    def agent_get_flights_flexible(*args, **kwargs):
        raise ImportError("Could not import flight_agent_tools module. Please ensure flights/flight_agent_tools.py exists.")
    def summarize_flights(*args, **kwargs):
        raise ImportError("Could not import flight_agent_tools module. Please ensure flights/flight_agent_tools.py exists.")


def _validate_flight_inputs(
    trip_type: str,
    departure: str,
    arrival: str,
    departure_date: str,
    arrival_date: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """Validate flight search inputs and return (is_valid, error_message).
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if not trip_type or not isinstance(trip_type, str):
        return False, "Trip type is required and must be a string ('one-way' or 'round-trip')."
    
    trip_type_lower = trip_type.lower().strip()
    if trip_type_lower not in ["one-way", "round-trip", "oneway", "roundtrip"]:
        return False, f"Invalid trip type: '{trip_type}'. Must be 'one-way' or 'round-trip'."
    
    if not departure or not isinstance(departure, str) or not departure.strip():
        return False, "Departure airport/city code is required and must be a non-empty string (e.g., 'JFK', 'NYC', 'LAX')."
    
    if not arrival or not isinstance(arrival, str) or not arrival.strip():
        return False, "Arrival airport/city code is required and must be a non-empty string (e.g., 'LAX', 'LHR', 'CDG')."
    
    if not departure_date or not isinstance(departure_date, str) or not departure_date.strip():
        return False, "Departure date is required and must be a non-empty string in YYYY-MM-DD format (e.g., '2025-12-10')."
    
    # Basic date format check
    import re
    date_pattern = r'^\d{4}-\d{2}-\d{2}$'
    if not re.match(date_pattern, departure_date):
        return False, f"Invalid departure date format: '{departure_date}'. Expected format: YYYY-MM-DD (e.g., 2025-12-10)."
    
    # For round-trip, arrival_date is required
    if trip_type_lower in ["round-trip", "roundtrip"]:
        if not arrival_date or not isinstance(arrival_date, str) or not arrival_date.strip():
            return False, "Arrival date is required for round-trip flights and must be in YYYY-MM-DD format (e.g., '2025-12-17')."
        if not re.match(date_pattern, arrival_date):
            return False, f"Invalid arrival date format: '{arrival_date}'. Expected format: YYYY-MM-DD (e.g., 2025-12-17)."
    
    return True, None


def register_flight_tools(mcp):
    """Register all flight-related tools with the MCP server."""
    
    @mcp.tool(description=get_doc("agent_get_flights", "flight"))
    def agent_get_flights_tool(
        trip_type: str,
        departure: str,
        arrival: str,
        departure_date: str,
        arrival_date: Optional[str] = None,
        currency: str = "USD",
        airline: Optional[str] = None,
        max_price: Optional[float] = None,
        direct_only: bool = False,
        max_duration: Optional[int] = None,
        dep_after: Optional[str] = None,
        dep_before: Optional[str] = None,
        arr_after: Optional[str] = None,
        arr_before: Optional[str] = None,
        stopover: Optional[str] = None,
        sort_by: Optional[str] = None,
        ascending: bool = True,
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
        travel_class: str = "economy"
    ) -> Dict:
        """Search for flights using SerpAPI Google Flights.
        
        This tool searches for one-way or round-trip flights with extensive
        filtering and sorting options. Supports filtering by airline, price,
        duration, departure/arrival times, direct flights, and more.
        
        Args:
            trip_type: "one-way" or "round-trip" (required)
            departure: Departure airport/city code (e.g., "JFK", "NYC", "LAX") (required)
            arrival: Arrival airport/city code (e.g., "LAX", "LHR", "CDG") (required)
            departure_date: Departure date in YYYY-MM-DD format (required)
            arrival_date: Return date for round-trip in YYYY-MM-DD format (required for round-trip)
            currency: Currency code (default: "USD")
            airline: Filter by airline name (optional)
            max_price: Maximum price filter (optional)
            direct_only: Only show direct flights (default: False)
            max_duration: Maximum flight duration in minutes (optional)
            dep_after: Departure time after (HH:MM format, optional)
            dep_before: Departure time before (HH:MM format, optional)
            arr_after: Arrival time after (HH:MM format, optional)
            arr_before: Arrival time before (HH:MM format, optional)
            stopover: Filter by stopover airport code (optional)
            sort_by: Sort by "price", "duration", "departure", or "arrival" (optional)
            ascending: Sort ascending (default: True)
            adults: Number of adults (default: 1)
            children: Number of children (default: 0)
            infants: Number of infants (default: 0)
            travel_class: "economy", "premium", "business", or "first" (default: "economy")
        
        Returns:
            Dictionary with flight search results
        """
        # Normalize trip_type
        trip_type_normalized = trip_type.lower().strip()
        if trip_type_normalized == "oneway":
            trip_type_normalized = "one-way"
        elif trip_type_normalized == "roundtrip":
            trip_type_normalized = "round-trip"
        
        # Validate inputs first
        is_valid, validation_error = _validate_flight_inputs(
            trip_type_normalized, departure, arrival, departure_date, arrival_date
        )
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": validation_error,
                "outbound": [],
                "return": [],
                "suggestion": "Please check your flight search parameters and try again."
            }
        
        # Validate numeric inputs
        if adults < 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid number of adults: {adults}. Must be 0 or greater.",
                "outbound": [],
                "return": [],
                "suggestion": "Please provide a valid number of adults (0 or more)."
            }
        
        if children < 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid number of children: {children}. Must be 0 or greater.",
                "outbound": [],
                "return": [],
                "suggestion": "Please provide a valid number of children (0 or more)."
            }
        
        if infants < 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid number of infants: {infants}. Must be 0 or greater.",
                "outbound": [],
                "return": [],
                "suggestion": "Please provide a valid number of infants (0 or more)."
            }
        
        if max_price is not None and max_price <= 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid max_price: {max_price}. Must be a positive number.",
                "outbound": [],
                "return": [],
                "suggestion": "Please provide a positive number for max_price."
            }
        
        try:
            # Call the flight search function
            result = agent_get_flights(
                trip_type=trip_type_normalized,
                dep=departure.strip().upper(),
                arr=arrival.strip().upper(),
                dep_date=departure_date.strip(),
                arr_date=arrival_date.strip() if arrival_date else None,
                currency=currency.upper() if currency else "USD",
                airline=airline.strip() if airline else None,
                max_price=max_price,
                direct_only=direct_only,
                max_duration=max_duration,
                dep_after=dep_after.strip() if dep_after else None,
                dep_before=dep_before.strip() if dep_before else None,
                arr_after=arr_after.strip() if arr_after else None,
                arr_before=arr_before.strip() if arr_before else None,
                stopover=stopover.strip().upper() if stopover else None,
                sort_by=sort_by.lower() if sort_by else None,
                ascending=ascending,
                adults=adults,
                children=children,
                infants=infants,
                travel_class=travel_class
            )
            
            return {
                "error": False,
                "outbound": result.get("outbound", []),
                "return": result.get("return", []),
                "passengers": result.get("_passengers", {"adults": adults, "children": children, "infants": infants}),
                "trip_type": trip_type_normalized,
                "departure": departure.strip().upper(),
                "arrival": arrival.strip().upper(),
                "departure_date": departure_date.strip(),
                "arrival_date": arrival_date.strip() if arrival_date else None
            }
            
        except ValueError as e:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid parameter: {str(e)}",
                "outbound": [],
                "return": [],
                "suggestion": "Please check your flight search parameters and try again."
            }
        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e)
            
            # Provide helpful error messages
            if "timeout" in error_message.lower() or "Timeout" in error_type:
                return {
                    "error": True,
                    "error_code": "TIMEOUT",
                    "error_message": "The flight search took too long to complete. The flight service may be slow or unavailable.",
                    "outbound": [],
                    "return": [],
                    "suggestion": "Please try again in a few moments. If the problem persists, the flight service may be temporarily unavailable."
                }
            elif "api" in error_message.lower() or "serpapi" in error_message.lower():
                return {
                    "error": True,
                    "error_code": "API_ERROR",
                    "error_message": f"Flight API error: {error_message}",
                    "outbound": [],
                    "return": [],
                    "suggestion": "Please verify your API credentials and try again. If the problem persists, contact support."
                }
            else:
                return {
                    "error": True,
                    "error_code": "UNEXPECTED_ERROR",
                    "error_message": f"An unexpected error occurred while searching for flights: {error_message}",
                    "outbound": [],
                    "return": [],
                    "suggestion": "Please try again. If the problem persists, contact support."
                }
    
    @mcp.tool(description=get_doc("agent_get_flights_flexible", "flight"))
    def agent_get_flights_flexible_tool(
        trip_type: str,
        departure: str,
        arrival: str,
        departure_date: str,
        arrival_date: Optional[str] = None,
        currency: str = "USD",
        airline: Optional[str] = None,
        max_price: Optional[float] = None,
        direct_only: bool = False,
        max_duration: Optional[int] = None,
        dep_after: Optional[str] = None,
        dep_before: Optional[str] = None,
        arr_after: Optional[str] = None,
        arr_before: Optional[str] = None,
        stopover: Optional[str] = None,
        sort_by: Optional[str] = None,
        ascending: bool = True,
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
        travel_class: str = "economy",
        days_flex: int = 3
    ) -> Dict:
        """Search for flights with flexible dates (±days_flex around departure_date).
        
        This tool performs the same flight search for multiple dates around the
        specified departure date, allowing users to find the best prices across
        a date range. Useful for finding cheaper flights when travel dates are flexible.
        
        Args:
            trip_type: "one-way" or "round-trip" (required)
            departure: Departure airport/city code (e.g., "JFK", "NYC", "LAX") (required)
            arrival: Arrival airport/city code (e.g., "LAX", "LHR", "CDG") (required)
            departure_date: Center departure date in YYYY-MM-DD format (required)
            arrival_date: Return date for round-trip in YYYY-MM-DD format (required for round-trip)
            currency: Currency code (default: "USD")
            airline: Filter by airline name (optional)
            max_price: Maximum price filter (optional)
            direct_only: Only show direct flights (default: False)
            max_duration: Maximum flight duration in minutes (optional)
            dep_after: Departure time after (HH:MM format, optional)
            dep_before: Departure time before (HH:MM format, optional)
            arr_after: Arrival time after (HH:MM format, optional)
            arr_before: Arrival time before (HH:MM format, optional)
            stopover: Filter by stopover airport code (optional)
            sort_by: Sort by "price", "duration", "departure", or "arrival" (optional)
            ascending: Sort ascending (default: True)
            adults: Number of adults (default: 1)
            children: Number of children (default: 0)
            infants: Number of infants (default: 0)
            travel_class: "economy", "premium", "business", or "first" (default: "economy")
            days_flex: Number of days flexibility (±days_flex around departure_date, default: 3, max: 7)
        
        Returns:
            Dictionary with flight search results across multiple dates
        """
        # Normalize trip_type
        trip_type_normalized = trip_type.lower().strip()
        if trip_type_normalized == "oneway":
            trip_type_normalized = "one-way"
        elif trip_type_normalized == "roundtrip":
            trip_type_normalized = "round-trip"
        
        # Validate inputs first
        is_valid, validation_error = _validate_flight_inputs(
            trip_type_normalized, departure, arrival, departure_date, arrival_date
        )
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": validation_error,
                "flights": [],
                "suggestion": "Please check your flight search parameters and try again."
            }
        
        # Validate days_flex
        if days_flex < 0 or days_flex > 7:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid days_flex: {days_flex}. Must be between 0 and 7.",
                "flights": [],
                "suggestion": "Please provide days_flex between 0 and 7."
            }
        
        # Validate numeric inputs (same as agent_get_flights_tool)
        if adults < 0 or children < 0 or infants < 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": "Number of passengers (adults, children, infants) must be 0 or greater.",
                "flights": [],
                "suggestion": "Please provide valid passenger counts."
            }
        
        if max_price is not None and max_price <= 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid max_price: {max_price}. Must be a positive number.",
                "flights": [],
                "suggestion": "Please provide a positive number for max_price."
            }
        
        try:
            # Call the flexible flight search function
            result = agent_get_flights_flexible(
                trip_type=trip_type_normalized,
                dep=departure.strip().upper(),
                arr=arrival.strip().upper(),
                dep_date=departure_date.strip(),
                arr_date=arrival_date.strip() if arrival_date else None,
                currency=currency.upper() if currency else "USD",
                airline=airline.strip() if airline else None,
                max_price=max_price,
                direct_only=direct_only,
                max_duration=max_duration,
                dep_after=dep_after.strip() if dep_after else None,
                dep_before=dep_before.strip() if dep_before else None,
                arr_after=arr_after.strip() if arr_after else None,
                arr_before=arr_before.strip() if arr_before else None,
                stopover=stopover.strip().upper() if stopover else None,
                sort_by=sort_by.lower() if sort_by else None,
                ascending=ascending,
                adults=adults,
                children=children,
                infants=infants,
                travel_class=travel_class,
                days_flex=days_flex
            )
            
            return {
                "error": False,
                "flights": result.get("flights", []),
                "passengers": result.get("_passengers", {"adults": adults, "children": children, "infants": infants}),
                "trip_type": trip_type_normalized,
                "departure": departure.strip().upper(),
                "arrival": arrival.strip().upper(),
                "departure_date": departure_date.strip(),
                "arrival_date": arrival_date.strip() if arrival_date else None,
                "days_flex": days_flex
            }
            
        except ValueError as e:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid parameter: {str(e)}",
                "flights": [],
                "suggestion": "Please check your flight search parameters and try again."
            }
        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e)
            
            # Provide helpful error messages
            if "timeout" in error_message.lower() or "Timeout" in error_type:
                return {
                    "error": True,
                    "error_code": "TIMEOUT",
                    "error_message": "The flexible flight search took too long to complete. The flight service may be slow or unavailable.",
                    "flights": [],
                    "suggestion": "Please try again in a few moments. If the problem persists, the flight service may be temporarily unavailable."
                }
            elif "api" in error_message.lower() or "serpapi" in error_message.lower():
                return {
                    "error": True,
                    "error_code": "API_ERROR",
                    "error_message": f"Flight API error: {error_message}",
                    "flights": [],
                    "suggestion": "Please verify your API credentials and try again. If the problem persists, contact support."
                }
            else:
                return {
                    "error": True,
                    "error_code": "UNEXPECTED_ERROR",
                    "error_message": f"An unexpected error occurred while searching for flights: {error_message}",
                    "flights": [],
                    "suggestion": "Please try again. If the problem persists, contact support."
                }

