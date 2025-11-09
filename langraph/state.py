"""Shared state definition for LangGraph orchestration."""

from typing import TypedDict, Dict, Any, Optional


class AgentState(TypedDict):
    """Shared state for LangGraph agents.
    
    Attributes:
        user_message: The current user message/query
        context: Additional context passed between agents
        route: Current routing decision ("main_agent" or "hotel_agent")
        last_response: Last response from an agent
    """
    user_message: str
    context: Dict[str, Any]
    route: str
    last_response: str

