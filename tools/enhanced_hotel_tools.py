"""
Enhanced hotel filtering, sorting, and analysis tools.
Includes advanced filtering, comparison, and recommendation capabilities.
"""

from typing import List, Dict, Any, Optional, Tuple
from langchain_core.tools import tool
import re
from datetime import datetime


@tool
def filter_hotels_by_amenities(
    hotels: List[Dict[str, Any]], 
    required_amenities: List[str],
    match_all: bool = True
) -> List[Dict[str, Any]]:
    """
    Filter hotels by required amenities with flexible matching.
    
    Args:
        hotels: List of hotel properties
        required_amenities: List of required amenities (e.g., ["Pool", "Gym", "Free WiFi"])
        match_all: If True, hotel must have ALL amenities; if False, hotel must have ANY amenity
    
    Returns:
        Filtered list of hotels meeting amenity requirements
    """
    if not required_amenities:
        return hotels
    
    filtered = []
    for hotel in hotels:
        hotel_amenities = hotel.get("amenities", [])
        hotel_amenities_lower = [a.lower() for a in hotel_amenities]
        
        # Check if hotel has required amenities
        has_amenities = []
        for req_amenity in required_amenities:
            req_lower = req_amenity.lower()
            # Check for exact match or partial match
            found = any(req_lower in amenity.lower() or amenity.lower() in req_lower 
                       for amenity in hotel_amenities)
            has_amenities.append(found)
        
        # Apply matching logic
        if match_all and all(has_amenities):
            filtered.append(hotel)
        elif not match_all and any(has_amenities):
            filtered.append(hotel)
    
    return filtered


@tool
def filter_hotels_by_location_type(
    hotels: List[Dict[str, Any]], 
    location_types: List[str]
) -> List[Dict[str, Any]]:
    """
    Filter hotels by location type (city center, airport, beach, etc.).
    
    Args:
        hotels: List of hotel properties
        location_types: List of location types (e.g., ["city center", "airport", "beach"])
    
    Returns:
        Filtered list of hotels in specified location types
    """
    if not location_types:
        return hotels
    
    filtered = []
    for hotel in hotels:
        address = hotel.get("address", "").lower()
        nearby_places = hotel.get("nearby_places", [])
        
        # Check if hotel matches any location type
        for location_type in location_types:
            location_lower = location_type.lower()
            
            # Check address
            if location_lower in address:
                filtered.append(hotel)
                break
            
            # Check nearby places
            for place in nearby_places:
                place_name = place.get("name", "").lower()
                if location_lower in place_name:
                    filtered.append(hotel)
                    break
    
    return filtered


@tool
def filter_hotels_by_room_features(
    hotels: List[Dict[str, Any]], 
    room_features: List[str]
) -> List[Dict[str, Any]]:
    """
    Filter hotels by room features and types.
    
    Args:
        hotels: List of hotel properties
        room_features: List of room features (e.g., ["suite", "balcony", "ocean view"])
    
    Returns:
        Filtered list of hotels with specified room features
    """
    if not room_features:
        return hotels
    
    filtered = []
    for hotel in hotels:
        room_types = hotel.get("room_types", [])
        amenities = hotel.get("amenities", [])
        
        # Check room types and amenities for features
        all_text = " ".join(room_types + amenities).lower()
        
        for feature in room_features:
            if feature.lower() in all_text:
                filtered.append(hotel)
                break
    
    return filtered


@tool
def sort_hotels_by_value(
    hotels: List[Dict[str, Any]], 
    ascending: bool = True
) -> List[Dict[str, Any]]:
    """
    Sort hotels by value (rating per dollar).
    
    Args:
        hotels: List of hotel properties
        ascending: If True, sort from best value to worst; if False, worst to best
    
    Returns:
        Sorted list of hotels by value
    """
    def calculate_value_score(hotel):
        rating = hotel.get("overall_rating", 0)
        price = hotel.get("rate_per_night", {}).get("extracted_lowest", 0)
        
        if price and price > 0:
            return rating / price
        return 0
    
    return sorted(
        hotels,
        key=calculate_value_score,
        reverse=not ascending
    )


@tool
def sort_hotels_by_popularity(
    hotels: List[Dict[str, Any]], 
    ascending: bool = False
) -> List[Dict[str, Any]]:
    """
    Sort hotels by popularity (number of reviews).
    
    Args:
        hotels: List of hotel properties
        ascending: If True, sort from least to most popular; if False, most to least
    
    Returns:
        Sorted list of hotels by popularity
    """
    return sorted(
        hotels,
        key=lambda h: h.get("reviews", 0),
        reverse=not ascending
    )


@tool
def sort_hotels_by_distance_from_landmark(
    hotels: List[Dict[str, Any]], 
    landmark: str,
    ascending: bool = True
) -> List[Dict[str, Any]]:
    """
    Sort hotels by distance from a landmark (based on nearby places).
    
    Args:
        hotels: List of hotel properties
        landmark: Landmark name to sort by distance from
        ascending: If True, sort from closest to farthest; if False, farthest to closest
    
    Returns:
        Sorted list of hotels by distance from landmark
    """
    def get_distance_score(hotel):
        nearby_places = hotel.get("nearby_places", [])
        landmark_lower = landmark.lower()
        
        for place in nearby_places:
            place_name = place.get("name", "").lower()
            if landmark_lower in place_name:
                # Return a score based on how close the match is
                return len(place_name) - len(landmark_lower)
        
        return float('inf')  # No nearby landmark found
    
    return sorted(
        hotels,
        key=get_distance_score,
        reverse=not ascending
    )


@tool
def compare_hotels_detailed(
    hotel1: Dict[str, Any], 
    hotel2: Dict[str, Any],
    nights: int = 1
) -> Dict[str, Any]:
    """
    Provide detailed comparison between two hotels.
    
    Args:
        hotel1: First hotel property
        hotel2: Second hotel property
        nights: Number of nights for cost calculation
    
    Returns:
        Detailed comparison including costs, amenities, and recommendations
    """
    # Extract key information
    name1 = hotel1.get("name", "Hotel 1")
    name2 = hotel2.get("name", "Hotel 2")
    
    rating1 = hotel1.get("overall_rating", 0)
    rating2 = hotel2.get("overall_rating", 0)
    
    reviews1 = hotel1.get("reviews", 0)
    reviews2 = hotel2.get("reviews", 0)
    
    price1 = hotel1.get("rate_per_night", {}).get("extracted_lowest", 0)
    price2 = hotel2.get("rate_per_night", {}).get("extracted_lowest", 0)
    
    amenities1 = hotel1.get("amenities", [])
    amenities2 = hotel2.get("amenities", [])
    
    # Calculate costs
    total_cost1 = price1 * nights if price1 else 0
    total_cost2 = price2 * nights if price2 else 0
    
    # Determine winner in different categories
    cheaper = name1 if total_cost1 < total_cost2 else name2
    higher_rated = name1 if rating1 > rating2 else name2
    more_popular = name1 if reviews1 > reviews2 else name2
    
    # Calculate savings
    savings = abs(total_cost1 - total_cost2)
    
    # Find unique amenities
    amenities1_set = set(a.lower() for a in amenities1)
    amenities2_set = set(a.lower() for a in amenities2)
    
    unique_to_1 = amenities1_set - amenities2_set
    unique_to_2 = amenities2_set - amenities1_set
    common_amenities = amenities1_set & amenities2_set
    
    return {
        "hotel1": {
            "name": name1,
            "rating": rating1,
            "reviews": reviews1,
            "price_per_night": price1,
            "total_cost": total_cost1,
            "amenities": amenities1,
            "unique_amenities": list(unique_to_1)
        },
        "hotel2": {
            "name": name2,
            "rating": rating2,
            "reviews": reviews2,
            "price_per_night": price2,
            "total_cost": total_cost2,
            "amenities": amenities2,
            "unique_amenities": list(unique_to_2)
        },
        "comparison": {
            "cheaper_option": cheaper,
            "higher_rated": higher_rated,
            "more_popular": more_popular,
            "savings": savings,
            "common_amenities": list(common_amenities),
            "nights": nights
        },
        "recommendation": {
            "budget_choice": cheaper,
            "quality_choice": higher_rated,
            "popular_choice": more_popular
        }
    }


@tool
def get_hotel_recommendations(
    hotels: List[Dict[str, Any]], 
    user_preferences: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Get personalized hotel recommendations based on user preferences.
    
    Args:
        hotels: List of hotel properties
        user_preferences: Dictionary with user preferences (budget, amenities, location, etc.)
    
    Returns:
        List of recommended hotels with scores
    """
    if not hotels:
        return []
    
    budget_max = user_preferences.get("max_budget", float('inf'))
    min_rating = user_preferences.get("min_rating", 0)
    preferred_amenities = user_preferences.get("amenities", [])
    location_preference = user_preferences.get("location_type", "")
    
    scored_hotels = []
    
    for hotel in hotels:
        score = 0
        
        # Budget score (lower price = higher score)
        price = hotel.get("rate_per_night", {}).get("extracted_lowest", 0)
        if price and price <= budget_max:
            score += (budget_max - price) / budget_max * 30
        
        # Rating score
        rating = hotel.get("overall_rating", 0)
        if rating >= min_rating:
            score += rating * 20
        
        # Amenity score
        hotel_amenities = [a.lower() for a in hotel.get("amenities", [])]
        amenity_matches = sum(1 for pref in preferred_amenities 
                            if any(pref.lower() in amenity for amenity in hotel_amenities))
        score += amenity_matches * 10
        
        # Location score
        if location_preference:
            address = hotel.get("address", "").lower()
            nearby_places = hotel.get("nearby_places", [])
            if (location_preference.lower() in address or
                any(location_preference.lower() in place.get("name", "").lower() 
                    for place in nearby_places)):
                score += 15
        
        # Popularity score (more reviews = higher score)
        reviews = hotel.get("reviews", 0)
        score += min(reviews / 1000, 10)  # Cap at 10 points
        
        scored_hotels.append({
            **hotel,
            "recommendation_score": round(score, 2)
        })
    
    # Sort by recommendation score
    scored_hotels.sort(key=lambda x: x["recommendation_score"], reverse=True)
    
    return scored_hotels[:10]  # Return top 10 recommendations


@tool
def analyze_hotel_trends(
    hotels: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Analyze trends and patterns in hotel data.
    
    Args:
        hotels: List of hotel properties
    
    Returns:
        Analysis of hotel trends including price ranges, popular amenities, etc.
    """
    if not hotels:
        return {"error": "No hotels to analyze"}
    
    # Price analysis
    prices = [h.get("rate_per_night", {}).get("extracted_lowest", 0) 
              for h in hotels if h.get("rate_per_night", {}).get("extracted_lowest")]
    prices = [p for p in prices if p > 0]
    
    price_stats = {
        "min_price": min(prices) if prices else 0,
        "max_price": max(prices) if prices else 0,
        "avg_price": sum(prices) / len(prices) if prices else 0,
        "price_range": f"${min(prices):.2f} - ${max(prices):.2f}" if prices else "N/A"
    }
    
    # Rating analysis
    ratings = [h.get("overall_rating", 0) for h in hotels if h.get("overall_rating")]
    rating_stats = {
        "avg_rating": sum(ratings) / len(ratings) if ratings else 0,
        "highest_rated": max(ratings) if ratings else 0,
        "lowest_rated": min(ratings) if ratings else 0
    }
    
    # Amenity analysis
    all_amenities = []
    for hotel in hotels:
        all_amenities.extend(hotel.get("amenities", []))
    
    amenity_counts = {}
    for amenity in all_amenities:
        amenity_counts[amenity] = amenity_counts.get(amenity, 0) + 1
    
    popular_amenities = sorted(amenity_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Hotel class analysis
    classes = [h.get("hotel_class", 0) for h in hotels if h.get("hotel_class")]
    class_distribution = {}
    for cls in classes:
        class_distribution[f"{cls}-star"] = class_distribution.get(f"{cls}-star", 0) + 1
    
    return {
        "total_hotels": len(hotels),
        "price_analysis": price_stats,
        "rating_analysis": rating_stats,
        "popular_amenities": popular_amenities,
        "class_distribution": class_distribution,
        "analysis_date": datetime.now().isoformat()
    }
