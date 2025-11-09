"""TripAdvisor agent client for MCP."""

from clients.base_client import BaseAgentClient


TripAdvisorAgentClient = BaseAgentClient(
    name="TripAdvisorAgent",
    allowed_tools=[
        "search_locations",
        "get_location_reviews",
        "get_location_photos",
        "get_location_details",
        "search_nearby"
    ]
)

