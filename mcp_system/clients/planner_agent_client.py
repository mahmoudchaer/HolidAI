"""Planner agent client for MCP."""

from clients.base_client import BaseAgentClient


PlannerAgentClient = BaseAgentClient(
    name="PlannerAgent",
    allowed_tools=[
        "agent_add_plan_item_tool",
        "agent_update_plan_item_tool",
        "agent_delete_plan_item_tool",
        "agent_get_plan_items_tool"
    ]
)

