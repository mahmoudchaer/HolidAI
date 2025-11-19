"""Hotel agent client for MCP."""

from clients.base_client import BaseAgentClient


HotelAgentClient = BaseAgentClient(
    name="HotelAgent",
    allowed_tools=["get_list_of_hotels", "get_hotel_rates", "get_hotel_rates_by_price", "get_hotel_details"]
)

