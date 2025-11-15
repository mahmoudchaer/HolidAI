"""Utilities agent client for MCP."""

from clients.base_client import BaseAgentClient


UtilitiesAgentClient = BaseAgentClient(
    name="UtilitiesAgent",
    allowed_tools=["get_real_time_weather", "convert_currencies", "get_real_time_date_time", "get_esim_bundles", "get_holidays"]
)

