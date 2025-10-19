"""
Enhanced hotel presentation and formatting tools.
Creates clean, user-friendly hotel displays.
"""

from typing import List, Dict, Any
from langchain_core.tools import tool


@tool
def format_hotel_cards(hotels: List[Dict[str, Any]], max_hotels: int = 5) -> str:
    """
    Format hotels as clean, card-style presentations.
    
    Args:
        hotels: List of hotel properties
        max_hotels: Maximum number of hotels to display
    
    Returns:
        Clean formatted string with hotel cards
    """
    if not hotels:
        return "😔 **No hotels found matching your criteria.**\n\nTry adjusting your search parameters or dates!"
    
    # Limit to max_hotels
    hotels = hotels[:max_hotels]
    
    result = f"🎉 **Great! I found {len(hotels)} amazing hotel{'s' if len(hotels) > 1 else ''} for you:**\n\n"
    
    for i, hotel in enumerate(hotels, 1):
        name = hotel.get("name", "Unknown Hotel")
        rating = hotel.get("overall_rating", 0)
        reviews = hotel.get("reviews", 0)
        hotel_class = hotel.get("hotel_class", 0)
        rate = hotel.get("rate_per_night", {})
        price = rate.get("lowest", "N/A")
        amenities = hotel.get("amenities", [])[:4]  # Show more amenities
        
        # Format amenities with emojis
        amenity_emojis = {
            "Free Wi-Fi": "📶",
            "Pool": "🏊‍♀️",
            "Gym": "💪",
            "Spa": "🧘‍♀️",
            "Parking": "🅿️",
            "Restaurant": "🍽️",
            "Bar": "🍸",
            "Breakfast": "🍳",
            "Air conditioning": "❄️",
            "Hot tub": "🛁",
            "Outdoor pool": "🏊‍♀️",
            "Fitness center": "💪",
            "Free parking": "🅿️",
            "Free Wi-Fi": "📶"
        }
        
        amenity_text = ""
        for amenity in amenities:
            emoji = amenity_emojis.get(amenity, "✨")
            amenity_text += f"{emoji} {amenity}  "
        
        if not amenity_text:
            amenity_text = "✨ Standard amenities"
        
        # Format reviews count
        reviews_text = f"{reviews:,}" if reviews > 0 else "No reviews"
        
        # Create hotel card with better formatting
        result += f"🏨 **{i}. {name}**\n"
        result += f"   ⭐ **{rating}/5** ({reviews_text}) • **{hotel_class}-star luxury**\n"
        result += f"   💰 **${price}** per night\n"
        result += f"   ✨ **Key Features:** {amenity_text.strip()}\n\n"
    
    result += "\n💡 **Need help choosing?** I can help you:\n"
    result += "• Compare specific hotels\n"
    result += "• Filter by price range\n"
    result += "• Find hotels near attractions\n"
    result += "• Book your favorite option\n\n"
    result += "Just let me know what you'd like to do next! 😊"
    
    return result


@tool
def format_hotel_comparison(hotels: List[Dict[str, Any]], max_hotels: int = 3) -> str:
    """
    Format hotels in a comparison table style.
    
    Args:
        hotels: List of hotel properties
        max_hotels: Maximum number of hotels to compare
    
    Returns:
        Clean formatted comparison string
    """
    if not hotels:
        return "❌ No hotels found for comparison."
    
    hotels = hotels[:max_hotels]
    
    result = f"📊 **Hotel Comparison ({len(hotels)} hotels):**\n\n"
    
    # Header
    result += "| Hotel | Rating | Price | Stars | Top Amenities |\n"
    result += "|-------|--------|-------|-------|---------------|\n"
    
    for hotel in hotels:
        name = hotel.get("name", "Unknown")[:20] + "..." if len(hotel.get("name", "")) > 20 else hotel.get("name", "Unknown")
        rating = hotel.get("overall_rating", 0)
        rate = hotel.get("rate_per_night", {})
        price = rate.get("lowest", "N/A")
        hotel_class = hotel.get("hotel_class", 0)
        amenities = hotel.get("amenities", [])[:2]
        
        amenity_text = ", ".join(amenities) if amenities else "Standard"
        
        result += f"| {name} | {rating}/5 | {price} | {hotel_class}⭐ | {amenity_text} |\n"
    
    return result


@tool
def format_hotel_highlights(hotels: List[Dict[str, Any]], max_hotels: int = 5) -> str:
    """
    Format hotels with key highlights and recommendations.
    
    Args:
        hotels: List of hotel properties
        max_hotels: Maximum number of hotels to display
    
    Returns:
        Clean formatted string with highlights
    """
    if not hotels:
        return "❌ No hotels found matching your criteria."
    
    hotels = hotels[:max_hotels]
    
    result = f"🌟 **Top {len(hotels)} Hotel Recommendations:**\n\n"
    
    for i, hotel in enumerate(hotels, 1):
        name = hotel.get("name", "Unknown Hotel")
        rating = hotel.get("overall_rating", 0)
        reviews = hotel.get("reviews", 0)
        hotel_class = hotel.get("hotel_class", 0)
        rate = hotel.get("rate_per_night", {})
        price = rate.get("lowest", "N/A")
        
        # Determine highlight based on rating and price
        if rating >= 4.5:
            highlight = "🔥 Highly Rated"
        elif hotel_class >= 5:
            highlight = "⭐ Luxury"
        elif price and "$" in str(price) and any(char.isdigit() for char in str(price)):
            # Try to extract numeric price for comparison
            try:
                price_num = float(str(price).replace("$", "").replace(",", ""))
                if price_num < 150:
                    highlight = "💰 Great Value"
                else:
                    highlight = "🏨 Premium"
            except:
                highlight = "🏨 Quality"
        else:
            highlight = "🏨 Quality"
        
        # Format reviews
        reviews_text = f"{reviews:,}" if reviews > 0 else "New"
        
        result += f"**{i}. {name}** {highlight}\n"
        result += f"   ⭐ {rating}/5 ({reviews_text} reviews) • {hotel_class}-star • {price}/night\n\n"
    
    return result.strip()


@tool
def format_budget_summary(hotels: List[Dict[str, Any]], nights: int = 1) -> str:
    """
    Format hotels with budget information and total costs.
    
    Args:
        hotels: List of hotel properties
        nights: Number of nights for cost calculation
    
    Returns:
        Clean formatted string with budget information
    """
    if not hotels:
        return "❌ No hotels found for budget analysis."
    
    hotels = hotels[:5]  # Limit to 5 hotels
    
    result = f"💰 **Budget Analysis for {nights} night{'s' if nights > 1 else ''}:**\n\n"
    
    for i, hotel in enumerate(hotels, 1):
        name = hotel.get("name", "Unknown Hotel")
        rate = hotel.get("rate_per_night", {})
        price = rate.get("lowest", "N/A")
        rating = hotel.get("overall_rating", 0)
        
        # Calculate total cost if possible
        total_cost = "N/A"
        if price and "$" in str(price):
            try:
                price_num = float(str(price).replace("$", "").replace(",", ""))
                total_cost = f"${price_num * nights:,.2f}"
            except:
                pass
        
        result += f"**{i}. {name}**\n"
        result += f"   💵 {price}/night → {total_cost} total\n"
        result += f"   ⭐ {rating}/5 rating\n\n"
    
    return result.strip()
