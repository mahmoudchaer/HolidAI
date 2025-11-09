"""Main agent client for MCP."""

from clients.base_client import BaseAgentClient


MainAgentClient = BaseAgentClient(
    name="MainAgent",
    allowed_tools=["delegate"],
    server_url="http://localhost:8090"
)

