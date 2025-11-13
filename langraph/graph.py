"""LangGraph orchestration for multi-agent travel system."""

from typing import Literal, Union, List
from langgraph.graph import StateGraph, END
from state import AgentState
from nodes.main_agent_node import main_agent_node
from nodes.visa_agent_node import visa_agent_node
from nodes.flight_agent_node import flight_agent_node
from nodes.hotel_agent_node import hotel_agent_node
from nodes.tripadvisor_agent_node import tripadvisor_agent_node
from nodes.conversational_agent_node import conversational_agent_node
from nodes.join_node import join_node


def route_decision(state: AgentState) -> Union[str, List[str], Literal["end"]]:
    """Route decision function based on state.route.
    
    Args:
        state: Current agent state
        
    Returns:
        Next node name(s) - can be a string, list of strings for parallel execution, or "end"
    """
    route = state.get("route", "main_agent")
    
    # If route is a list, return it for parallel execution
    if isinstance(route, list):
        return route
    
    # Handle string routes
    if route == "hotel_agent":
        return "hotel_agent"
    elif route == "visa_agent":
        return "visa_agent"
    elif route == "flight_agent":
        return "flight_agent"
    elif route == "tripadvisor_agent":
        return "tripadvisor_agent"
    elif route == "conversational_agent":
        return "conversational_agent"
    elif route == "join_node":
        return "join_node"
    elif route == "main_agent":
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
    graph.add_node("visa_agent", visa_agent_node)
    graph.add_node("flight_agent", flight_agent_node)
    graph.add_node("hotel_agent", hotel_agent_node)
    graph.add_node("tripadvisor_agent", tripadvisor_agent_node)
    graph.add_node("join_node", join_node)
    graph.add_node("conversational_agent", conversational_agent_node)
    
    # Set entry point
    graph.set_entry_point("main_agent")
    
    # Add conditional routing from main_agent
    # This handles both single routes and lists for parallel execution
    graph.add_conditional_edges(
        "main_agent",
        route_decision,
        {
            "main_agent": "main_agent",
            "hotel_agent": "hotel_agent",
            "visa_agent": "visa_agent",
            "flight_agent": "flight_agent",
            "tripadvisor_agent": "tripadvisor_agent",
            "conversational_agent": "conversational_agent",
            "join_node": "join_node",
            "end": END
        }
    )
    
    # All specialized agents return to join_node using add_edge
    # When multiple nodes use add_edge to route to the same target,
    # LangGraph automatically waits for all of them to complete and merges their state
    graph.add_edge("visa_agent", "join_node")
    graph.add_edge("flight_agent", "join_node")
    graph.add_edge("hotel_agent", "join_node")
    graph.add_edge("tripadvisor_agent", "join_node")
    
    # Join node routes to conversational agent when ready, or back to itself if waiting
    graph.add_conditional_edges(
        "join_node",
        route_decision,
        {
            "join_node": "join_node",  # Allow routing back to itself to wait for results
            "conversational_agent": "conversational_agent",
            "end": END
        }
    )
    
    # Conversational agent ends the workflow
    graph.add_conditional_edges(
        "conversational_agent",
        route_decision,
        {
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
        "last_response": "",
        "collected_info": {},
        "agents_called": [],
        "ready_for_response": False,
        "needs_flights": False,
        "needs_hotels": False,
        "needs_visa": False,
        "needs_tripadvisor": False,
        "flight_result": None,
        "hotel_result": None,
        "visa_result": None,
        "tripadvisor_result": None,
        "join_retry_count": 0
    }
    
    if config is None:
        config = {"recursion_limit": 100}  # Increased to accommodate join_node retries
    
    final_state = await app.ainvoke(initial_state, config)
    return final_state




