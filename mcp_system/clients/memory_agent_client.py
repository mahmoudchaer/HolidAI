"""Memory agent client for MCP."""

from clients.base_client import BaseAgentClient


MemoryAgentClient = BaseAgentClient(
    name="MemoryAgent",
    allowed_tools=[
        "agent_analyze_memory_tool",
        "agent_store_memory_tool",
        "agent_update_memory_tool",
        "agent_delete_memory_tool",
        "agent_get_relevant_memories_tool"
    ]
)

