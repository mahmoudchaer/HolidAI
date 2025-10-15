"""
Atomic SerpApi tools for fetching hotel data.
Each tool has a single, clear purpose.
"""

import requests
import os
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SERPAPI_BASE_URL = "https://serpapi.com/search"


@tool
def fetch_hotels(
    city: str,
    check_in_date: str,
    check_out_date: str,
    adults: int = 2,
    children: int = 0,
    currency: str = "USD",
    gl: str = "us",
    hl: str = "en"
) -> List[Dict[str, Any]]:
    """
    Fetch hotels from SerpApi Google Hotels API.
    
    Args:
        city: City or location to search (e.g., "Paris", "New York")
        check_in_date: Check-in date in YYYY-MM-DD format (e.g., "2025-10-16")
        check_out_date: Check-out date in YYYY-MM-DD format (e.g., "2025-10-20")
        adults: Number of adults (default: 2)
        children: Number of children (default: 0)
        currency: Currency code (default: "USD")
        gl: Country code for localization (default: "us")
        hl: Language code (default: "en")
    
    Returns:
        List of hotel properties with details
    """
    if not SERPAPI_KEY:
        raise ValueError("SERPAPI_KEY environment variable not set")
    
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
        resp = requests.get(SERPAPI_BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        properties = data.get("properties", [])
        
        # Limit to 10 hotels to reduce token usage
        properties = properties[:10]
        
        # Simplify data - keep only essential fields
        simplified = []
        for prop in properties:
            simplified.append({
                "name": prop.get("name"),
                "overall_rating": prop.get("overall_rating"),
                "reviews": prop.get("reviews"),
                "hotel_class": prop.get("hotel_class"),
                "rate_per_night": prop.get("rate_per_night"),
                "total_rate": prop.get("total_rate"),
                "amenities": prop.get("amenities", [])[:5],  # Only first 5 amenities
                "nearby_places": prop.get("nearby_places", [])[:3],  # Only 3 nearby places
                "link": prop.get("link")
            })
        
        return simplified
    except requests.exceptions.RequestException as e:
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
        resp = requests.get(SERPAPI_BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch hotel details: {str(e)}")

