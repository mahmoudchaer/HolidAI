"""TripAdvisor-related tools for the MCP server."""

import os
import httpx
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
        
        # Make API request
        with httpx.Client(timeout=timeout) as client:
            if method.upper() == "GET":
                response = client.get(f"{BASE_URL}{endpoint}", params=params)
            else:
                response = client.post(f"{BASE_URL}{endpoint}", json=params)
            
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
    except httpx.TimeoutException:
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
    except Exception:
        default_data = {} if is_single_object else []
        return {
            "error": True,
            "error_code": "UNEXPECTED_ERROR",
            "error_message": "An unexpected error occurred during the TripAdvisor API call. Please try again.",
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
        
        return _make_api_call("GET", f"/location/{location_id}/reviews", params)
    
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
        
        return _make_api_call("GET", f"/location/{location_id}/details", params, is_single_object=True)
    
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

