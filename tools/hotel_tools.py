"""
Single-purpose hotel filtering, sorting, and selection tools.
"""

from typing import List, Dict, Any, Optional
from langchain_core.tools import tool


@tool
def filter_hotels_by_rating(hotels: List[Dict[str, Any]], min_rating: float) -> List[Dict[str, Any]]:
    """
    Filter hotels by minimum overall rating.
    
    Args:
        hotels: List of hotel properties
        min_rating: Minimum rating threshold (e.g., 4.0)
    
    Returns:
        Filtered list of hotels meeting the rating requirement
    """
    return [h for h in hotels if h.get("overall_rating", 0) >= min_rating]


@tool
def filter_hotels_by_price(hotels: List[Dict[str, Any]], max_price: float) -> List[Dict[str, Any]]:
    """
    Filter hotels by maximum price per night.
    
    Args:
        hotels: List of hotel properties
        max_price: Maximum price per night
    
    Returns:
        Filtered list of hotels within the price range
    """
    filtered = []
    for h in hotels:
        rate = h.get("rate_per_night", {})
        price = rate.get("extracted_lowest", 0)
        if price and price <= max_price:
            filtered.append(h)
    return filtered


@tool
def filter_hotels_by_class(hotels: List[Dict[str, Any]], min_class: int) -> List[Dict[str, Any]]:
    """
    Filter hotels by minimum hotel class (star rating).
    
    Args:
        hotels: List of hotel properties
        min_class: Minimum hotel class (e.g., 3, 4, 5)
    
    Returns:
        Filtered list of hotels meeting the class requirement
    """
    return [h for h in hotels if h.get("extracted_hotel_class", 0) >= min_class]


@tool
def filter_hotels_by_amenities(hotels: List[Dict[str, Any]], required_amenities: List[str]) -> List[Dict[str, Any]]:
    """
    Filter hotels that have all required amenities.
    
    Args:
        hotels: List of hotel properties
        required_amenities: List of required amenity names (e.g., ["Free Wi-Fi", "Pool"])
    
    Returns:
        Filtered list of hotels with all required amenities
    """
    filtered = []
    for h in hotels:
        amenities = h.get("amenities", [])
        amenities_lower = [a.lower() for a in amenities]
        if all(req.lower() in amenities_lower for req in required_amenities):
            filtered.append(h)
    return filtered


@tool
def sort_hotels_by_price(hotels: List[Dict[str, Any]], ascending: bool = True) -> List[Dict[str, Any]]:
    """
    Sort hotels by price per night.
    
    Args:
        hotels: List of hotel properties
        ascending: If True, sort from lowest to highest price; if False, highest to lowest
    
    Returns:
        Sorted list of hotels
    """
    return sorted(
        hotels,
        key=lambda h: h.get("rate_per_night", {}).get("extracted_lowest", float('inf')),
        reverse=not ascending
    )


@tool
def sort_hotels_by_rating(hotels: List[Dict[str, Any]], ascending: bool = False) -> List[Dict[str, Any]]:
    """
    Sort hotels by overall rating.
    
    Args:
        hotels: List of hotel properties
        ascending: If True, sort from lowest to highest rating; if False, highest to lowest
    
    Returns:
        Sorted list of hotels
    """
    return sorted(
        hotels,
        key=lambda h: h.get("overall_rating", 0),
        reverse=not ascending
    )


@tool
def get_top_hotels(hotels: List[Dict[str, Any]], n: int = 5) -> List[Dict[str, Any]]:
    """
    Get the top N hotels from the list.
    
    Args:
        hotels: List of hotel properties
        n: Number of top hotels to return (max 10)
    
    Returns:
        List of top N hotels
    """
    # Limit to max 10 to reduce tokens
    n = min(n, 10)
    return hotels[:n]


@tool
def select_hotel_by_name(hotels: List[Dict[str, Any]], hotel_name: str) -> Optional[Dict[str, Any]]:
    """
    Select a hotel by name (case-insensitive partial match).
    
    Args:
        hotels: List of hotel properties
        hotel_name: Name or partial name of the hotel
    
    Returns:
        Selected hotel property or None if not found
    """
    hotel_name_lower = hotel_name.lower()
    for h in hotels:
        if hotel_name_lower in h.get("name", "").lower():
            return h
    return None


@tool
def select_hotel_by_index(hotels: List[Dict[str, Any]], index: int) -> Optional[Dict[str, Any]]:
    """
    Select a hotel by its index in the list.
    
    Args:
        hotels: List of hotel properties
        index: Zero-based index of the hotel
    
    Returns:
        Selected hotel property or None if index is out of range
    """
    if 0 <= index < len(hotels):
        return hotels[index]
    return None


@tool
def get_hotel_summary(hotel: Dict[str, Any]) -> str:
    """
    Get a clean, concise summary of a hotel.
    
    Args:
        hotel: Hotel property dictionary
    
    Returns:
        Clean formatted string with hotel summary
    """
    name = hotel.get("name", "Unknown")
    rating = hotel.get("overall_rating", "N/A")
    reviews = hotel.get("reviews", 0)
    hotel_class = hotel.get("hotel_class", 0)
    rate = hotel.get("rate_per_night", {})
    price = rate.get("lowest", "N/A")
    amenities = hotel.get("amenities", [])[:3]  # Only top 3 amenities
    
    # Format amenities nicely
    amenity_text = ", ".join(amenities) if amenities else "Standard amenities"
    
    # Create clean summary
    summary = f"🏨 **{name}**\n"
    summary += f"⭐ {rating}/5 ({reviews:,} reviews) • {hotel_class}-star • {price}/night\n"
    summary += f"✨ {amenity_text}"
    
    return summary


@tool
def format_hotels_list(hotels: List[Dict[str, Any]], max_hotels: int = 5) -> str:
    """
    Format a list of hotels in a clean, readable format.
    
    Args:
        hotels: List of hotel properties
        max_hotels: Maximum number of hotels to display
    
    Returns:
        Clean formatted string with hotel list
    """
    if not hotels:
        return "No hotels found matching your criteria."
    
    # Limit to max_hotels
    hotels = hotels[:max_hotels]
    
    result = f"🏨 **Found {len(hotels)} hotel{'s' if len(hotels) > 1 else ''}:**\n\n"
    
    for i, hotel in enumerate(hotels, 1):
        name = hotel.get("name", "Unknown Hotel")
        rating = hotel.get("overall_rating", 0)
        reviews = hotel.get("reviews", 0)
        hotel_class = hotel.get("hotel_class", 0)
        rate = hotel.get("rate_per_night", {})
        price = rate.get("lowest", "N/A")
        amenities = hotel.get("amenities", [])[:3]
        
        # Format amenities
        amenity_text = ", ".join(amenities) if amenities else "Standard amenities"
        
        # Format reviews count
        reviews_text = f"{reviews:,}" if reviews > 0 else "No reviews"
        
        result += f"**{i}. {name}**\n"
        result += f"   ⭐ {rating}/5 ({reviews_text}) • {hotel_class}-star • {price}/night\n"
        result += f"   ✨ {amenity_text}\n\n"
    
    return result.strip()

