"""Visa agent client for MCP."""

from clients.base_client import BaseAgentClient


VisaAgentClient = BaseAgentClient(
    name="VisaAgent",
    allowed_tools=["get_traveldoc_requirement_tool"]
)

