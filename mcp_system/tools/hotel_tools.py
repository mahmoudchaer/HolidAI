"""Hotel-related tools for the MCP server."""

import os
import httpx
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
from tools.doc_loader import get_doc

# Load environment variables from .env file in main directory
# Get the project root directory (2 levels up from mcp_system/tools/)
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# API configuration
API_ENDPOINT = "https://api.liteapi.travel/v3.0/hotels/rates"
HOTEL_DETAILS_ENDPOINT = "https://api.liteapi.travel/v3.0/data/hotel"
HOTELS_LIST_ENDPOINT = "https://api.liteapi.travel/v3.0/data/hotels"
API_KEY = os.getenv("LITEAPI_KEY")

# Validate that required credentials are set
if not API_KEY:
    raise ValueError(
        "Missing required API credentials in .env file. "
        "Please set LITEAPI_KEY"
    )


def _validate_hotel_inputs(
    checkin: str,
    checkout: str,
    occupancies: List[Dict],
    hotel_ids: Optional[List[str]] = None,
    city_name: Optional[str] = None,
    country_code: Optional[str] = None,
    iata_code: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """Validate hotel rates search inputs and return (is_valid, error_message).
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    # Basic date format check
    date_pattern = r'^\d{4}-\d{2}-\d{2}$'
    if not re.match(date_pattern, checkin):
        return False, f"Invalid check-in date format: '{checkin}'. Expected format: YYYY-MM-DD (e.g., 2025-12-10)."
    
    if not re.match(date_pattern, checkout):
        return False, f"Invalid check-out date format: '{checkout}'. Expected format: YYYY-MM-DD (e.g., 2025-12-17)."
    
    try:
        checkin_date = datetime.strptime(checkin, "%Y-%m-%d")
        checkout_date = datetime.strptime(checkout, "%Y-%m-%d")
        
        # Check that checkout is after checkin
        if checkout_date <= checkin_date:
            return False, f"Check-out date '{checkout}' must be after check-in date '{checkin}'. Please ensure the check-out date is later than the check-in date."
    except ValueError:
        return False, "Invalid date format. Please use YYYY-MM-DD format (e.g., 2025-12-10)."
    
    # Validate occupancies
    if not occupancies or len(occupancies) == 0:
        return False, "At least one occupancy is required. Please provide occupancies array with at least one room."
    
    for i, occupancy in enumerate(occupancies):
        if not isinstance(occupancy, dict):
            return False, f"Occupancy {i+1}: Must be an object with 'adults' field."
        
        if "adults" not in occupancy:
            return False, f"Occupancy {i+1}: Missing required field 'adults'. Each occupancy must specify the number of adults."
        
        adults = occupancy.get("adults")
        if not isinstance(adults, int) or adults < 1:
            return False, f"Occupancy {i+1}: 'adults' must be a positive integer (at least 1)."
        
        children = occupancy.get("children", [])
        if children and not isinstance(children, list):
            return False, f"Occupancy {i+1}: 'children' must be an array of integers (ages)."
    
    # Validate that at least one location identifier is provided
    location_provided = bool(hotel_ids) or bool(city_name and country_code) or bool(iata_code)
    if not location_provided:
        return False, "At least one location identifier is required. Please provide either: hotelIds, (cityName and countryCode), or iataCode."
    
    # If city_name is provided, country_code must also be provided
    if city_name and not country_code:
        return False, "If 'cityName' is provided, 'countryCode' must also be provided. Please provide both cityName and countryCode."
    
    return True, None


def _build_request_payload(
    checkin: str,
    checkout: str,
    occupancies: List[Dict],
    hotel_ids: Optional[List[str]] = None,
    city_name: Optional[str] = None,
    country_code: Optional[str] = None,
    iata_code: Optional[str] = None,
    currency: str = "USD",
    guest_nationality: str = "US",
    max_rates_per_hotel: int = 1,
    refundable_rates_only: bool = False,
    room_mapping: bool = True
) -> Dict:
    """Build the API request payload with defaults."""
    # Ensure boolean values are actual booleans, not strings (safety check)
    if isinstance(refundable_rates_only, str):
        refundable_rates_only = refundable_rates_only.lower() in ("true", "1", "yes")
    if isinstance(room_mapping, str):
        room_mapping = room_mapping.lower() in ("true", "1", "yes")
    
    # Ensure max_rates_per_hotel is an integer
    if isinstance(max_rates_per_hotel, str):
        try:
            max_rates_per_hotel = int(max_rates_per_hotel)
        except (ValueError, TypeError):
            max_rates_per_hotel = 1
    
    payload = {
        "checkin": checkin,
        "checkout": checkout,
        "occupancies": occupancies,
        "currency": currency,
        "guestNationality": guest_nationality,
        "maxRatesPerHotel": max_rates_per_hotel,
        "refundableRatesOnly": bool(refundable_rates_only),  # Explicit bool conversion
        "roomMapping": bool(room_mapping)  # Explicit bool conversion
    }
    
    # Add location identifier (at least one must be provided)
    if hotel_ids:
        payload["hotelIds"] = hotel_ids
    elif city_name and country_code:
        payload["cityName"] = city_name
        payload["countryCode"] = country_code
    elif iata_code:
        payload["iataCode"] = iata_code
    
    return payload


def _extract_hotel_price(hotel: Dict) -> float:
    """Extract the minimum price from a hotel object.
    
    Args:
        hotel: Hotel object from API response
        
    Returns:
        Minimum price as float, or infinity if price not found
    """
    try:
        min_price = float('inf')
        
        # Check if hotel has roomTypes
        if "roomTypes" in hotel and isinstance(hotel["roomTypes"], list):
            for room_type in hotel["roomTypes"]:
                # Try offerRetailRate.amount first (most common)
                if "offerRetailRate" in room_type and "amount" in room_type["offerRetailRate"]:
                    price = float(room_type["offerRetailRate"]["amount"])
                    min_price = min(min_price, price)
                
                # Also check rates array for retailRate.total
                if "rates" in room_type and isinstance(room_type["rates"], list):
                    for rate in room_type["rates"]:
                        if "retailRate" in rate and "total" in rate["retailRate"]:
                            if isinstance(rate["retailRate"]["total"], list) and len(rate["retailRate"]["total"]) > 0:
                                if "amount" in rate["retailRate"]["total"][0]:
                                    price = float(rate["retailRate"]["total"][0]["amount"])
                                    min_price = min(min_price, price)
        
        # If still infinity, try direct price fields
        if min_price == float('inf'):
            if "price" in hotel:
                min_price = float(hotel["price"])
            elif "amount" in hotel:
                min_price = float(hotel["amount"])
        
        return min_price if min_price != float('inf') else float('inf')
    except (ValueError, KeyError, TypeError, AttributeError):
        return float('inf')  # Return infinity for invalid prices to sort them last


def _parse_and_sort_hotels(api_response: Dict, sort_by: Optional[str] = None, top_k: Optional[int] = None) -> Tuple[List[Dict], Optional[str]]:
    """Parse API response and optionally sort hotels.
    
    Args:
        api_response: The raw API response
        sort_by: Optional sort key - 'price' to sort by price (lowest first)
        top_k: Optional limit to return only top k results after sorting
    
    Returns:
        Tuple of (List of hotel objects, Optional error message)
    """
    try:
        # Extract hotels from response
        hotels = []
        if "data" in api_response:
            data = api_response["data"]
            if isinstance(data, list):
                hotels = data
            elif "offers" in data:
                hotels = data["offers"]
            elif "hotels" in data:
                hotels = data["hotels"]
        elif "offers" in api_response:
            hotels = api_response["offers"]
        elif "hotels" in api_response:
            hotels = api_response["hotels"]
        elif isinstance(api_response, list):
            hotels = api_response
        
        if not hotels:
            return [], None  # No hotels found is not an error
        
        # Sort by price if requested
        if sort_by == "price":
            try:
                hotels.sort(key=_extract_hotel_price)
            except Exception as e:
                return [], f"Error sorting hotels by price: {str(e)}. Returning unsorted results."
        
        # Limit to top k if specified
        if top_k is not None and top_k > 0:
            hotels = hotels[:top_k]
        
        return hotels, None
    except (KeyError, TypeError, AttributeError) as e:
        return [], f"Error parsing hotel search results: {str(e)}. The response format may have changed."


def _make_api_call(request_payload: Dict, top_k: Optional[int] = None, sort_by: Optional[str] = None) -> Dict:
    """Helper function to make API calls with error handling.
    
    Args:
        request_payload: The API request payload
        top_k: Optional limit to return only top k results
        
    Returns:
        Dict with error status and results
    """
    try:
        # Ensure required fields are present (safety check)
        if "guestNationality" not in request_payload:
            request_payload["guestNationality"] = "US"  # Default fallback
            print("[HOTEL API] WARNING: guestNationality was missing, using default 'US'")
        if "currency" not in request_payload:
            request_payload["currency"] = "USD"  # Default fallback
            print("[HOTEL API] WARNING: currency was missing, using default 'USD'")
        
        # Log the request for debugging
        print(f"[HOTEL API] Making request to {API_ENDPOINT}")
        print(f"[HOTEL API] Payload keys: {list(request_payload.keys())}")
        print(f"[HOTEL API] guestNationality: {request_payload.get('guestNationality')}")
        print(f"[HOTEL API] currency: {request_payload.get('currency')}")
        
        # Make API request
        with httpx.Client(timeout=12.0) as client:
            response = client.post(
                API_ENDPOINT,
                json=request_payload,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": API_KEY
                }
            )
            
            # Handle 204 No Content
            if response.status_code == 204:
                return {
                    "error": False,
                    "message": "No hotel rates found for the specified criteria. Try different dates, location, or search parameters.",
                    "hotels": []
                }
            
            # Handle 400 Bad Request
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    error_message = error_data.get("message", "Bad request: Invalid parameters sent to hotel API.")
                    if isinstance(error_message, dict):
                        error_message = str(error_message)
                    print(f"[HOTEL API] 400 Bad Request - API Error: {error_message}")
                    print(f"[HOTEL API] Full error response: {error_data}")
                except Exception as parse_err:
                    error_message = f"Bad request: Invalid parameters sent to hotel API. Response parsing error: {parse_err}"
                    print(f"[HOTEL API] 400 Bad Request - Could not parse error response: {response.text[:500]}")
                
                return {
                    "error": True,
                    "error_code": "BAD_REQUEST",
                    "error_message": f"Invalid search parameters: {error_message}",
                    "api_error_details": error_message,
                    "hotels": [],
                    "suggestion": "Please verify your search parameters (dates, location, occupancies) and try again."
                }
            
            # Handle other HTTP errors
            response.raise_for_status()
            
            # Handle 200 OK
            api_response = response.json()
            
            # Check if response has errors
            if "errors" in api_response or "error" in api_response:
                error_info = api_response.get("errors") or api_response.get("error", {})
                if isinstance(error_info, list) and len(error_info) > 0:
                    error_message = error_info[0].get("message", "Unknown error occurred")
                elif isinstance(error_info, dict):
                    error_message = error_info.get("message", "Unknown error occurred")
                else:
                    error_message = str(error_info) if error_info else "Unknown error occurred"
                
                return {
                    "error": True,
                    "error_code": "API_ERROR",
                    "error_message": "The hotel search service encountered an error. Please try again with different parameters.",
                    "hotels": [],
                    "suggestion": "Please try again with different search parameters. If the problem persists, contact support."
                }
            
            # Parse and optionally sort hotels
            hotels, parse_error = _parse_and_sort_hotels(api_response, sort_by, top_k)
            
            # If parsing had an error but we still got some hotels, include a warning
            if parse_error and not hotels:
                return {
                    "error": True,
                    "error_code": "PARSE_ERROR",
                    "error_message": parse_error,
                    "hotels": [],
                    "suggestion": "The hotel search completed but we couldn't process the results. Please try again or contact support."
                }
            
            # Process successful response (don't expose raw API response to agent)
            result = {
                "error": False,
                "hotels": hotels,
                "search_params": {
                    "checkin": request_payload.get("checkin"),
                    "checkout": request_payload.get("checkout"),
                    "location": (
                        request_payload.get("hotelIds") or
                        f"{request_payload.get('cityName', '')}, {request_payload.get('countryCode', '')}" or
                        request_payload.get("iataCode", "")
                    ),
                    "top_k": top_k if top_k else None,
                    "sort_by": sort_by if sort_by else "none"
                }
            }
            
            # Add warning if parsing had issues but hotels were still returned
            if parse_error:
                result["warning"] = parse_error
            
            # Add helpful message if no hotels found
            if not hotels:
                result["message"] = "No hotel rates found for the specified criteria. Try different dates, location, or search parameters."
            
            return result
            
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        # Try to get detailed error information from response
        try:
            error_response = e.response.json()
            api_error_message = error_response.get("message") or error_response.get("error") or str(error_response)
        except Exception:
            api_error_message = e.response.text[:500] if hasattr(e.response, 'text') else "No error details available"
        
        # Log detailed error information
        print(f"[HOTEL API ERROR] Status Code: {status_code}")
        print(f"[HOTEL API ERROR] Response: {api_error_message}")
        print(f"[HOTEL API ERROR] Request URL: {API_ENDPOINT}")
        print(f"[HOTEL API ERROR] Request Payload: {request_payload}")
        
        if status_code == 400:
            error_msg = f"Invalid search parameters: {api_error_message}"
        elif status_code == 401:
            error_msg = f"Authentication failed: {api_error_message}"
        elif status_code == 403:
            error_msg = f"Access denied: {api_error_message}"
        elif status_code == 404:
            error_msg = f"Service endpoint not found: {api_error_message}"
        elif status_code == 429:
            error_msg = f"Too many requests: {api_error_message}"
        elif status_code == 500:
            error_msg = f"Internal server error from LiteAPI: {api_error_message}"
        elif status_code == 503:
            error_msg = f"Service temporarily unavailable: {api_error_message}"
        else:
            error_msg = f"HTTP {status_code} error: {api_error_message}"
        
        return {
            "error": True,
            "error_code": "HTTP_ERROR",
            "error_message": error_msg,
            "http_status_code": status_code,
            "api_error_details": api_error_message,
            "hotels": [],
            "suggestion": "Please verify your search parameters and try again. If the problem persists, contact support."
        }
    except httpx.TimeoutException:
        return {
            "error": True,
            "error_code": "TIMEOUT",
            "error_message": "Request timeout: The hotel search took too long to respond (over 12 seconds).",
            "hotels": [],
            "suggestion": "The hotel search service may be experiencing high load. Please try again in a few moments."
        }
    except httpx.RequestError as e:
        return {
            "error": True,
            "error_code": "NETWORK_ERROR",
            "error_message": f"Network error: Unable to connect to hotel search service. {str(e)}",
            "hotels": [],
            "suggestion": "Please check your internet connection and try again. If the problem persists, the service may be temporarily unavailable."
        }
    except Exception:
        return {
            "error": True,
            "error_code": "UNEXPECTED_ERROR",
            "error_message": "An unexpected error occurred during hotel search. Please try again.",
            "hotels": [],
            "suggestion": "An unexpected error occurred. Please try again or contact support if the problem persists."
        }


def _make_hotel_details_api_call(hotel_id: str, language: Optional[str] = None, timeout: float = 4.0) -> Dict:
    """Helper function to make GET request for hotel details with error handling.
    
    Args:
        hotel_id: The unique hotel ID
        language: Optional language code (e.g., 'en', 'fr')
        timeout: Request timeout in seconds (default: 4.0)
        
    Returns:
        Dict with error status and hotel details
    """
    try:
        # Build query parameters
        params = {"hotelId": hotel_id}
        if language:
            params["language"] = language
        if timeout:
            params["timeout"] = timeout
        
        # Make API request
        with httpx.Client(timeout=timeout + 2.0) as client:
            response = client.get(
                HOTEL_DETAILS_ENDPOINT,
                params=params,
                headers={
                    "X-API-Key": API_KEY
                }
            )
            
            # Handle 400 Bad Request
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    error_message = error_data.get("message", "Bad request: Invalid hotel ID.")
                    if isinstance(error_message, dict):
                        error_message = str(error_message)
                except Exception:
                    error_message = "Bad request: Invalid hotel ID provided."
                
                return {
                    "error": True,
                    "error_code": "BAD_REQUEST",
                    "error_message": "Invalid hotel ID provided. Please check the hotel ID and try again.",
                    "hotel": None,
                    "suggestion": "Please verify the hotel ID is correct and try again."
                }
            
            # Handle 401 Unauthorized
            if response.status_code == 401:
                return {
                    "error": True,
                    "error_code": "UNAUTHORIZED",
                    "error_message": "Authentication failed. Please check your API credentials.",
                    "hotel": None,
                    "suggestion": "Please verify your API credentials are correct."
                }
            
            # Handle other HTTP errors
            response.raise_for_status()
            
            # Handle 200 OK
            api_response = response.json()
            
            # Check if response has errors
            if "errors" in api_response or "error" in api_response:
                error_info = api_response.get("errors") or api_response.get("error", {})
                if isinstance(error_info, list) and len(error_info) > 0:
                    error_message = error_info[0].get("message", "Unknown error occurred")
                elif isinstance(error_info, dict):
                    error_message = error_info.get("message", "Unknown error occurred")
                else:
                    error_message = str(error_info) if error_info else "Unknown error occurred"
                
                return {
                    "error": True,
                    "error_code": "API_ERROR",
                    "error_message": "The hotel details service encountered an error. Please try again.",
                    "hotel": None,
                    "suggestion": "Please try again. If the problem persists, contact support."
                }
            
            # Extract hotel data from response
            hotel_data = None
            if "data" in api_response:
                hotel_data = api_response["data"]
            elif isinstance(api_response, dict) and "id" in api_response:
                hotel_data = api_response
            
            if not hotel_data:
                return {
                    "error": True,
                    "error_code": "PARSE_ERROR",
                    "error_message": "Hotel details not found in the response.",
                    "hotel": None,
                    "suggestion": "Please try again or contact support if the problem persists."
                }
            
            # Process successful response
            return {
                "error": False,
                "hotel": hotel_data
            }
            
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        if status_code == 400:
            error_msg = "Invalid hotel ID provided. Please check your input and try again."
        elif status_code == 401:
            error_msg = "Authentication failed. Please check your API credentials."
        elif status_code == 404:
            error_msg = "Hotel not found. Please verify the hotel ID is correct."
        elif status_code == 429:
            error_msg = "Too many requests. Please wait a moment and try again."
        elif status_code == 500:
            error_msg = "Internal server error. Please try again later."
        elif status_code == 503:
            error_msg = "Service temporarily unavailable. Please try again later."
        else:
            error_msg = "The hotel details service returned an error. Please try again."
        
        return {
            "error": True,
            "error_code": "HTTP_ERROR",
            "error_message": error_msg,
            "hotel": None,
            "suggestion": "Please try again. If the problem persists, contact support."
        }
    except httpx.TimeoutException:
        return {
            "error": True,
            "error_code": "TIMEOUT",
            "error_message": "Request timed out while fetching hotel details. Please try again.",
            "hotel": None,
            "suggestion": "Please try again. The service may be experiencing high load."
        }
    except httpx.NetworkError as e:
        return {
            "error": True,
            "error_code": "NETWORK_ERROR",
            "error_message": f"Network error: Unable to connect to hotel details service. {str(e)}",
            "hotel": None,
            "suggestion": "Please check your internet connection and try again. If the problem persists, the service may be temporarily unavailable."
        }
    except Exception:
        return {
            "error": True,
            "error_code": "UNEXPECTED_ERROR",
            "error_message": "An unexpected error occurred while fetching hotel details. Please try again.",
            "hotel": None,
            "suggestion": "An unexpected error occurred. Please try again or contact support if the problem persists."
        }


def _make_hotels_list_api_call(
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
    hotel_name: Optional[str] = None,
    offset: int = 0,
    limit: int = 100,
    longitude: Optional[float] = None,
    latitude: Optional[float] = None,
    radius: Optional[int] = None,
    min_rating: Optional[float] = None,
    min_reviews_count: Optional[int] = None,
    star_rating: Optional[str] = None,
    hotel_ids: Optional[str] = None,
    timeout: float = 10.0
) -> Dict:
    """Make API call to list/search hotels.
    
    Args:
        country_code: Country code ISO-2 code (e.g., 'SG', 'US')
        city_name: Name of the city
        hotel_name: Name of the hotel (loose match, case-insensitive)
        offset: Number of rows to skip before returning
        limit: Maximum number of results (default: 100, max: 5000)
        longitude: Longitude geo coordinates
        latitude: Latitude geo coordinates
        radius: Radius in meters (min 1000m)
        min_rating: Minimum rating of the hotel (e.g., 8.6)
        min_reviews_count: Minimum number of reviews
        star_rating: Comma-separated list of star ratings (e.g., '3.5,4.0,5.0')
        hotel_ids: Comma-separated list of hotel IDs (e.g., 'lp1897,lp1343')
        timeout: Request timeout in seconds
        
    Returns:
        Dict with hotel list or error information
    """
    try:
        # Build query parameters
        params = {
            "offset": offset,
            "limit": min(limit, 5000)  # Cap at API maximum
        }
        
        if country_code:
            params["countryCode"] = country_code
        if city_name:
            params["cityName"] = city_name
        if hotel_name:
            params["hotelName"] = hotel_name
        if longitude is not None:
            params["longitude"] = longitude
        if latitude is not None:
            params["latitude"] = latitude
        if radius is not None:
            params["radius"] = max(radius, 1000)  # Minimum 1000m
        if min_rating is not None:
            params["minRating"] = min_rating
        if min_reviews_count is not None:
            params["minReviewsCount"] = min_reviews_count
        if star_rating:
            params["starRating"] = star_rating
        if hotel_ids:
            params["hotelIds"] = hotel_ids
        
        headers = {
            "X-API-Key": API_KEY,
            "Accept": "application/json"
        }
        
        with httpx.Client(timeout=timeout) as client:
            response = client.get(
                HOTELS_LIST_ENDPOINT,
                params=params,
                headers=headers
            )
            
            # Check for HTTP errors
            if response.status_code == 401:
                return {
                    "error": True,
                    "error_code": "UNAUTHORIZED",
                    "error_message": "Invalid API key. Please check your API credentials.",
                    "hotels": [],
                    "total": 0
                }
            
            if response.status_code == 400:
                error_data = response.json() if response.text else {}
                return {
                    "error": True,
                    "error_code": "BAD_REQUEST",
                    "error_message": error_data.get("message", "Invalid request parameters."),
                    "hotels": [],
                    "total": 0
                }
            
            if response.status_code != 200:
                return {
                    "error": True,
                    "error_code": "API_ERROR",
                    "error_message": f"Hotel list API returned status {response.status_code}.",
                    "hotels": [],
                    "total": 0
                }
            
            # Parse response
            data = response.json()
            
            return {
                "error": False,
                "hotels": data.get("data", []),
                "hotel_ids": data.get("hotelIds", []),
                "total": data.get("total", 0)
            }
            
    except httpx.TimeoutException:
        return {
            "error": True,
            "error_code": "TIMEOUT",
            "error_message": f"Request timed out after {timeout} seconds.",
            "hotels": [],
            "total": 0,
            "suggestion": "Try again or increase the timeout value."
        }
    except httpx.RequestError as e:
        return {
            "error": True,
            "error_code": "NETWORK_ERROR",
            "error_message": f"Network error occurred: {str(e)}",
            "hotels": [],
            "total": 0,
            "suggestion": "Check your internet connection and try again."
        }
    except Exception as e:
        return {
            "error": True,
            "error_code": "UNKNOWN_ERROR",
            "error_message": f"An unexpected error occurred: {str(e)}",
            "hotels": [],
            "total": 0,
            "suggestion": "Please try again or contact support if the issue persists."
        }


def register_hotel_tools(mcp):
    """Register all hotel-related tools with the MCP server."""
    
    @mcp.tool(description=get_doc("get_hotel_rates", "hotel"))
    def get_hotel_rates(
        checkin: str,
        checkout: str,
        occupancies: List[Dict],
        hotel_ids: Optional[List[str]] = None,
        city_name: Optional[str] = None,
        country_code: Optional[str] = None,
        iata_code: Optional[str] = None,
        currency: Optional[str] = None,
        guest_nationality: Optional[str] = None,
        max_rates_per_hotel: Optional[int] = None,
        refundable_rates_only: Optional[bool] = None,
        room_mapping: Optional[bool] = None,
        k: Optional[int] = None
    ) -> Dict:
        """Get hotel rates. Accepts minimal input and auto-fills defaults.
        
        At least one location identifier must be provided: hotelIds, (cityName and countryCode), or iataCode.
        """
        # Set defaults
        currency = currency or "USD"
        guest_nationality = guest_nationality or "US"
        
        # Convert string booleans to actual booleans (MCP may pass strings)
        if isinstance(refundable_rates_only, str):
            refundable_rates_only = refundable_rates_only.lower() in ("true", "1", "yes")
        if isinstance(room_mapping, str):
            room_mapping = room_mapping.lower() in ("true", "1", "yes")
        
        # Convert numeric parameters (might come as strings from JSON)
        try:
            if max_rates_per_hotel is not None:
                max_rates_per_hotel = int(max_rates_per_hotel) if not isinstance(max_rates_per_hotel, int) else max_rates_per_hotel
            else:
                max_rates_per_hotel = 1
        except (ValueError, TypeError):
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid max_rates_per_hotel value: {max_rates_per_hotel}. Must be an integer.",
                "hotels": []
            }
        
        try:
            if k is not None:
                k = int(k) if not isinstance(k, int) else k
            else:
                k = 10  # Default to 10 hotels
        except (ValueError, TypeError):
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid k value: {k}. Must be an integer.",
                "hotels": []
            }
        
        refundable_rates_only = refundable_rates_only if refundable_rates_only is not None else False
        room_mapping = room_mapping if room_mapping is not None else True
        
        # Validate k parameter first
        if k <= 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid value for parameter 'k': {k}. The parameter 'k' must be a positive integer (e.g., 1, 5, 10).",
                "hotels": [],
                "suggestion": "Please provide a positive number for 'k' (e.g., k=5 to get top 5 hotels)."
            }
        
        if k > 200:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Parameter 'k' ({k}) is too large. Maximum allowed is 200 results.",
                "hotels": [],
                "suggestion": "Please reduce 'k' to 200 or less. For example, use k=10 to get top 10 results."
            }
        
        # Validate inputs first
        is_valid, validation_error = _validate_hotel_inputs(
            checkin, checkout, occupancies, hotel_ids, city_name, country_code, iata_code
        )
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": validation_error,
                "hotels": [],
                "suggestion": "Please correct the input parameters and try again."
            }
        
        # Build API request payload
        request_payload = _build_request_payload(
            checkin=checkin,
            checkout=checkout,
            occupancies=occupancies,
            hotel_ids=hotel_ids,
            city_name=city_name,
            country_code=country_code,
            iata_code=iata_code,
            currency=currency,
            guest_nationality=guest_nationality,
            max_rates_per_hotel=max_rates_per_hotel,
            refundable_rates_only=refundable_rates_only,
            room_mapping=room_mapping
        )
        
        return _make_api_call(request_payload, top_k=k, sort_by=None)
    
    @mcp.tool(description=get_doc("get_hotel_rates_by_price", "hotel"))
    def get_hotel_rates_by_price(
        checkin: str,
        checkout: str,
        occupancies: List[Dict],
        k: int,
        hotel_ids: Optional[List[str]] = None,
        city_name: Optional[str] = None,
        country_code: Optional[str] = None,
        iata_code: Optional[str] = None,
        currency: Optional[str] = None,
        guest_nationality: Optional[str] = None,
        max_rates_per_hotel: Optional[int] = None,
        refundable_rates_only: Optional[bool] = None,
        room_mapping: Optional[bool] = None
    ) -> Dict:
        """Get hotel rates sorted by price (lowest first) and return top k results.
        
        At least one location identifier must be provided: hotelIds, (cityName and countryCode), or iataCode.
        """
        # Validate k parameter first
        if k <= 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid value for parameter 'k': {k}. The parameter 'k' must be a positive integer (e.g., 1, 5, 10).",
                "hotels": [],
                "suggestion": "Please provide a positive number for 'k' (e.g., k=5 to get top 5 cheapest hotels)."
            }
        
        if k > 200:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Parameter 'k' ({k}) is too large. Maximum allowed is 200 results.",
                "hotels": [],
                "suggestion": "Please reduce 'k' to 200 or less. For example, use k=10 to get top 10 results."
            }
        
        # Set defaults
        currency = currency or "USD"
        guest_nationality = guest_nationality or "US"
        
        # Convert string booleans to actual booleans (MCP may pass strings)
        if isinstance(refundable_rates_only, str):
            refundable_rates_only = refundable_rates_only.lower() in ("true", "1", "yes")
        if isinstance(room_mapping, str):
            room_mapping = room_mapping.lower() in ("true", "1", "yes")
        
        # Convert numeric parameters (might come as strings from JSON)
        try:
            if max_rates_per_hotel is not None:
                max_rates_per_hotel = int(max_rates_per_hotel) if not isinstance(max_rates_per_hotel, int) else max_rates_per_hotel
            else:
                max_rates_per_hotel = 1
        except (ValueError, TypeError):
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid max_rates_per_hotel value: {max_rates_per_hotel}. Must be an integer.",
                "hotels": [],
                "suggestion": "Please provide a valid integer for max_rates_per_hotel."
            }
        
        refundable_rates_only = refundable_rates_only if refundable_rates_only is not None else False
        room_mapping = room_mapping if room_mapping is not None else True
        
        # Validate inputs first
        is_valid, validation_error = _validate_hotel_inputs(
            checkin, checkout, occupancies, hotel_ids, city_name, country_code, iata_code
        )
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": validation_error,
                "hotels": [],
                "suggestion": "Please correct the input parameters and try again."
            }
        
        # Build API request payload
        request_payload = _build_request_payload(
            checkin=checkin,
            checkout=checkout,
            occupancies=occupancies,
            hotel_ids=hotel_ids,
            city_name=city_name,
            country_code=country_code,
            iata_code=iata_code,
            currency=currency,
            guest_nationality=guest_nationality,
            max_rates_per_hotel=max_rates_per_hotel,
            refundable_rates_only=refundable_rates_only,
            room_mapping=room_mapping
        )
        
        return _make_api_call(request_payload, top_k=k, sort_by="price")
    
    @mcp.tool(description=get_doc("get_hotel_details", "hotel"))
    def get_hotel_details(
        hotel_id: str,
        language: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict:
        """Get detailed information about a specific hotel by its ID.
        
        Args:
            hotel_id: Unique ID of the hotel (required)
            language: Optional language code (e.g., 'en', 'fr'). Default: None (uses API default)
            timeout: Optional request timeout in seconds. Default: 4.0
        """
        # Validate hotel_id
        if not hotel_id or not isinstance(hotel_id, str) or not hotel_id.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": "Hotel ID is required and must be a non-empty string.",
                "hotel": None,
                "suggestion": "Please provide a valid hotel ID."
            }
        
        # Set defaults
        timeout = timeout if timeout is not None else 4.0
        
        # Validate timeout
        if timeout <= 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid timeout value: {timeout}. Timeout must be a positive number.",
                "hotel": None,
                "suggestion": "Please provide a positive timeout value (e.g., 4.0)."
            }
        
        return _make_hotel_details_api_call(hotel_id.strip(), language, timeout)
    
    @mcp.tool(description=get_doc("get_list_of_hotels", "hotel"))
    def get_list_of_hotels(
        country_code: Optional[str] = None,
        city_name: Optional[str] = None,
        hotel_name: Optional[str] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        longitude: Optional[float] = None,
        latitude: Optional[float] = None,
        radius: Optional[int] = None,
        min_rating: Optional[float] = None,
        min_reviews_count: Optional[int] = None,
        star_rating: Optional[str] = None,
        hotel_ids: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict:
        """Search and list hotels based on various criteria.
        
        Use this tool to browse/search for hotels WITHOUT needing specific dates.
        This is perfect for general hotel browsing, finding hotels in a city, or searching by name.
        
        At least one search criterion should be provided (e.g., city_name, country_code, hotel_name, or hotel_ids).
        
        Args:
            country_code: Country code ISO-2 code (e.g., 'LB', 'US', 'FR')
            city_name: Name of the city (e.g., 'Beirut', 'Paris', 'New York')
            hotel_name: Name or partial name of hotel (case-insensitive, e.g., 'hilton')
            offset: Number of results to skip (for pagination). Default: 0
            limit: Maximum number of results to return. Default: 100, Max: 5000
            longitude: Longitude for geo-based search
            latitude: Latitude for geo-based search
            radius: Search radius in meters (minimum 1000m). Use with longitude/latitude.
            min_rating: Minimum hotel rating (e.g., 8.0, 8.5)
            min_reviews_count: Minimum number of reviews (e.g., 100)
            star_rating: Comma-separated star ratings (e.g., '4.0,5.0')
            hotel_ids: Comma-separated list of specific hotel IDs (e.g., 'lp1897,lp1343')
            timeout: Request timeout in seconds. Default: 10.0
            
        Returns:
            Dict with 'hotels' list containing hotel information, 'total' count, and error status
        """
        # Set defaults
        # Convert string parameters to integers (JSON might pass them as strings)
        try:
            offset = int(offset) if offset is not None else 0
        except (ValueError, TypeError):
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid offset value: {offset}. Must be an integer.",
                "hotels": [],
                "total": 0
            }
        
        try:
            limit = int(limit) if limit is not None else 100
        except (ValueError, TypeError):
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid limit value: {limit}. Must be an integer.",
                "hotels": [],
                "total": 0
            }
        
        # Convert other numeric parameters
        try:
            if radius is not None:
                radius = int(radius)
        except (ValueError, TypeError):
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid radius value: {radius}. Must be an integer.",
                "hotels": [],
                "total": 0
            }
        
        try:
            if min_rating is not None:
                min_rating = float(min_rating)
        except (ValueError, TypeError):
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid min_rating value: {min_rating}. Must be a number.",
                "hotels": [],
                "total": 0
            }
        
        try:
            if min_reviews_count is not None:
                min_reviews_count = int(min_reviews_count)
        except (ValueError, TypeError):
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid min_reviews_count value: {min_reviews_count}. Must be an integer.",
                "hotels": [],
                "total": 0
            }
        
        try:
            if longitude is not None:
                longitude = float(longitude)
            if latitude is not None:
                latitude = float(latitude)
        except (ValueError, TypeError):
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": "Invalid longitude/latitude values. Must be numbers.",
                "hotels": [],
                "total": 0
            }
        
        timeout = float(timeout) if timeout is not None else 10.0
        
        # Validate inputs
        if offset < 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid offset: {offset}. Offset must be 0 or greater.",
                "hotels": [],
                "total": 0
            }
        
        if limit <= 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid limit: {limit}. Limit must be greater than 0.",
                "hotels": [],
                "total": 0
            }
        
        if limit > 5000:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Limit too large: {limit}. Maximum allowed is 5000.",
                "hotels": [],
                "total": 0
            }
        
        if timeout <= 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid timeout: {timeout}. Timeout must be greater than 0.",
                "hotels": [],
                "total": 0
            }
        
        # Validate geo search parameters
        if (longitude is not None or latitude is not None or radius is not None):
            if longitude is None or latitude is None:
                return {
                    "error": True,
                    "error_code": "VALIDATION_ERROR",
                    "error_message": "For geo-based search, both longitude and latitude are required.",
                    "hotels": [],
                    "total": 0
                }
            
            if radius is not None and radius < 1000:
                return {
                    "error": True,
                    "error_code": "VALIDATION_ERROR",
                    "error_message": f"Invalid radius: {radius}. Minimum radius is 1000 meters.",
                    "hotels": [],
                    "total": 0
                }
        
        # Check if at least one search criterion is provided
        has_criteria = any([
            country_code, city_name, hotel_name, hotel_ids,
            (longitude is not None and latitude is not None)
        ])
        
        if not has_criteria:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": "At least one search criterion is required (country_code, city_name, hotel_name, hotel_ids, or geo coordinates).",
                "hotels": [],
                "total": 0,
                "suggestion": "Provide at least one search parameter like city_name='Beirut' or country_code='LB'"
            }
        
        return _make_hotels_list_api_call(
            country_code=country_code,
            city_name=city_name,
            hotel_name=hotel_name,
            offset=offset,
            limit=limit,
            longitude=longitude,
            latitude=latitude,
            radius=radius,
            min_rating=min_rating,
            min_reviews_count=min_reviews_count,
            star_rating=star_rating,
            hotel_ids=hotel_ids,
            timeout=timeout
        )

