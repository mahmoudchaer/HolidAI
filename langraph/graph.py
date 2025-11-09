"""LangGraph orchestration for multi-agent travel system."""

import os
from typing import Literal
from langgraph.graph import StateGraph, END
from state import AgentState
from nodes.main_agent_node import main_agent_node


def route_decision(state: AgentState) -> Literal["main_agent", "hotel_agent", "end"]:
    """Route decision function based on state.route.
    
    Args:
        state: Current agent state
        
    Returns:
        Next node name or END
    """
    route = state.get("route", "main_agent")
    
    if route == "hotel_agent":
        return "hotel_agent"
    elif route == "main_agent":
        # If we have a response, end the workflow
        if state.get("last_response"):
            return "end"
        return "main_agent"
    else:
        return "end"


def create_graph() -> StateGraph:
    """Create and configure the LangGraph.
    
    Returns:
        Configured StateGraph instance
    """
    # Create the graph
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("main_agent", main_agent_node)
    
    # Set entry point
    graph.set_entry_point("main_agent")
    
    # Add conditional routing from main_agent
    graph.add_conditional_edges(
        "main_agent",
        route_decision,
        {
            "main_agent": "main_agent",
            "hotel_agent": "hotel_agent",
            "end": END
        }
    )
    
    return graph.compile()


# Create the graph instance
app = create_graph()


async def run(user_message: str, config: dict = None) -> dict:
    """Run the LangGraph with a user message.
    
    Args:
        user_message: The user's message/query
        config: Optional runtime configuration
        
    Returns:
        Final state dictionary
    """
    initial_state = {
        "user_message": user_message,
        "context": {},
        "route": "main_agent",
        "last_response": ""
    }
    
    if config is None:
        config = {"recursion_limit": 50}
    
    final_state = await app.ainvoke(initial_state, config)
    return final_state

