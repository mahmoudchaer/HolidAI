"""
Tools for exploring nearby places and attractions.
"""

from typing import List, Dict, Any
from langchain_core.tools import tool


@tool
def get_nearby_places(hotel: Dict[str, Any], limit: int = 3) -> List[Dict[str, Any]]:
    """
    Get nearby places from hotel data.
    
    Args:
        hotel: Hotel property dictionary
        limit: Maximum number of places to return (max 5)
    
    Returns:
        List of nearby places with transportation info
    """
    nearby = hotel.get("nearby_places", [])
    limit = min(limit, 5)  # Max 5 places
    return nearby[:limit]


@tool
def format_nearby_places(nearby_places: List[Dict[str, Any]]) -> str:
    """
    Format nearby places into a readable string.
    
    Args:
        nearby_places: List of nearby place dictionaries
    
    Returns:
        Formatted string with nearby places information
    """
    if not nearby_places:
        return "No nearby places information available."
    
    formatted = ["Nearby Places:"]
    for i, place in enumerate(nearby_places, 1):
        name = place.get("name", "Unknown")
        transports = place.get("transportations", [])
        
        formatted.append(f"\n{i}. {name}")
        if transports:
            for transport in transports:
                t_type = transport.get("type", "Unknown")
                duration = transport.get("duration", "N/A")
                formatted.append(f"   - {t_type}: {duration}")
    
    return "\n".join(formatted)


@tool
def extract_place_names(nearby_places: List[Dict[str, Any]]) -> List[str]:
    """
    Extract just the names of nearby places.
    
    Args:
        nearby_places: List of nearby place dictionaries
    
    Returns:
        List of place names
    """
    return [place.get("name", "Unknown") for place in nearby_places]


@tool
def filter_places_by_transport_type(
    nearby_places: List[Dict[str, Any]],
    transport_type: str
) -> List[Dict[str, Any]]:
    """
    Filter nearby places by available transportation type.
    
    Args:
        nearby_places: List of nearby place dictionaries
        transport_type: Type of transportation (e.g., "Walking", "Taxi", "Public transport")
    
    Returns:
        Filtered list of places accessible by the specified transport type
    """
    filtered = []
    transport_type_lower = transport_type.lower()
    
    for place in nearby_places:
        transports = place.get("transportations", [])
        for transport in transports:
            if transport_type_lower in transport.get("type", "").lower():
                filtered.append(place)
                break
    
    return filtered

