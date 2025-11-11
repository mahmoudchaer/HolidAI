"""Flight agent client for MCP."""

from clients.base_client import BaseAgentClient


FlightAgentClient = BaseAgentClient(
    name="FlightAgent",
    allowed_tools=["agent_get_flights_tool", "agent_get_flights_flexible_tool"]
)

