"""LangGraph orchestration for multi-agent travel system."""

from typing import Literal
from langgraph.graph import StateGraph, END
from state import AgentState
from nodes.main_agent_node import main_agent_node
from nodes.visa_agent_node import visa_agent_node
from nodes.flight_agent_node import flight_agent_node
from nodes.hotel_agent_node import hotel_agent_node
from nodes.tripadvisor_agent_node import tripadvisor_agent_node
from nodes.conversational_agent_node import conversational_agent_node


def route_decision(state: AgentState) -> Literal["main_agent", "hotel_agent", "visa_agent", "flight_agent", "tripadvisor_agent", "conversational_agent", "end"]:
    """Route decision function based on state.route.
    
    Args:
        state: Current agent state
        
    Returns:
        Next node name or END
    """
    route = state.get("route", "main_agent")
    
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
    graph.add_node("conversational_agent", conversational_agent_node)
    
    # Set entry point
    graph.set_entry_point("main_agent")
    
    # Add conditional routing from main_agent
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
            "end": END
        }
    )
    
    # All specialized agents return to main_agent
    graph.add_conditional_edges(
        "visa_agent",
        route_decision,
        {
            "main_agent": "main_agent",
            "end": END
        }
    )
    
    graph.add_conditional_edges(
        "flight_agent",
        route_decision,
        {
            "main_agent": "main_agent",
            "end": END
        }
    )
    
    graph.add_conditional_edges(
        "hotel_agent",
        route_decision,
        {
            "main_agent": "main_agent",
            "end": END
        }
    )
    
    graph.add_conditional_edges(
        "tripadvisor_agent",
        route_decision,
        {
            "main_agent": "main_agent",
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
        "ready_for_response": False
    }
    
    if config is None:
        config = {"recursion_limit": 50}
    
    final_state = await app.ainvoke(initial_state, config)
    return final_state




