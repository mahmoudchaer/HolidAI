"""Shared state definition for LangGraph orchestration."""

from typing import TypedDict, Dict, Any, Optional, List


class AgentState(TypedDict):
    """Shared state for LangGraph agents.
    
    Attributes:
        user_message: The original user message/query
        context: Additional context passed between agents
        route: Current routing decision
        last_response: Last response from an agent
        collected_info: Information collected from specialized agents
        agents_called: List of agents that have been called
        ready_for_response: Whether we have enough info to generate final response
    """
    user_message: str
    context: Dict[str, Any]
    route: str
    last_response: str
    collected_info: Dict[str, Any]
    agents_called: List[str]
    ready_for_response: bool

