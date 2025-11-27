"""TripAdvisor-related tools for the MCP server."""

import os
import httpx
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
from tools.doc_loader import get_doc
from tools.api_logger import log_api_call

# Load environment variables from .env file in main directory
# Get the project root directory (2 levels up from mcp_system/tools/)
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# API configuration
BASE_URL = "https://api.content.tripadvisor.com/api/v1"
API_KEY = os.getenv("TRIPADVISOR_KEY")

# Validate that required credentials are set
if not API_KEY:
    raise ValueError(
        "Missing required API credentials in .env file. "
        "Please set TRIPADVISOR_KEY"
    )

# Supported languages
SUPPORTED_LANGUAGES = [
    "en", "ar", "zh", "zh_TW", "da", "nl", "en_AU", "en_CA", "en_HK", "en_IN",
    "en_IE", "en_MY", "en_NZ", "en_PH", "en_SG", "en_ZA", "en_UK", "fr", "fr_BE",
    "fr_CA", "fr_CH", "de_AT", "de", "el", "iw", "in", "it", "it_CH", "ja", "ko",
    "no", "pt_PT", "pt", "ru", "es_AR", "es_CO", "es_MX", "es_PE", "es", "es_VE",
    "es_CL", "sv", "th", "tr", "vi"
]

# Supported categories
SUPPORTED_CATEGORIES = ["hotels", "attractions", "restaurants", "geos"]

# Supported radius units
SUPPORTED_RADIUS_UNITS = ["km", "mi", "m"]

# Supported photo sources
SUPPORTED_PHOTO_SOURCES = ["Expert", "Management", "Traveler"]


def _validate_language(language: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validate language parameter.
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if language is None:
        return True, None
    
    if language not in SUPPORTED_LANGUAGES:
        return False, f"Unsupported language: '{language}'. Supported languages: {', '.join(SUPPORTED_LANGUAGES[:10])}..."
    
    return True, None


def _validate_category(category: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validate category parameter.
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if category is None:
        return True, None
    
    if category not in SUPPORTED_CATEGORIES:
        return False, f"Unsupported category: '{category}'. Supported categories: {', '.join(SUPPORTED_CATEGORIES)}."
    
    return True, None


def _validate_radius_unit(radius_unit: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validate radius unit parameter.
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if radius_unit is None:
        return True, None
    
    if radius_unit not in SUPPORTED_RADIUS_UNITS:
        return False, f"Unsupported radius unit: '{radius_unit}'. Supported units: {', '.join(SUPPORTED_RADIUS_UNITS)}."
    
    return True, None


def _validate_lat_long(lat_long: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validate latitude/longitude format.
    
    Expected format: "lat,lon" (e.g., "40.7128,-74.0060")
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if lat_long is None:
        return True, None
    
    try:
        parts = lat_long.split(",")
        if len(parts) != 2:
            return False, f"Invalid latLong format: '{lat_long}'. Expected format: 'lat,lon' (e.g., '40.7128,-74.0060')."
        
        lat = float(parts[0].strip())
        lon = float(parts[1].strip())
        
        if not (-90 <= lat <= 90):
            return False, f"Invalid latitude: {lat}. Latitude must be between -90 and 90."
        
        if not (-180 <= lon <= 180):
            return False, f"Invalid longitude: {lon}. Longitude must be between -180 and 180."
        
        return True, None
    except ValueError:
        return False, f"Invalid latLong format: '{lat_long}'. Expected format: 'lat,lon' with numeric values (e.g., '40.7128,-74.0060')."


def _validate_location_id(location_id: Optional[int]) -> Tuple[bool, Optional[str]]:
    """Validate location ID parameter.
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if location_id is None:
        return False, "Location ID is required and must be a positive integer."
    
    # Try to convert string to int if needed
    if isinstance(location_id, str):
        try:
            location_id = int(location_id)
        except ValueError:
            return False, f"Invalid location ID: {location_id}. Location ID must be a positive integer."
    
    if not isinstance(location_id, int) or location_id <= 0:
        return False, f"Invalid location ID: {location_id}. Location ID must be a positive integer."
    
    return True, None


def _validate_limit(limit: Optional[int], max_limit: int = 10) -> Tuple[bool, Optional[str]]:
    """Validate limit parameter.
    
    Args:
        limit: The limit value to validate
        max_limit: Maximum allowed limit (default: 10)
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if limit is None:
        return True, None
    
    if not isinstance(limit, int) or limit <= 0:
        return False, f"Invalid limit: {limit}. Limit must be a positive integer."
    
    if limit > max_limit:
        return False, f"Limit ({limit}) exceeds maximum allowed ({max_limit}). Please reduce the limit."
    
    return True, None


def _validate_offset(offset: Optional[int]) -> Tuple[bool, Optional[str]]:
    """Validate offset parameter.
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if offset is None:
        return True, None
    
    if not isinstance(offset, int) or offset < 0:
        return False, f"Invalid offset: {offset}. Offset must be a non-negative integer."
    
    return True, None


def _validate_radius(radius: Optional[float]) -> Tuple[bool, Optional[str]]:
    """Validate radius parameter.
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if radius is None:
        return True, None
    
    if not isinstance(radius, (int, float)) or radius <= 0:
        return False, f"Invalid radius: {radius}. Radius must be a positive number."
    
    return True, None


def _extract_location_rating(location: Dict) -> float:
    """Extract rating from a location object.
    
    Args:
        location: Location object from API response
        
    Returns:
        Rating as float, or 0.0 if rating not found
    """
    try:
        # Try multiple possible field names for rating
        rating = (location.get("rating") or 
                 location.get("ratingValue") or 
                 location.get("averageRating") or 
                 location.get("rating_average") or
                 0.0)
        
        if isinstance(rating, (int, float)):
            return float(rating)
        elif isinstance(rating, str):
            try:
                return float(rating)
            except ValueError:
                return 0.0
        return 0.0
    except (KeyError, TypeError, AttributeError):
        return 0.0  # Return 0 for locations without ratings (sorts them last)


def _sort_locations_by_rating(locations: List[Dict], reverse: bool = True) -> List[Dict]:
    """Sort locations by rating.
    
    Args:
        locations: List of location objects
        reverse: If True, sort descending (highest first). If False, ascending (lowest first)
        
    Returns:
        Sorted list of locations
    """
    try:
        return sorted(locations, key=_extract_location_rating, reverse=reverse)
    except Exception:
        return locations  # Return unsorted if sorting fails


def _filter_locations_by_rating(locations: List[Dict], min_rating: float) -> List[Dict]:
    """Filter locations by minimum rating.
    
    Args:
        locations: List of location objects
        min_rating: Minimum rating threshold (e.g., 4.0 for 4+ stars)
        
    Returns:
        Filtered list of locations with rating >= min_rating
    """
    try:
        filtered = []
        for location in locations:
            rating = _extract_location_rating(location)
            if rating >= min_rating:
                filtered.append(location)
        return filtered
    except Exception:
        return locations  # Return all if filtering fails


def _filter_locations_by_price_level(locations: List[Dict], max_price_level: Optional[int] = None) -> List[Dict]:
    """Filter locations by price level.
    
    Args:
        locations: List of location objects
        max_price_level: Maximum price level (1-4, where 1=cheapest, 4=most expensive)
        
    Returns:
        Filtered list of locations
    """
    if max_price_level is None:
        return locations
    
    try:
        filtered = []
        for location in locations:
            price_level = location.get("priceLevel") or location.get("price_level")
            if price_level is None:
                # Include locations without price level
                filtered.append(location)
            elif isinstance(price_level, (int, float)):
                if float(price_level) <= max_price_level:
                    filtered.append(location)
        return filtered
    except Exception:
        return locations


def _extract_location_distance(location: Dict) -> float:
    """Extract distance from a location object.
    
    Args:
        location: Location object from API response
        
    Returns:
        Distance as float, or infinity if distance not found
    """
    try:
        # Try multiple possible field names for distance
        distance = (location.get("distance") or 
                   location.get("distanceValue") or 
                   location.get("distance_km") or
                   float('inf'))
        
        if isinstance(distance, (int, float)):
            return float(distance)
        elif isinstance(distance, str):
            try:
                return float(distance)
            except ValueError:
                return float('inf')
        return float('inf')
    except (KeyError, TypeError, AttributeError):
        return float('inf')  # Return infinity for locations without distance (sorts them last)


def _sort_locations_by_distance(locations: List[Dict], reverse: bool = False) -> List[Dict]:
    """Sort locations by distance.
    
    Args:
        locations: List of location objects
        reverse: If True, sort descending (farthest first). If False, ascending (closest first)
        
    Returns:
        Sorted list of locations
    """
    try:
        return sorted(locations, key=_extract_location_distance, reverse=reverse)
    except Exception:
        return locations  # Return unsorted if sorting fails


def _filter_locations_by_cuisine(locations: List[Dict], cuisine_types: List[str]) -> List[Dict]:
    """Filter locations by cuisine type.
    
    Args:
        locations: List of location objects
        cuisine_types: List of cuisine type strings to match (case-insensitive)
        
    Returns:
        Filtered list of locations matching any of the cuisine types
    """
    if not cuisine_types:
        return locations
    
    try:
        filtered = []
        cuisine_lower = [c.lower() for c in cuisine_types]
        
        for location in locations:
            # Get cuisine from location (could be in details or direct)
            cuisine = location.get("cuisine") or location.get("cuisineType")
            
            if cuisine is None:
                continue
            
            # Handle different cuisine formats
            location_cuisines = []
            if isinstance(cuisine, list):
                for item in cuisine:
                    if isinstance(item, str):
                        location_cuisines.append(item.lower())
                    elif isinstance(item, dict):
                        name = item.get("name") or item.get("value") or str(item)
                        location_cuisines.append(name.lower())
            elif isinstance(cuisine, str):
                location_cuisines.append(cuisine.lower())
            
            # Check if any cuisine matches
            if any(c in location_cuisines for c in cuisine_lower):
                filtered.append(location)
        
        return filtered
    except Exception:
        return locations  # Return all if filtering fails


def _make_api_call(
    method: str,
    endpoint: str,
    params: Dict,
    timeout: float = 10.0,
    is_single_object: bool = False
) -> Dict:
    """Helper function to make API calls with error handling.
    
    Args:
        method: HTTP method ("GET" or "POST")
        endpoint: API endpoint path
        params: Query parameters
        timeout: Request timeout in seconds (default: 10.0)
        
    Returns:
        Dict with error status and results
    """
    try:
        # Add API key to params
        params["key"] = API_KEY
        
        # Make API request with timeout
        # Use a timeout object that allows for longer read times
        timeout_config = httpx.Timeout(timeout, connect=10.0, read=timeout, write=10.0, pool=10.0)
        start_time = time.time()
        with httpx.Client(timeout=timeout_config) as client:
            if method.upper() == "GET":
                response = client.get(f"{BASE_URL}{endpoint}", params=params)
            else:
                response = client.post(f"{BASE_URL}{endpoint}", json=params)
            response_time_ms = (time.time() - start_time) * 1000
            
            # Log API call
            success = response.status_code == 200
            error_msg = None
            if response.status_code == 200:
                try:
                    api_response = response.json()
                    if "errors" in api_response or "error" in api_response:
                        error_info = api_response.get("errors") or api_response.get("error", {})
                        if isinstance(error_info, list) and len(error_info) > 0:
                            error_msg = error_info[0].get("message", "Unknown error")
                        elif isinstance(error_info, dict):
                            error_msg = error_info.get("message", "Unknown error")
                        else:
                            error_msg = str(error_info) if error_info else "Unknown error"
                        success = False
                except:
                    pass
            
            log_api_call(
                service="activities",
                endpoint=endpoint,
                method=method.upper(),
                request_payload=params if method.upper() == "POST" else params,
                response_status=response.status_code,
                response_time_ms=response_time_ms,
                success=success,
                error_message=error_msg
            )
            
            # Handle 400 Bad Request
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    error_message = error_data.get("message", "Bad request: Invalid parameters.")
                    if isinstance(error_message, dict):
                        error_message = str(error_message)
                except Exception:
                    error_message = "Bad request: Invalid parameters sent to TripAdvisor API."
                
                default_data = {} if is_single_object else []
                return {
                    "error": True,
                    "error_code": "BAD_REQUEST",
                    "error_message": "Invalid search parameters provided. Please check your input data.",
                    "data": default_data,
                    "suggestion": "Please verify your search parameters and try again."
                }
            
            # Handle 401 Unauthorized
            if response.status_code == 401:
                default_data = {} if is_single_object else []
                return {
                    "error": True,
                    "error_code": "UNAUTHORIZED",
                    "error_message": "Authentication failed. Please check your API credentials.",
                    "data": default_data,
                    "suggestion": "Please verify your API key is correct."
                }
            
            # Handle 403 Forbidden
            if response.status_code == 403:
                default_data = {} if is_single_object else []
                return {
                    "error": True,
                    "error_code": "FORBIDDEN",
                    "error_message": "Access denied. Please check your API permissions.",
                    "data": default_data,
                    "suggestion": "Please verify your API key has the required permissions."
                }
            
            # Handle 404 Not Found
            if response.status_code == 404:
                default_data = {} if is_single_object else []
                return {
                    "error": True,
                    "error_code": "NOT_FOUND",
                    "error_message": "Resource not found. The requested location or endpoint may not exist.",
                    "data": default_data,
                    "suggestion": "Please verify the location ID or search query and try again."
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
                
                default_data = {} if is_single_object else []
                return {
                    "error": True,
                    "error_code": "API_ERROR",
                    "error_message": "The TripAdvisor service encountered an error. Please try again with different parameters.",
                    "data": default_data,
                    "suggestion": "Please try again with different search parameters. If the problem persists, contact support."
                }
            
            # Process successful response
            response_data = api_response.get("data", api_response)
            return {
                "error": False,
                "data": response_data
            }
            
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        if status_code == 400:
            error_msg = "Invalid search parameters. Please check your input data and try again."
        elif status_code == 401:
            error_msg = "Authentication failed. Please check your API credentials."
        elif status_code == 403:
            error_msg = "Access denied. Please check your API permissions."
        elif status_code == 404:
            error_msg = "Resource not found. Please verify your search parameters."
        elif status_code == 429:
            error_msg = "Too many requests. Please wait a moment and try again."
        elif status_code == 500:
            error_msg = "Internal server error. Please try again later."
        elif status_code == 503:
            error_msg = "Service temporarily unavailable. Please try again later."
        else:
            error_msg = "The TripAdvisor service returned an error. Please try again."
        
        default_data = {} if is_single_object else []
        return {
            "error": True,
            "error_code": "HTTP_ERROR",
            "error_message": error_msg,
            "data": default_data,
            "suggestion": "Please verify your search parameters and try again. If the problem persists, contact support."
        }
    except httpx.TimeoutException as e:
        default_data = {} if is_single_object else []
        return {
            "error": True,
            "error_code": "TIMEOUT",
            "error_message": f"Request timeout: The TripAdvisor API took too long to respond (over {timeout} seconds).",
            "data": default_data,
            "suggestion": "The TripAdvisor service may be experiencing high load. Please try again in a few moments."
        }
    except httpx.RequestError as e:
        default_data = {} if is_single_object else []
        return {
            "error": True,
            "error_code": "NETWORK_ERROR",
            "error_message": f"Network error: Unable to connect to TripAdvisor service. {str(e)}",
            "data": default_data,
            "suggestion": "Please check your internet connection and try again. If the problem persists, the service may be temporarily unavailable."
        }
    except Exception as e:
        # Catch any other exceptions including httpcore exceptions
        error_type = type(e).__name__
        default_data = {} if is_single_object else []
        
        # Check if it's a timeout-related exception
        if "timeout" in error_type.lower() or "Timeout" in error_type:
            return {
                "error": True,
                "error_code": "TIMEOUT",
                "error_message": f"Request timeout: The TripAdvisor API took too long to respond (over {timeout} seconds).",
                "data": default_data,
                "suggestion": "The TripAdvisor service may be experiencing high load. Please try again in a few moments."
            }
        
        return {
            "error": True,
            "error_code": "UNEXPECTED_ERROR",
            "error_message": f"An unexpected error occurred during the TripAdvisor API call: {error_type}. Please try again.",
            "data": default_data,
            "suggestion": "An unexpected error occurred. Please try again or contact support if the problem persists."
        }


def register_tripadvisor_tools(mcp):
    """Register all TripAdvisor-related tools with the MCP server."""
    
    @mcp.tool(description=get_doc("search_locations", "tripadvisor"))
    def search_locations(
        search_query: str,
        category: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        location: Optional[str] = None,
        lat_long: Optional[str] = None,
        radius: Optional[float] = None,
        radius_unit: Optional[str] = None,
        language: Optional[str] = None
    ) -> Dict:
        """Search for locations on TripAdvisor. Returns up to 10 locations based on a text query.
        
        Args:
            search_query: Text to search for (required)
            category: Filter by category: hotels | attractions | restaurants | geos
            phone: Phone number (no "+")
            address: Address text
            location: Location/city name (alias for address, used if address not provided)
            lat_long: Latitude and longitude in format "lat,lon" (e.g., "40.7128,-74.0060")
            radius: Search radius
            radius_unit: Unit for radius: km | mi | m
            language: Response language (default: "en")
        """
        # Validate search_query
        if not search_query or not isinstance(search_query, str) or not search_query.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": "Search query is required and must be a non-empty string.",
                "data": [],
                "suggestion": "Please provide a search query."
            }
        
        # Use location as address if address is not provided
        if not address and location:
            address = location
        
        # Validate parameters
        is_valid, error_msg = _validate_category(category)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported category or omit the category parameter."
            }
        
        is_valid, error_msg = _validate_language(language)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported language code or omit to use default (en)."
            }
        
        is_valid, error_msg = _validate_lat_long(lat_long)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use the format 'lat,lon' (e.g., '40.7128,-74.0060')."
            }
        
        is_valid, error_msg = _validate_radius(radius)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please provide a positive number for radius."
            }
        
        is_valid, error_msg = _validate_radius_unit(radius_unit)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported radius unit: km, mi, or m."
            }
        
        # Build query parameters
        params = {
            "searchQuery": search_query.strip()
        }
        
        if category:
            params["category"] = category
        if phone:
            params["phone"] = phone
        if address:
            params["address"] = address
        if lat_long:
            params["latLong"] = lat_long
        if radius is not None:
            params["radius"] = str(radius)
        if radius_unit:
            params["radiusUnit"] = radius_unit
        if language:
            params["language"] = language
        
        return _make_api_call("GET", "/location/search", params)
    
    @mcp.tool(description=get_doc("get_location_reviews", "tripadvisor"))
    def get_location_reviews(
        location_id: int,
        language: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> Dict:
        """Get reviews for a specific location. Returns up to 5 recent reviews.
        
        Args:
            location_id: TripAdvisor location ID (required)
            language: Response language (default: "en")
            limit: Number of reviews to return (max 5, default: 5)
            offset: Index of first review (default: 0)
        """
        # Convert location_id to int if it's a string
        if isinstance(location_id, str):
            try:
                location_id = int(location_id)
            except ValueError:
                return {
                    "error": True,
                    "error_code": "VALIDATION_ERROR",
                    "error_message": f"Invalid location ID: {location_id}. Location ID must be a positive integer.",
                    "data": [],
                    "suggestion": "Please provide a valid positive integer location ID."
                }
        
        # Validate location_id
        is_valid, error_msg = _validate_location_id(location_id)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please provide a valid positive integer location ID."
            }
        
        # Validate language
        is_valid, error_msg = _validate_language(language)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported language code or omit to use default (en)."
            }
        
        # Validate limit (max 5 for reviews)
        is_valid, error_msg = _validate_limit(limit, max_limit=5)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please provide a limit between 1 and 5."
            }
        
        # Validate offset
        is_valid, error_msg = _validate_offset(offset)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please provide a non-negative integer for offset."
            }
        
        # Build query parameters
        params = {}
        if language:
            params["language"] = language
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        
        # Use longer timeout for reviews as they can take longer
        return _make_api_call("GET", f"/location/{location_id}/reviews", params, timeout=15.0)
    
    @mcp.tool(description=get_doc("get_location_photos", "tripadvisor"))
    def get_location_photos(
        location_id: int,
        language: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        source: Optional[str] = None
    ) -> Dict:
        """Get photos for a specific location. Returns up to 5 high-quality photos ordered by recency.
        
        Args:
            location_id: TripAdvisor location ID (required)
            language: Response language (default: "en")
            limit: Number of photos to return (max 5, default: 5)
            offset: Index of first photo (default: 0)
            source: Photo source filter: "Expert", "Management", "Traveler" (comma-separated)
        """
        # Convert location_id to int if it's a string
        if isinstance(location_id, str):
            try:
                location_id = int(location_id)
            except ValueError:
                return {
                    "error": True,
                    "error_code": "VALIDATION_ERROR",
                    "error_message": f"Invalid location ID: {location_id}. Location ID must be a positive integer.",
                    "data": [],
                    "suggestion": "Please provide a valid positive integer location ID."
                }
        
        # Validate location_id
        is_valid, error_msg = _validate_location_id(location_id)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please provide a valid positive integer location ID."
            }
        
        # Validate language
        is_valid, error_msg = _validate_language(language)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported language code or omit to use default (en)."
            }
        
        # Validate limit (max 5 for photos)
        is_valid, error_msg = _validate_limit(limit, max_limit=5)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please provide a limit between 1 and 5."
            }
        
        # Validate offset
        is_valid, error_msg = _validate_offset(offset)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please provide a non-negative integer for offset."
            }
        
        # Validate source if provided
        if source:
            sources = [s.strip() for s in source.split(",")]
            invalid_sources = [s for s in sources if s not in SUPPORTED_PHOTO_SOURCES]
            if invalid_sources:
                return {
                    "error": True,
                    "error_code": "VALIDATION_ERROR",
                    "error_message": f"Invalid photo sources: {', '.join(invalid_sources)}. Supported sources: {', '.join(SUPPORTED_PHOTO_SOURCES)}.",
                    "data": [],
                    "suggestion": "Please use comma-separated values from: Expert, Management, Traveler."
                }
        
        # Build query parameters
        params = {}
        if language:
            params["language"] = language
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if source:
            params["source"] = source
        
        return _make_api_call("GET", f"/location/{location_id}/photos", params)
    
    @mcp.tool(description=get_doc("get_location_details", "tripadvisor"))
    def get_location_details(
        location_id: int,
        language: Optional[str] = None,
        currency: Optional[str] = None
    ) -> Dict:
        """Get full details about a location: name, address, category, rating, ranking, coordinates, contact info, TripAdvisor URLs, amenities, cuisine, features, pricing.
        
        Args:
            location_id: TripAdvisor location ID (required)
            language: Response language (default: "en")
            currency: ISO 4217 currency code (default: "USD")
        """
        # Convert location_id to int if it's a string
        if isinstance(location_id, str):
            try:
                location_id = int(location_id)
            except ValueError:
                return {
                    "error": True,
                    "error_code": "VALIDATION_ERROR",
                    "error_message": f"Invalid location ID: {location_id}. Location ID must be a positive integer.",
                    "data": {},
                    "suggestion": "Please provide a valid positive integer location ID."
                }
        
        # Validate location_id
        is_valid, error_msg = _validate_location_id(location_id)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": {},
                "suggestion": "Please provide a valid positive integer location ID."
            }
        
        # Validate language
        is_valid, error_msg = _validate_language(language)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported language code or omit to use default (en)."
            }
        
        # Build query parameters
        params = {}
        if language:
            params["language"] = language
        if currency:
            params["currency"] = currency
        
        # Use longer timeout for details as they can take longer
        return _make_api_call("GET", f"/location/{location_id}/details", params, timeout=15.0, is_single_object=True)
    
    @mcp.tool(description=get_doc("search_nearby", "tripadvisor"))
    def search_nearby(
        lat_long: str,
        category: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        radius: Optional[float] = None,
        radius_unit: Optional[str] = None,
        language: Optional[str] = None
    ) -> Dict:
        """Search for locations near a given latitude/longitude. Returns up to 10 locations.
        
        Args:
            lat_long: Latitude and longitude in format "lat,lon" (required, e.g., "40.7128,-74.0060")
            category: Filter by category: hotels | attractions | restaurants | geos
            phone: Phone number (no "+")
            address: Address text
            radius: Search radius
            radius_unit: Unit for radius: km | mi | m
            language: Response language (default: "en")
        """
        # Validate lat_long (required)
        is_valid, error_msg = _validate_lat_long(lat_long)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please provide lat_long in format 'lat,lon' (e.g., '40.7128,-74.0060')."
            }
        
        # Validate category
        is_valid, error_msg = _validate_category(category)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported category or omit the category parameter."
            }
        
        # Validate language
        is_valid, error_msg = _validate_language(language)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported language code or omit to use default (en)."
            }
        
        # Validate radius
        is_valid, error_msg = _validate_radius(radius)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please provide a positive number for radius."
            }
        
        # Validate radius_unit
        is_valid, error_msg = _validate_radius_unit(radius_unit)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported radius unit: km, mi, or m."
            }
        
        # Build query parameters
        params = {
            "latLong": lat_long
        }
        
        if category:
            params["category"] = category
        if phone:
            params["phone"] = phone
        if address:
            params["address"] = address
        if radius is not None:
            params["radius"] = str(radius)
        if radius_unit:
            params["radiusUnit"] = radius_unit
        if language:
            params["language"] = language
        
        return _make_api_call("GET", "/location/nearby_search", params)
    
    @mcp.tool(description=get_doc("search_locations_by_rating", "tripadvisor"))
    def search_locations_by_rating(
        search_query: str,
        min_rating: Optional[float] = None,
        sort_by_rating: bool = True,
        top_k: Optional[int] = None,
        category: Optional[str] = None,
        language: Optional[str] = None
    ) -> Dict:
        """Search for locations and return them sorted by rating (highest first). Optionally filter by minimum rating.
        
        Args:
            search_query: Text to search for (required)
            min_rating: Minimum rating threshold (e.g., 4.0 for 4+ stars). Locations below this will be filtered out.
            sort_by_rating: If True, sort by rating descending (highest first). If False, return unsorted.
            top_k: Number of top-rated locations to return (default: all results)
            category: Filter by category: hotels | attractions | restaurants | geos
            language: Response language (default: "en")
        """
        # Validate search_query
        if not search_query or not isinstance(search_query, str) or not search_query.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": "Search query is required and must be a non-empty string.",
                "data": [],
                "suggestion": "Please provide a search query."
            }
        
        # Validate min_rating
        if min_rating is not None:
            if not isinstance(min_rating, (int, float)) or min_rating < 0 or min_rating > 5:
                return {
                    "error": True,
                    "error_code": "VALIDATION_ERROR",
                    "error_message": f"Invalid min_rating: {min_rating}. Rating must be between 0 and 5.",
                    "data": [],
                    "suggestion": "Please provide a rating between 0 and 5 (e.g., 4.0 for 4+ stars)."
                }
        
        # Validate top_k
        if top_k is not None:
            if not isinstance(top_k, int) or top_k <= 0:
                return {
                    "error": True,
                    "error_code": "VALIDATION_ERROR",
                    "error_message": f"Invalid top_k: {top_k}. Must be a positive integer.",
                    "data": [],
                    "suggestion": "Please provide a positive integer for top_k (e.g., 5 for top 5)."
                }
            if top_k > 10:
                return {
                    "error": True,
                    "error_code": "VALIDATION_ERROR",
                    "error_message": f"Invalid top_k: {top_k}. Maximum is 10 (API limit).",
                    "data": [],
                    "suggestion": "Please provide top_k between 1 and 10."
                }
        
        # Validate category
        is_valid, error_msg = _validate_category(category)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported category or omit the category parameter."
            }
        
        # Validate language
        is_valid, error_msg = _validate_language(language)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported language code or omit to use default (en)."
            }
        
        # Build query parameters
        params = {
            "searchQuery": search_query.strip()
        }
        
        if category:
            params["category"] = category
        if language:
            params["language"] = language
        
        # Make API call
        result = _make_api_call("GET", "/location/search", params)
        
        if result.get("error"):
            return result
        
        # Process and sort results
        locations = result.get("data", [])
        if not locations:
            return result
        
        # Filter by minimum rating if specified
        if min_rating is not None:
            locations = _filter_locations_by_rating(locations, min_rating)
        
        # Sort by rating if requested
        if sort_by_rating:
            locations = _sort_locations_by_rating(locations, reverse=True)
        
        # Limit to top_k if specified
        if top_k is not None:
            locations = locations[:top_k]
        
        return {
            "error": False,
            "data": locations,
            "search_params": {
                "query": search_query,
                "min_rating": min_rating,
                "sort_by_rating": sort_by_rating,
                "top_k": top_k
            }
        }
    
    @mcp.tool(description=get_doc("search_nearby_by_rating", "tripadvisor"))
    def search_nearby_by_rating(
        lat_long: str,
        min_rating: Optional[float] = None,
        sort_by_rating: bool = True,
        top_k: Optional[int] = None,
        category: Optional[str] = None,
        radius: Optional[float] = None,
        radius_unit: Optional[str] = None,
        language: Optional[str] = None
    ) -> Dict:
        """Search for locations near coordinates and return them sorted by rating (highest first). Optionally filter by minimum rating.
        
        Args:
            lat_long: Latitude and longitude in format "lat,lon" (required, e.g., "40.7128,-74.0060")
            min_rating: Minimum rating threshold (e.g., 4.0 for 4+ stars). Locations below this will be filtered out.
            sort_by_rating: If True, sort by rating descending (highest first). If False, return unsorted.
            top_k: Number of top-rated locations to return (default: all results, max 10)
            category: Filter by category: hotels | attractions | restaurants | geos
            radius: Search radius
            radius_unit: Unit for radius: km | mi | m
            language: Response language (default: "en")
        """
        # Validate lat_long (required)
        is_valid, error_msg = _validate_lat_long(lat_long)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please provide lat_long in format 'lat,lon' (e.g., '40.7128,-74.0060')."
            }
        
        # Validate min_rating
        if min_rating is not None:
            if not isinstance(min_rating, (int, float)) or min_rating < 0 or min_rating > 5:
                return {
                    "error": True,
                    "error_code": "VALIDATION_ERROR",
                    "error_message": f"Invalid min_rating: {min_rating}. Rating must be between 0 and 5.",
                    "data": [],
                    "suggestion": "Please provide a rating between 0 and 5 (e.g., 4.0 for 4+ stars)."
                }
        
        # Validate top_k
        if top_k is not None:
            if not isinstance(top_k, int) or top_k <= 0:
                return {
                    "error": True,
                    "error_code": "VALIDATION_ERROR",
                    "error_message": f"Invalid top_k: {top_k}. Must be a positive integer.",
                    "data": [],
                    "suggestion": "Please provide a positive integer for top_k (e.g., 5 for top 5)."
                }
            if top_k > 10:
                return {
                    "error": True,
                    "error_code": "VALIDATION_ERROR",
                    "error_message": f"Invalid top_k: {top_k}. Maximum is 10 (API limit).",
                    "data": [],
                    "suggestion": "Please provide top_k between 1 and 10."
                }
        
        # Validate other parameters
        is_valid, error_msg = _validate_category(category)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported category or omit the category parameter."
            }
        
        is_valid, error_msg = _validate_language(language)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported language code or omit to use default (en)."
            }
        
        is_valid, error_msg = _validate_radius(radius)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please provide a positive number for radius."
            }
        
        is_valid, error_msg = _validate_radius_unit(radius_unit)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported radius unit: km, mi, or m."
            }
        
        # Build query parameters
        params = {
            "latLong": lat_long
        }
        
        if category:
            params["category"] = category
        if radius is not None:
            params["radius"] = str(radius)
        if radius_unit:
            params["radiusUnit"] = radius_unit
        if language:
            params["language"] = language
        
        # Make API call
        result = _make_api_call("GET", "/location/nearby_search", params)
        
        if result.get("error"):
            return result
        
        # Process and sort results
        locations = result.get("data", [])
        if not locations:
            return result
        
        # Filter by minimum rating if specified
        if min_rating is not None:
            locations = _filter_locations_by_rating(locations, min_rating)
        
        # Sort by rating if requested
        if sort_by_rating:
            locations = _sort_locations_by_rating(locations, reverse=True)
        
        # Limit to top_k if specified
        if top_k is not None:
            locations = locations[:top_k]
        
        return {
            "error": False,
            "data": locations,
            "search_params": {
                "lat_long": lat_long,
                "min_rating": min_rating,
                "sort_by_rating": sort_by_rating,
                "top_k": top_k
            }
        }
    
    @mcp.tool(description=get_doc("get_top_rated_locations", "tripadvisor"))
    def get_top_rated_locations(
        search_query: str,
        k: int,
        category: Optional[str] = None,
        min_rating: Optional[float] = None,
        language: Optional[str] = None
    ) -> Dict:
        """Get the top k highest-rated locations matching a search query. Perfect for finding the best-rated places.
        
        Args:
            search_query: Text to search for (required)
            k: Number of top-rated locations to return (required, 1-10)
            category: Filter by category: hotels | attractions | restaurants | geos
            min_rating: Minimum rating threshold (e.g., 4.0 for 4+ stars only)
            language: Response language (default: "en")
        """
        # Validate search_query
        if not search_query or not isinstance(search_query, str) or not search_query.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": "Search query is required and must be a non-empty string.",
                "data": [],
                "suggestion": "Please provide a search query."
            }
        
        # Validate k
        if not isinstance(k, int) or k <= 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid k: {k}. Must be a positive integer.",
                "data": [],
                "suggestion": "Please provide a positive integer for k (e.g., 5 for top 5)."
            }
        
        if k > 10:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid k: {k}. Maximum is 10 (API limit).",
                "data": [],
                "suggestion": "Please provide k between 1 and 10."
            }
        
        # Validate min_rating
        if min_rating is not None:
            if not isinstance(min_rating, (int, float)) or min_rating < 0 or min_rating > 5:
                return {
                    "error": True,
                    "error_code": "VALIDATION_ERROR",
                    "error_message": f"Invalid min_rating: {min_rating}. Rating must be between 0 and 5.",
                    "data": [],
                    "suggestion": "Please provide a rating between 0 and 5 (e.g., 4.0 for 4+ stars)."
                }
        
        # Validate category
        is_valid, error_msg = _validate_category(category)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported category or omit the category parameter."
            }
        
        # Validate language
        is_valid, error_msg = _validate_language(language)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported language code or omit to use default (en)."
            }
        
        # Build query parameters
        params = {
            "searchQuery": search_query.strip()
        }
        
        if category:
            params["category"] = category
        if language:
            params["language"] = language
        
        # Make API call
        result = _make_api_call("GET", "/location/search", params)
        
        if result.get("error"):
            return result
        
        # Process and sort results
        locations = result.get("data", [])
        if not locations:
            return result
        
        # Filter by minimum rating if specified
        if min_rating is not None:
            locations = _filter_locations_by_rating(locations, min_rating)
        
        # Sort by rating (highest first)
        locations = _sort_locations_by_rating(locations, reverse=True)
        
        # Return top k
        locations = locations[:k]
        
        return {
            "error": False,
            "data": locations,
            "search_params": {
                "query": search_query,
                "k": k,
                "min_rating": min_rating,
                "sorted_by": "rating_descending"
            }
        }
    
    @mcp.tool(description=get_doc("search_locations_by_price", "tripadvisor"))
    def search_locations_by_price(
        search_query: str,
        max_price_level: int,
        category: Optional[str] = None,
        language: Optional[str] = None
    ) -> Dict:
        """Search for locations and filter by maximum price level. Perfect for budget-conscious users.
        
        Args:
            search_query: Text to search for (required)
            max_price_level: Maximum price level (1-4, where 1=cheapest, 4=most expensive) (required)
            category: Filter by category: hotels | attractions | restaurants | geos
            language: Response language (default: "en")
        """
        # Validate search_query
        if not search_query or not isinstance(search_query, str) or not search_query.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": "Search query is required and must be a non-empty string.",
                "data": [],
                "suggestion": "Please provide a search query."
            }
        
        # Validate max_price_level
        if not isinstance(max_price_level, int) or max_price_level < 1 or max_price_level > 4:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid max_price_level: {max_price_level}. Price level must be between 1 and 4 (1=cheapest, 4=most expensive).",
                "data": [],
                "suggestion": "Please provide a price level between 1 and 4."
            }
        
        # Validate category
        is_valid, error_msg = _validate_category(category)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported category or omit the category parameter."
            }
        
        # Validate language
        is_valid, error_msg = _validate_language(language)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported language code or omit to use default (en)."
            }
        
        # Build query parameters
        params = {
            "searchQuery": search_query.strip()
        }
        
        if category:
            params["category"] = category
        if language:
            params["language"] = language
        
        # Make API call
        result = _make_api_call("GET", "/location/search", params)
        
        if result.get("error"):
            return result
        
        # Get locations and filter by price
        locations = result.get("data", [])
        if not locations:
            return result
        
        # Filter by price level
        locations = _filter_locations_by_price_level(locations, max_price_level)
        
        return {
            "error": False,
            "data": locations,
            "search_params": {
                "query": search_query,
                "max_price_level": max_price_level
            }
        }
    
    @mcp.tool(description=get_doc("search_nearby_by_price", "tripadvisor"))
    def search_nearby_by_price(
        lat_long: str,
        max_price_level: int,
        category: Optional[str] = None,
        radius: Optional[float] = None,
        radius_unit: Optional[str] = None,
        language: Optional[str] = None
    ) -> Dict:
        """Search for locations near coordinates and filter by maximum price level. Perfect for finding budget-friendly places nearby.
        
        Args:
            lat_long: Latitude and longitude in format "lat,lon" (required, e.g., "40.7128,-74.0060")
            max_price_level: Maximum price level (1-4, where 1=cheapest, 4=most expensive) (required)
            category: Filter by category: hotels | attractions | restaurants | geos
            radius: Search radius
            radius_unit: Unit for radius: km | mi | m
            language: Response language (default: "en")
        """
        # Validate lat_long
        is_valid, error_msg = _validate_lat_long(lat_long)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please provide lat_long in format 'lat,lon' (e.g., '40.7128,-74.0060')."
            }
        
        # Validate max_price_level
        if not isinstance(max_price_level, int) or max_price_level < 1 or max_price_level > 4:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid max_price_level: {max_price_level}. Price level must be between 1 and 4 (1=cheapest, 4=most expensive).",
                "data": [],
                "suggestion": "Please provide a price level between 1 and 4."
            }
        
        # Validate other parameters
        is_valid, error_msg = _validate_category(category)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported category or omit the category parameter."
            }
        
        is_valid, error_msg = _validate_language(language)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported language code or omit to use default (en)."
            }
        
        is_valid, error_msg = _validate_radius(radius)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please provide a positive number for radius."
            }
        
        is_valid, error_msg = _validate_radius_unit(radius_unit)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported radius unit: km, mi, or m."
            }
        
        # Build query parameters
        params = {
            "latLong": lat_long
        }
        
        if category:
            params["category"] = category
        if radius is not None:
            params["radius"] = str(radius)
        if radius_unit:
            params["radiusUnit"] = radius_unit
        if language:
            params["language"] = language
        
        # Make API call
        result = _make_api_call("GET", "/location/nearby_search", params)
        
        if result.get("error"):
            return result
        
        # Get locations and filter by price
        locations = result.get("data", [])
        if not locations:
            return result
        
        # Filter by price level
        locations = _filter_locations_by_price_level(locations, max_price_level)
        
        return {
            "error": False,
            "data": locations,
            "search_params": {
                "lat_long": lat_long,
                "max_price_level": max_price_level
            }
        }
    
    @mcp.tool(description=get_doc("search_nearby_by_distance", "tripadvisor"))
    def search_nearby_by_distance(
        lat_long: str,
        sort_by_distance: bool = True,
        category: Optional[str] = None,
        radius: Optional[float] = None,
        radius_unit: Optional[str] = None,
        language: Optional[str] = None
    ) -> Dict:
        """Search for locations near coordinates and return them sorted by distance (closest first). Perfect for finding the nearest places.
        
        Args:
            lat_long: Latitude and longitude in format "lat,lon" (required, e.g., "40.7128,-74.0060")
            sort_by_distance: If True, sort by distance ascending (closest first). If False, return unsorted.
            category: Filter by category: hotels | attractions | restaurants | geos
            radius: Search radius
            radius_unit: Unit for radius: km | mi | m
            language: Response language (default: "en")
        """
        # Validate lat_long
        is_valid, error_msg = _validate_lat_long(lat_long)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please provide lat_long in format 'lat,lon' (e.g., '40.7128,-74.0060')."
            }
        
        # Validate other parameters
        is_valid, error_msg = _validate_category(category)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported category or omit the category parameter."
            }
        
        is_valid, error_msg = _validate_language(language)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported language code or omit to use default (en)."
            }
        
        is_valid, error_msg = _validate_radius(radius)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please provide a positive number for radius."
            }
        
        is_valid, error_msg = _validate_radius_unit(radius_unit)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported radius unit: km, mi, or m."
            }
        
        # Build query parameters
        params = {
            "latLong": lat_long
        }
        
        if category:
            params["category"] = category
        if radius is not None:
            params["radius"] = str(radius)
        if radius_unit:
            params["radiusUnit"] = radius_unit
        if language:
            params["language"] = language
        
        # Make API call
        result = _make_api_call("GET", "/location/nearby_search", params)
        
        if result.get("error"):
            return result
        
        # Get locations and sort by distance
        locations = result.get("data", [])
        if not locations:
            return result
        
        # Sort by distance if requested
        if sort_by_distance:
            locations = _sort_locations_by_distance(locations, reverse=False)
        
        return {
            "error": False,
            "data": locations,
            "search_params": {
                "lat_long": lat_long,
                "sort_by_distance": sort_by_distance
            }
        }
    
    @mcp.tool(description=get_doc("find_closest_location", "tripadvisor"))
    def find_closest_location(
        lat_long: str,
        category: Optional[str] = None,
        radius: Optional[float] = None,
        radius_unit: Optional[str] = None,
        language: Optional[str] = None
    ) -> Dict:
        """Find the single closest location to given coordinates. Perfect for "find nearest" queries.
        
        Args:
            lat_long: Latitude and longitude in format "lat,lon" (required, e.g., "40.7128,-74.0060")
            category: Filter by category: hotels | attractions | restaurants | geos
            radius: Search radius
            radius_unit: Unit for radius: km | mi | m
            language: Response language (default: "en")
        """
        # Validate lat_long
        is_valid, error_msg = _validate_lat_long(lat_long)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": {},
                "suggestion": "Please provide lat_long in format 'lat,lon' (e.g., '40.7128,-74.0060')."
            }
        
        # Validate other parameters
        is_valid, error_msg = _validate_category(category)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": {},
                "suggestion": "Please use a supported category or omit the category parameter."
            }
        
        is_valid, error_msg = _validate_language(language)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": {},
                "suggestion": "Please use a supported language code or omit to use default (en)."
            }
        
        is_valid, error_msg = _validate_radius(radius)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": {},
                "suggestion": "Please provide a positive number for radius."
            }
        
        is_valid, error_msg = _validate_radius_unit(radius_unit)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": {},
                "suggestion": "Please use a supported radius unit: km, mi, or m."
            }
        
        # Build query parameters
        params = {
            "latLong": lat_long
        }
        
        if category:
            params["category"] = category
        if radius is not None:
            params["radius"] = str(radius)
        if radius_unit:
            params["radiusUnit"] = radius_unit
        if language:
            params["language"] = language
        
        # Make API call
        result = _make_api_call("GET", "/location/nearby_search", params)
        
        if result.get("error"):
            return result
        
        # Get locations and find closest
        locations = result.get("data", [])
        if not locations:
            return {
                "error": False,
                "data": {},
                "message": "No locations found near the specified coordinates."
            }
        
        # Sort by distance and get closest
        locations = _sort_locations_by_distance(locations, reverse=False)
        closest = locations[0] if locations else {}
        
        return {
            "error": False,
            "data": closest,
            "search_params": {
                "lat_long": lat_long,
                "total_found": len(locations)
            }
        }
    
    @mcp.tool(description=get_doc("search_restaurants_by_cuisine", "tripadvisor"))
    def search_restaurants_by_cuisine(
        search_query: str,
        cuisine_types: List[str],
        language: Optional[str] = None
    ) -> Dict:
        """Search for restaurants and filter by cuisine type(s). Perfect for finding specific types of food.
        
        Args:
            search_query: Text to search for (required, e.g., "restaurants Paris")
            cuisine_types: List of cuisine types to filter by (required, e.g., ["Italian", "French"])
            language: Response language (default: "en")
        
        Note: This function first searches for restaurants, then gets details for each to check cuisine.
        For better performance, consider using search_locations with category="restaurants" and filtering manually.
        """
        # Validate search_query
        if not search_query or not isinstance(search_query, str) or not search_query.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": "Search query is required and must be a non-empty string.",
                "data": [],
                "suggestion": "Please provide a search query."
            }
        
        # Validate cuisine_types
        if not cuisine_types or not isinstance(cuisine_types, list) or len(cuisine_types) == 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": "Cuisine types are required and must be a non-empty list.",
                "data": [],
                "suggestion": "Please provide at least one cuisine type (e.g., ['Italian', 'French'])."
            }
        
        # Validate language
        is_valid, error_msg = _validate_language(language)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported language code or omit to use default (en)."
            }
        
        # Build query parameters
        params = {
            "searchQuery": search_query.strip(),
            "category": "restaurants"
        }
        
        if language:
            params["language"] = language
        
        # Make API call
        result = _make_api_call("GET", "/location/search", params)
        
        if result.get("error"):
            return result
        
        # Get locations
        locations = result.get("data", [])
        if not locations:
            return result
        
        def normalize_cuisine(cuisine_str: str) -> str:
            """Normalize cuisine string for matching."""
            if not cuisine_str:
                return ""
            # Convert to lowercase and strip whitespace
            normalized = cuisine_str.lower().strip()
            # Remove common suffixes/prefixes that might interfere with matching
            normalized = normalized.replace(" cuisine", "").replace(" restaurant", "")
            normalized = normalized.replace(" food", "").replace(" dining", "")
            return normalized
        
        def extract_cuisine_list(cuisine_data) -> List[str]:
            """Extract list of cuisine strings from various formats."""
            cuisine_list = []
            if not cuisine_data:
                return cuisine_list
            
            if isinstance(cuisine_data, list):
                for item in cuisine_data:
                    if isinstance(item, str):
                        cuisine_list.append(normalize_cuisine(item))
                    elif isinstance(item, dict):
                        # Try multiple possible keys
                        name = (item.get("name") or 
                               item.get("value") or 
                               item.get("label") or
                               item.get("cuisine") or
                               str(item))
                        cuisine_list.append(normalize_cuisine(name))
                    else:
                        cuisine_list.append(normalize_cuisine(str(item)))
            elif isinstance(cuisine_data, str):
                # Handle comma-separated cuisine strings
                if "," in cuisine_data:
                    for part in cuisine_data.split(","):
                        cuisine_list.append(normalize_cuisine(part))
                else:
                    cuisine_list.append(normalize_cuisine(cuisine_data))
            else:
                cuisine_list.append(normalize_cuisine(str(cuisine_data)))
            
            return cuisine_list
        
        def matches_cuisine(location_cuisines: List[str], search_cuisines: List[str]) -> bool:
            """Check if any location cuisine matches any search cuisine (flexible matching)."""
            if not location_cuisines or not search_cuisines:
                return False
            
            for search_cuisine in search_cuisines:
                search_normalized = normalize_cuisine(search_cuisine)
                if not search_normalized:
                    continue
                
                for loc_cuisine in location_cuisines:
                    if not loc_cuisine:
                        continue
                    
                    # Exact match
                    if search_normalized == loc_cuisine:
                        return True
                    
                    # Partial match (search term is contained in location cuisine)
                    if search_normalized in loc_cuisine:
                        return True
                    
                    # Partial match (location cuisine is contained in search term)
                    if loc_cuisine in search_normalized:
                        return True
                    
                    # Word-based matching (check if key words match)
                    search_words = set(search_normalized.split())
                    loc_words = set(loc_cuisine.split())
                    if search_words and loc_words and search_words.intersection(loc_words):
                        return True
            
            return False
        
        # Normalize search cuisine types
        normalized_search_cuisines = [normalize_cuisine(c) for c in cuisine_types]
        
        # First, try to filter by cuisine from search results if available
        filtered_locations = []
        locations_needing_details = []
        
        for location in locations:
            # Try to get cuisine from search result if available
            cuisine = location.get("cuisine") or location.get("cuisineType") or location.get("cuisine_type")
            
            # Also check location name for cuisine hints (e.g., "Italian Restaurant")
            location_name = location.get("name", "").lower()
            name_has_cuisine = any(normalize_cuisine(c) in location_name for c in cuisine_types)
            
            if cuisine:
                location_cuisines = extract_cuisine_list(cuisine)
                if matches_cuisine(location_cuisines, cuisine_types):
                    filtered_locations.append(location)
                elif name_has_cuisine:
                    # If name suggests the cuisine, include it
                    filtered_locations.append(location)
                else:
                    # Doesn't match, don't include
                    pass
            elif name_has_cuisine:
                # No cuisine data but name suggests it, include it
                filtered_locations.append(location)
            else:
                # No cuisine in search result, need to get details
                location_id = location.get("locationId") or location.get("id")
                if location_id:
                    locations_needing_details.append((location, location_id))
        
        # If we have locations without cuisine info, get details for them (limit to 10 to avoid too many API calls)
        if locations_needing_details and len(filtered_locations) < 10:
            for location, location_id in locations_needing_details[:10]:
                # Get details for this location with increased timeout for details calls
                detail_params = {}
                if language:
                    detail_params["language"] = language
                
                detail_result = _make_api_call("GET", f"/location/{location_id}/details", detail_params, timeout=15.0, is_single_object=True)
                
                # If API call failed, skip this location
                if detail_result.get("error"):
                    continue
                
                detail_data = detail_result.get("data", {})
                cuisine = detail_data.get("cuisine")
                
                # Also check name in details
                detail_name = detail_data.get("name", "").lower()
                name_has_cuisine = any(normalize_cuisine(c) in detail_name for c in cuisine_types)
                
                if cuisine:
                    location_cuisines = extract_cuisine_list(cuisine)
                    if matches_cuisine(location_cuisines, cuisine_types):
                        # Add cuisine info to location and include it
                        location["cuisine"] = cuisine
                        filtered_locations.append(location)
                    elif name_has_cuisine:
                        # Name suggests cuisine, include it
                        location["cuisine"] = cuisine if cuisine else []
                        filtered_locations.append(location)
                elif name_has_cuisine:
                    # No cuisine data but name suggests it, include it
                    filtered_locations.append(location)
        
        # If still no matches after checking details, be more lenient:
        # If search query itself contains cuisine keywords, include all results
        if not filtered_locations and locations:
            search_query_lower = search_query.lower()
            query_has_cuisine = any(normalize_cuisine(c) in search_query_lower for c in cuisine_types)
            
            if query_has_cuisine:
                # Search query itself mentions the cuisine, so include all results
                filtered_locations = locations[:10]  # Limit to 10
                return {
                    "error": False,
                    "data": filtered_locations,
                    "message": f"Search query contains cuisine keywords. Returning all restaurants from search (cuisine filtering applied to search query).",
                    "search_params": {
                        "query": search_query,
                        "cuisine_types": cuisine_types,
                        "filtered_count": len(filtered_locations),
                        "total_searched": len(locations),
                        "note": "Results based on search query containing cuisine keywords"
                    }
                }
        
        # If still no matches, return empty with helpful message
        if not filtered_locations:
            return {
                "error": False,
                "data": [],
                "message": f"No restaurants found matching cuisine types: {', '.join(cuisine_types)}. Try different cuisine types or a different search query.",
                "search_params": {
                    "query": search_query,
                    "cuisine_types": cuisine_types
                }
            }
        
        return {
            "error": False,
            "data": filtered_locations,
            "search_params": {
                "query": search_query,
                "cuisine_types": cuisine_types,
                "filtered_count": len(filtered_locations),
                "total_searched": len(locations)
            }
        }
    
    @mcp.tool(description=get_doc("get_multiple_location_details", "tripadvisor"))
    def get_multiple_location_details(
        location_ids: List[int],
        language: Optional[str] = None,
        currency: Optional[str] = None
    ) -> Dict:
        """Get details for multiple locations at once. More efficient than calling get_location_details multiple times.
        
        Args:
            location_ids: List of TripAdvisor location IDs (required, max 10)
            language: Response language (default: "en")
            currency: ISO 4217 currency code (default: "USD")
        """
        # Validate location_ids
        if not location_ids or not isinstance(location_ids, list) or len(location_ids) == 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": "Location IDs are required and must be a non-empty list.",
                "data": [],
                "suggestion": "Please provide at least one location ID."
            }
        
        if len(location_ids) > 10:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Too many location IDs: {len(location_ids)}. Maximum is 10.",
                "data": [],
                "suggestion": "Please provide up to 10 location IDs."
            }
        
        # Validate each location_id
        validated_ids = []
        for loc_id in location_ids:
            if isinstance(loc_id, str):
                try:
                    loc_id = int(loc_id)
                except ValueError:
                    return {
                        "error": True,
                        "error_code": "VALIDATION_ERROR",
                        "error_message": f"Invalid location ID: {loc_id}. Location ID must be a positive integer.",
                        "data": [],
                        "suggestion": "Please provide valid positive integer location IDs."
                    }
            
            is_valid, error_msg = _validate_location_id(loc_id)
            if not is_valid:
                return {
                    "error": True,
                    "error_code": "VALIDATION_ERROR",
                    "error_message": error_msg,
                    "data": [],
                    "suggestion": "Please provide valid positive integer location IDs."
                }
            validated_ids.append(loc_id)
        
        # Validate language
        is_valid, error_msg = _validate_language(language)
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": error_msg,
                "data": [],
                "suggestion": "Please use a supported language code or omit to use default (en)."
            }
        
        # Make sequential API calls (since _make_api_call is synchronous)
        results = []
        for loc_id in validated_ids:
            params = {}
            if language:
                params["language"] = language
            if currency:
                params["currency"] = currency
            
            # Use longer timeout for details calls
            result = _make_api_call("GET", f"/location/{loc_id}/details", params, timeout=15.0, is_single_object=True)
            results.append(result)
        
        # Combine results
        successful = []
        errors = []
        
        for i, result in enumerate(results):
            if result.get("error"):
                errors.append({
                    "location_id": validated_ids[i],
                    "error": result.get("error_message", "Unknown error")
                })
            else:
                successful.append(result.get("data", {}))
        
        return {
            "error": len(successful) == 0,  # Error only if all failed
            "data": successful,
            "errors": errors if errors else None,
            "summary": {
                "requested": len(validated_ids),
                "successful": len(successful),
                "failed": len(errors)
            }
        }
    
    @mcp.tool(description=get_doc("compare_locations", "tripadvisor"))
    def compare_locations(
        location_ids: List[int],
        language: Optional[str] = None,
        currency: Optional[str] = None
    ) -> Dict:
        """Compare 2-3 locations side by side. Returns a structured comparison of ratings, prices, distances, and other key attributes.
        
        Args:
            location_ids: List of 2-3 TripAdvisor location IDs to compare (required)
            language: Response language (default: "en")
            currency: ISO 4217 currency code (default: "USD")
        """
        # Validate location_ids
        if not location_ids or not isinstance(location_ids, list):
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": "Location IDs are required and must be a list.",
                "data": {},
                "suggestion": "Please provide a list of 2-3 location IDs."
            }
        
        if len(location_ids) < 2 or len(location_ids) > 3:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid number of location IDs: {len(location_ids)}. Must be 2 or 3.",
                "data": {},
                "suggestion": "Please provide exactly 2 or 3 location IDs to compare."
            }
        
        # Get details for all locations
        details_result = get_multiple_location_details(location_ids, language, currency)
        
        if details_result.get("error") or not details_result.get("data"):
            return {
                "error": True,
                "error_code": "API_ERROR",
                "error_message": "Failed to retrieve location details for comparison.",
                "data": {},
                "suggestion": "Please verify the location IDs are valid."
            }
        
        locations = details_result["data"]
        
        # Build comparison
        comparison = {
            "locations": [],
            "comparison": {}
        }
        
        for loc in locations:
            # Extract rating using the helper function
            rating_value = _extract_location_rating(loc)
            rating = rating_value if rating_value > 0 else None
            
            # Extract price level with multiple field checks
            price_level = (loc.get("priceLevel") or 
                          loc.get("price_level") or
                          loc.get("price") or
                          None)
            
            # Extract address with multiple format checks
            address = None
            if "address" in loc:
                addr = loc.get("address")
                if isinstance(addr, dict):
                    address = (addr.get("address_string") or 
                              addr.get("street1") or 
                              addr.get("addressString") or
                              str(addr))
                elif isinstance(addr, str):
                    address = addr
            elif "address_obj" in loc:
                addr_obj = loc.get("address_obj", {})
                address = (addr_obj.get("address_string") or 
                          addr_obj.get("street1") or
                          str(addr_obj))
            
            # Extract ranking with multiple format checks
            ranking = None
            if "ranking" in loc:
                ranking = loc.get("ranking")
            elif "rankingData" in loc:
                rank_data = loc.get("rankingData", {})
                if isinstance(rank_data, dict):
                    ranking = rank_data.get("ranking") or rank_data.get("rank")
                else:
                    ranking = rank_data
            
            # Extract cuisine with proper formatting
            cuisine = loc.get("cuisine")
            cuisine_list = None
            if cuisine:
                if isinstance(cuisine, list):
                    cuisine_list = []
                    for item in cuisine:
                        if isinstance(item, str):
                            cuisine_list.append(item)
                        elif isinstance(item, dict):
                            name = item.get("name") or item.get("value") or str(item)
                            cuisine_list.append(name)
                        else:
                            cuisine_list.append(str(item))
                elif isinstance(cuisine, str):
                    cuisine_list = [cuisine]
            
            loc_data = {
                "id": loc.get("locationId") or loc.get("id") or loc.get("location_id"),
                "name": loc.get("name"),
                "rating": rating,
                "price_level": price_level,
                "category": loc.get("category"),
                "address": address,
                "ranking": ranking,
                "cuisine": cuisine_list if cuisine_list else cuisine,
                "amenities": loc.get("amenities"),
                "features": loc.get("features"),
                "tripadvisor_url": loc.get("webUrl") or loc.get("tripadvisorUrl") or loc.get("url")
            }
            comparison["locations"].append(loc_data)
        
        # Add summary comparison
        ratings = [loc.get("rating") for loc in comparison["locations"] if loc.get("rating") is not None]
        if ratings:
            comparison["comparison"]["highest_rated"] = max(ratings)
            comparison["comparison"]["lowest_rated"] = min(ratings)
            comparison["comparison"]["average_rating"] = sum(ratings) / len(ratings)
        
        price_levels = [loc.get("price_level") for loc in comparison["locations"] if loc.get("price_level") is not None]
        if price_levels:
            comparison["comparison"]["most_expensive"] = max(price_levels)
            comparison["comparison"]["most_affordable"] = min(price_levels)
        
        return {
            "error": False,
            "data": comparison,
            "summary": {
                "compared": len(location_ids),
                "successful": len(locations)
            }
        }

