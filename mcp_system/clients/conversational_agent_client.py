"""Conversational agent client for MCP."""

from clients.base_client import BaseAgentClient


ConversationalAgentClient = BaseAgentClient(
    name="ConversationalAgent",
    allowed_tools=[]
)

