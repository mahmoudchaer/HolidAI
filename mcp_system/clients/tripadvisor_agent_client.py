"""TripAdvisor agent client for MCP."""

from clients.base_client import BaseAgentClient


TripAdvisorAgentClient = BaseAgentClient(
    name="TripAdvisorAgent",
    allowed_tools=[
        "search_locations",
        "get_location_reviews",
        "get_location_photos",
        "get_location_details",
        "search_nearby",
        "search_locations_by_rating",
        "search_nearby_by_rating",
        "get_top_rated_locations",
        "search_locations_by_price",
        "search_nearby_by_price",
        "search_nearby_by_distance",
        "find_closest_location",
        "search_restaurants_by_cuisine",
        "get_multiple_location_details",
        "compare_locations"
    ]
)

