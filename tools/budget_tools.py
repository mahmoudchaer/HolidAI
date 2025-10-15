"""
Budget calculation and management tools.
"""

from typing import Dict, Any
from langchain_core.tools import tool


@tool
def calculate_total_budget(
    price_per_night: float,
    nights: int,
    extras: float = 0.0,
    tax_rate: float = 0.0
) -> Dict[str, float]:
    """
    Calculate the total budget for a hotel stay.
    
    Args:
        price_per_night: Price per night for the hotel
        nights: Number of nights staying
        extras: Additional costs (e.g., room service, tours)
        tax_rate: Tax rate as a decimal (e.g., 0.10 for 10%)
    
    Returns:
        Dictionary with budget breakdown
    """
    subtotal = price_per_night * nights
    taxes = subtotal * tax_rate
    total = subtotal + taxes + extras
    
    return {
        "price_per_night": round(price_per_night, 2),
        "nights": nights,
        "accommodation_subtotal": round(subtotal, 2),
        "taxes": round(taxes, 2),
        "extras": round(extras, 2),
        "total_budget": round(total, 2)
    }


@tool
def compare_hotel_costs(hotel1: Dict[str, Any], hotel2: Dict[str, Any], nights: int) -> Dict[str, Any]:
    """
    Compare the total costs of two hotels for a given number of nights.
    
    Args:
        hotel1: First hotel property
        hotel2: Second hotel property
        nights: Number of nights
    
    Returns:
        Comparison with savings information
    """
    price1 = hotel1.get("rate_per_night", {}).get("extracted_lowest", 0)
    price2 = hotel2.get("rate_per_night", {}).get("extracted_lowest", 0)
    
    total1 = price1 * nights
    total2 = price2 * nights
    
    cheaper = "hotel1" if total1 < total2 else "hotel2"
    savings = abs(total1 - total2)
    
    return {
        "hotel1_name": hotel1.get("name", "Hotel 1"),
        "hotel1_total": round(total1, 2),
        "hotel2_name": hotel2.get("name", "Hotel 2"),
        "hotel2_total": round(total2, 2),
        "cheaper_option": cheaper,
        "savings": round(savings, 2)
    }


@tool
def estimate_daily_expenses(
    meals_budget: float = 50.0,
    transport_budget: float = 20.0,
    activities_budget: float = 30.0
) -> Dict[str, float]:
    """
    Estimate daily expenses beyond accommodation.
    
    Args:
        meals_budget: Daily budget for meals
        transport_budget: Daily budget for transportation
        activities_budget: Daily budget for activities
    
    Returns:
        Daily expense breakdown
    """
    total_daily = meals_budget + transport_budget + activities_budget
    
    return {
        "meals": round(meals_budget, 2),
        "transport": round(transport_budget, 2),
        "activities": round(activities_budget, 2),
        "total_daily_expenses": round(total_daily, 2)
    }

