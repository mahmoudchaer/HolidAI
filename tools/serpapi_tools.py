"""
Enhanced SerpApi tools for fetching comprehensive hotel data.
Includes better error handling, more data fields, and advanced search capabilities.
"""

import requests
import os
import logging
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables from .env file
load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SERPAPI_BASE_URL = "https://serpapi.com/search"

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@tool
def fetch_hotels(
    city: str,
    check_in_date: str,
    check_out_date: str,
    adults: int = 2,
    children: int = 0,
    currency: str = "USD",
    gl: str = "us",
    hl: str = "en",
    max_results: int = 15
) -> List[Dict[str, Any]]:
    """
    Fetch hotels from SerpApi Google Hotels API with enhanced data and error handling.
    
    Args:
        city: City or location to search (e.g., "Paris", "New York")
        check_in_date: Check-in date in YYYY-MM-DD format (e.g., "2025-10-16")
        check_out_date: Check-out date in YYYY-MM-DD format (e.g., "2025-10-20")
        adults: Number of adults (default: 2)
        children: Number of children (default: 0)
        currency: Currency code (default: "USD")
        gl: Country code for localization (default: "us")
        hl: Language code (default: "en")
        max_results: Maximum number of results to return (default: 15)
    
    Returns:
        List of hotel properties with comprehensive details
    """
    if not SERPAPI_KEY:
        raise ValueError("SERPAPI_KEY environment variable not set")
    
    # Validate dates
    try:
        check_in = datetime.strptime(check_in_date, "%Y-%m-%d")
        check_out = datetime.strptime(check_out_date, "%Y-%m-%d")
        if check_out <= check_in:
            raise ValueError("Check-out date must be after check-in date")
    except ValueError as e:
        raise ValueError(f"Invalid date format or logic: {str(e)}")
    
    params = {
        "engine": "google_hotels",
        "q": city,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "adults": adults,
        "currency": currency,
        "gl": gl,
        "hl": hl,
        "api_key": SERPAPI_KEY,
        "output": "json"
    }
    
    if children > 0:
        params["children"] = children
    
    try:
        logger.info(f"Fetching hotels for {city} from {check_in_date} to {check_out_date}")
        resp = requests.get(SERPAPI_BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        # Check for API errors
        if "error" in data:
            raise Exception(f"SerpApi error: {data['error']}")
        
        properties = data.get("properties", [])
        logger.info(f"Found {len(properties)} hotels")
        
        # Limit results
        properties = properties[:max_results]
        
        # Enhanced data processing
        enhanced_hotels = []
        for prop in properties:
            try:
                # Extract comprehensive hotel data
                hotel_data = {
                    "name": prop.get("name", "Unknown Hotel"),
                    "overall_rating": prop.get("overall_rating", 0),
                    "reviews": prop.get("reviews", 0),
                    "hotel_class": prop.get("hotel_class", 0),
                    "rate_per_night": prop.get("rate_per_night", {}),
                    "total_rate": prop.get("total_rate", {}),
                    "amenities": prop.get("amenities", [])[:8],  # More amenities
                    "nearby_places": prop.get("nearby_places", [])[:5],  # More nearby places
                    "link": prop.get("link", ""),
                    "property_token": prop.get("property_token", ""),
                    "address": prop.get("address", ""),
                    "phone": prop.get("phone", ""),
                    "images": prop.get("images", [])[:3],  # Hotel images
                    "description": prop.get("description", ""),
                    "check_in_time": prop.get("check_in_time", ""),
                    "check_out_time": prop.get("check_out_time", ""),
                    "cancellation_policy": prop.get("cancellation_policy", ""),
                    "pet_friendly": prop.get("pet_friendly", False),
                    "free_wifi": prop.get("free_wifi", False),
                    "parking": prop.get("parking", False),
                    "pool": prop.get("pool", False),
                    "gym": prop.get("gym", False),
                    "restaurant": prop.get("restaurant", False),
                    "spa": prop.get("spa", False),
                    "business_center": prop.get("business_center", False),
                    "airport_shuttle": prop.get("airport_shuttle", False),
                    "room_types": prop.get("room_types", [])[:3],  # Available room types
                    "deals": prop.get("deals", []),  # Current deals/promotions
                    "loyalty_program": prop.get("loyalty_program", ""),
                    "last_updated": datetime.now().isoformat()
                }
                
                # Calculate price per night if not available
                if not hotel_data["rate_per_night"] and hotel_data["total_rate"]:
                    nights = (check_out - check_in).days
                    total_price = hotel_data["total_rate"].get("extracted_lowest", 0)
                    if total_price and nights > 0:
                        hotel_data["rate_per_night"] = {
                            "lowest": f"${total_price/nights:.2f}",
                            "extracted_lowest": total_price/nights
                        }
                
                enhanced_hotels.append(hotel_data)
                
            except Exception as e:
                logger.warning(f"Error processing hotel {prop.get('name', 'Unknown')}: {str(e)}")
                continue
        
        logger.info(f"Successfully processed {len(enhanced_hotels)} hotels")
        return enhanced_hotels
        
    except requests.exceptions.Timeout:
        raise Exception("Request timed out. Please try again.")
    except requests.exceptions.ConnectionError:
        raise Exception("Connection error. Please check your internet connection.")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            raise Exception("Invalid API key. Please check your SERPAPI_KEY.")
        elif e.response.status_code == 429:
            raise Exception("API rate limit exceeded. Please try again later.")
        else:
            raise Exception(f"HTTP error {e.response.status_code}: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error fetching hotels: {str(e)}")
        raise Exception(f"Failed to fetch hotels: {str(e)}")


@tool
def get_hotel_details(property_token: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific hotel property.
    
    Args:
        property_token: Unique token identifying the property
    
    Returns:
        Detailed hotel information including amenities, reviews, nearby places
    """
    if not SERPAPI_KEY:
        raise ValueError("SERPAPI_KEY environment variable not set")
    
    params = {
        "engine": "google_hotels",
        "property_token": property_token,
        "api_key": SERPAPI_KEY,
        "output": "json"
    }
    
    try:
        logger.info(f"Fetching details for hotel token: {property_token}")
        resp = requests.get(SERPAPI_BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        if "error" in data:
            raise Exception(f"SerpApi error: {data['error']}")
            
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch hotel details: {str(e)}")
        raise Exception(f"Failed to fetch hotel details: {str(e)}")


@tool
def search_hotels_near_landmark(
    landmark: str,
    check_in_date: str,
    check_out_date: str,
    radius_km: int = 5,
    adults: int = 2,
    children: int = 0,
    currency: str = "USD"
) -> List[Dict[str, Any]]:
    """
    Search for hotels near a specific landmark or attraction.
    
    Args:
        landmark: Landmark name (e.g., "Eiffel Tower", "Times Square")
        check_in_date: Check-in date in YYYY-MM-DD format
        check_out_date: Check-out date in YYYY-MM-DD format
        radius_km: Search radius in kilometers (default: 5)
        adults: Number of adults (default: 2)
        children: Number of children (default: 0)
        currency: Currency code (default: "USD")
    
    Returns:
        List of hotels near the specified landmark
    """
    # Use the landmark as the search query
    return fetch_hotels(
        city=f"hotels near {landmark}",
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        adults=adults,
        children=children,
        currency=currency,
        max_results=10
    )


@tool
def search_hotels_by_chain(
    hotel_chain: str,
    city: str,
    check_in_date: str,
    check_out_date: str,
    adults: int = 2,
    children: int = 0,
    currency: str = "USD"
) -> List[Dict[str, Any]]:
    """
    Search for hotels from a specific chain in a city.
    
    Args:
        hotel_chain: Hotel chain name (e.g., "Marriott", "Hilton", "Holiday Inn")
        city: City to search in
        check_in_date: Check-in date in YYYY-MM-DD format
        check_out_date: Check-out date in YYYY-MM-DD format
        adults: Number of adults (default: 2)
        children: Number of children (default: 0)
        currency: Currency code (default: "USD")
    
    Returns:
        List of hotels from the specified chain
    """
    # Search for hotels from specific chain
    return fetch_hotels(
        city=f"{hotel_chain} hotels in {city}",
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        adults=adults,
        children=children,
        currency=currency,
        max_results=10
    )


@tool
def search_hotels_with_deals(
    city: str,
    check_in_date: str,
    check_out_date: str,
    adults: int = 2,
    children: int = 0,
    currency: str = "USD"
) -> List[Dict[str, Any]]:
    """
    Search for hotels with current deals and promotions.
    
    Args:
        city: City to search in
        check_in_date: Check-in date in YYYY-MM-DD format
        check_out_date: Check-out date in YYYY-MM-DD format
        adults: Number of adults (default: 2)
        children: Number of children (default: 0)
        currency: Currency code (default: "USD")
    
    Returns:
        List of hotels with current deals
    """
    hotels = fetch_hotels(
        city=city,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        adults=adults,
        children=children,
        currency=currency,
        max_results=20
    )
    
    # Filter hotels that have deals
    hotels_with_deals = []
    for hotel in hotels:
        if hotel.get("deals") or hotel.get("loyalty_program"):
            hotels_with_deals.append(hotel)
    
    return hotels_with_deals[:10]  # Return top 10 with deals

