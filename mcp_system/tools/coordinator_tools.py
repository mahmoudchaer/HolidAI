"""Coordinator tools for agent orchestration."""

from typing import Dict, Any
from tools.doc_loader import get_doc


def register_coordinator_tools(mcp):
    """Register coordinator tools with the MCP server."""
    
    @mcp.tool(description=get_doc("delegate", "coordinator"))
    def delegate(agent: str, task: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate a task to a specialized agent.
        
        Args:
            agent: The target agent name (e.g., "hotel_agent")
            task: The task to perform (e.g., "get_hotel_rates")
            args: Arguments to pass to the agent
        
        Returns:
            Dictionary with delegation info:
            {
                "status": "delegated",
                "agent": agent,
                "task": task,
                "args": args
            }
        """
        return {
            "status": "delegated",
            "agent": agent,
            "task": task,
            "args": args
        }

