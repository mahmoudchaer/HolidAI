"""LangGraph orchestration for multi-agent travel system."""

from typing import Literal, Union, List
from langgraph.graph import StateGraph, END
from state import AgentState
from nodes.rfi_node import rfi_node
from nodes.main_agent_node import main_agent_node
from nodes.feedback_node import feedback_node
from nodes.plan_executor_node import plan_executor_node
from nodes.plan_executor_feedback_node import plan_executor_feedback_node
from nodes.visa_agent_node import visa_agent_node
from nodes.visa_agent_feedback_node import visa_agent_feedback_node
from nodes.flight_agent_node import flight_agent_node
from nodes.flight_agent_feedback_node import flight_agent_feedback_node
from nodes.hotel_agent_node import hotel_agent_node
from nodes.hotel_agent_feedback_node import hotel_agent_feedback_node
from nodes.tripadvisor_agent_node import tripadvisor_agent_node
from nodes.tripadvisor_agent_feedback_node import tripadvisor_agent_feedback_node
from nodes.utilities_agent_node import utilities_agent_node
from nodes.utilities_agent_feedback_node import utilities_agent_feedback_node
from nodes.conversational_agent_node import conversational_agent_node
from nodes.conversational_agent_feedback_node import conversational_agent_feedback_node
from nodes.join_node import join_node
from nodes.memory_agent_node import memory_agent_node
from nodes.trip_planner_node import trip_planner_node
from nodes.trip_planner_feedback_node import trip_planner_feedback_node


def route_decision(state: AgentState) -> Union[str, List[str], Literal["end"]]:
    """Route decision function based on state.route.
    
    Args:
        state: Current agent state
        
    Returns:
        Next node name(s) - can be a string, list of strings for parallel execution, or "end"
    """
    route = state.get("route", "rfi_node")
    
    # If route is a list, return it for parallel execution
    if isinstance(route, list):
        return route
    
    # Handle string routes
    if route == "memory_agent":
        return "memory_agent"
    elif route == "rfi_node":
        return "rfi_node"
    elif route == "feedback":
        return "feedback"
    elif route == "plan_executor_feedback":
        return "plan_executor_feedback"
    elif route == "plan_executor":
        return "plan_executor"
    elif route == "hotel_agent":
        return "hotel_agent"
    elif route == "visa_agent":
        return "visa_agent"
    elif route == "flight_agent":
        return "flight_agent"
    elif route == "tripadvisor_agent":
        return "tripadvisor_agent"
    elif route == "utilities_agent":
        return "utilities_agent"
    elif route == "conversational_agent":
        return "conversational_agent"
    elif route == "join_node":
        return "join_node"
    elif route == "main_agent":
        return "main_agent"
    elif route == "trip_planner":
        return "trip_planner"
    elif route == "trip_planner_feedback":
        return "trip_planner_feedback"
    elif route == "conversational_agent_feedback":
        return "conversational_agent_feedback"
    else:
        return "end"


def create_graph() -> StateGraph:
    """Create and configure the LangGraph.
    
    Returns:
        Configured StateGraph instance
    """
    # Create the graph
    graph = StateGraph(AgentState)
    
    # Add nodes - main workflow nodes
    graph.add_node("memory_agent", memory_agent_node)  # Memory agent - handles memory retrieval and storage FIRST
    graph.add_node("rfi_node", rfi_node)  # RFI node - validates logical completeness
    graph.add_node("main_agent", main_agent_node)
    graph.add_node("feedback", feedback_node)
    graph.add_node("plan_executor", plan_executor_node)
    graph.add_node("plan_executor_feedback", plan_executor_feedback_node)
    graph.add_node("visa_agent", visa_agent_node)
    graph.add_node("visa_agent_feedback", visa_agent_feedback_node)
    graph.add_node("flight_agent", flight_agent_node)
    graph.add_node("flight_agent_feedback", flight_agent_feedback_node)
    graph.add_node("hotel_agent", hotel_agent_node)
    graph.add_node("hotel_agent_feedback", hotel_agent_feedback_node)
    graph.add_node("tripadvisor_agent", tripadvisor_agent_node)
    graph.add_node("tripadvisor_agent_feedback", tripadvisor_agent_feedback_node)
    graph.add_node("utilities_agent", utilities_agent_node)
    graph.add_node("utilities_agent_feedback", utilities_agent_feedback_node)
    graph.add_node("join_node", join_node)
    graph.add_node("conversational_agent", conversational_agent_node)
    graph.add_node("conversational_agent_feedback", conversational_agent_feedback_node)
    graph.add_node("trip_planner", trip_planner_node)
    graph.add_node("trip_planner_feedback", trip_planner_feedback_node)
    
    # Set entry point - Memory agent runs first!
    graph.set_entry_point("memory_agent")
    
    # Memory agent always routes to RFI node
    graph.add_edge("memory_agent", "rfi_node")
    
    # RFI node routes based on validation result
    graph.add_conditional_edges(
        "rfi_node",
        route_decision,
        {
            "main_agent": "main_agent",
            "conversational_agent": "conversational_agent",
            "trip_planner": "trip_planner",
            "end": END
        }
    )
    
    # Trip planner routes to its feedback node
    graph.add_edge("trip_planner", "trip_planner_feedback")
    
    # Trip planner feedback routes to conversational_agent_feedback for final validation
    graph.add_conditional_edges(
        "trip_planner_feedback",
        route_decision,
        {
            "conversational_agent_feedback": "conversational_agent_feedback",
            "end": END
        }
    )
    
    # Main agent routes to feedback for validation or conversational agent for simple queries
    graph.add_conditional_edges(
        "main_agent",
        route_decision,
        {
            "feedback": "feedback",
            "plan_executor": "plan_executor",  # Only if no agents needed
            "conversational_agent": "conversational_agent",
            "end": END
        }
    )
    
    # Main agent feedback node routes based on validation result
    graph.add_conditional_edges(
        "feedback",
        route_decision,
        {
            "plan_executor_feedback": "plan_executor_feedback",  # validation passed, check plan executor next
            "main_agent": "main_agent",  # plan needs fixing
            "end": END
        }
    )
    
    # Plan executor feedback validates the execution plan structure before execution
    graph.add_conditional_edges(
        "plan_executor_feedback",
        route_decision,
        {
            "plan_executor": "plan_executor",  # structure valid, execute
            "main_agent": "main_agent",  # structure invalid, regenerate plan
            "end": END
        }
    )
    
    # Plan executor routes to agents (parallel execution) or join_node when done
    graph.add_conditional_edges(
        "plan_executor",
        route_decision,
        {
            "plan_executor": "plan_executor",
            "hotel_agent": "hotel_agent",
            "visa_agent": "visa_agent",
            "flight_agent": "flight_agent",
            "tripadvisor_agent": "tripadvisor_agent",
            "utilities_agent": "utilities_agent",
            "join_node": "join_node",
            "end": END
        }
    )
    
    # Each specialized agent routes to its feedback node for validation
    # Flight agent → flight feedback
    graph.add_edge("flight_agent", "flight_agent_feedback")
    graph.add_conditional_edges(
        "flight_agent_feedback",
        lambda state: "flight_agent" if state.get("flight_feedback_message") and state.get("flight_feedback_retry_count", 0) < 2 else "plan_executor",
        {
            "flight_agent": "flight_agent",  # retry if feedback says so
            "plan_executor": "plan_executor"  # continue if passed
        }
    )
    
    # Hotel agent → hotel feedback
    graph.add_edge("hotel_agent", "hotel_agent_feedback")
    graph.add_conditional_edges(
        "hotel_agent_feedback",
        lambda state: "hotel_agent" if state.get("hotel_feedback_message") and state.get("hotel_feedback_retry_count", 0) < 2 else "plan_executor",
        {
            "hotel_agent": "hotel_agent",  # retry if feedback says so
            "plan_executor": "plan_executor"  # continue if passed
        }
    )
    
    # Visa agent → visa feedback
    graph.add_edge("visa_agent", "visa_agent_feedback")
    graph.add_conditional_edges(
        "visa_agent_feedback",
        lambda state: "visa_agent" if state.get("visa_feedback_message") and state.get("visa_feedback_retry_count", 0) < 2 else "plan_executor",
        {
            "visa_agent": "visa_agent",  # retry if feedback says so
            "plan_executor": "plan_executor"  # continue if passed
        }
    )
    
    # TripAdvisor agent → tripadvisor feedback
    graph.add_edge("tripadvisor_agent", "tripadvisor_agent_feedback")
    graph.add_conditional_edges(
        "tripadvisor_agent_feedback",
        lambda state: "tripadvisor_agent" if state.get("tripadvisor_feedback_message") and state.get("tripadvisor_feedback_retry_count", 0) < 2 else "plan_executor",
        {
            "tripadvisor_agent": "tripadvisor_agent",  # retry if feedback says so
            "plan_executor": "plan_executor"  # continue if passed
        }
    )
    
    # Utilities agent → utilities feedback
    graph.add_edge("utilities_agent", "utilities_agent_feedback")
    graph.add_conditional_edges(
        "utilities_agent_feedback",
        lambda state: "utilities_agent" if state.get("utilities_feedback_message") and state.get("utilities_feedback_retry_count", 0) < 2 else "plan_executor",
        {
            "utilities_agent": "utilities_agent",  # retry if feedback says so
            "plan_executor": "plan_executor"  # continue if passed
        }
    )
    
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
    
    # Conversational agent routes to its feedback for validation
    graph.add_edge("conversational_agent", "conversational_agent_feedback")
    
    # Conversational feedback validates the final response
    graph.add_conditional_edges(
        "conversational_agent_feedback",
        route_decision,
        {
            "conversational_agent": "conversational_agent",  # regenerate if needed
            "end": END  # end if passed
        }
    )
    
    return graph.compile()


# Create the graph instance
app = create_graph()


async def run(user_message: str, config: dict = None, user_email: str = None, session_id: str = None) -> dict:
    """Run the LangGraph with a user message.
    
    Args:
        user_message: The user's message/query
        config: Optional runtime configuration
        user_email: User's email for memory operations (handled by memory_agent)
        session_id: Session ID for STM access
        
    Returns:
        Final state dictionary
    """
    initial_state = {
        "user_message": user_message,
        "context": {},
        "route": "memory_agent",  # Start with Memory agent to retrieve/store memories
        "last_response": "",
        "collected_info": {},
        "agents_called": [],
        "ready_for_response": False,
        "needs_flights": False,
        "needs_hotels": False,
        "needs_visa": False,
        "needs_tripadvisor": False,
        "needs_utilities": False,
        "flight_result": None,
        "hotel_result": None,
        "visa_result": None,
        "tripadvisor_result": None,
        "utilities_result": None,
        "feedback_message": None,
        "feedback_retry_count": 0,
        "plan_executor_feedback_message": None,
        "plan_executor_retry_count": 0,
        "flight_feedback_message": None,
        "flight_feedback_retry_count": 0,
        "hotel_feedback_message": None,
        "hotel_feedback_retry_count": 0,
        "visa_feedback_message": None,
        "visa_feedback_retry_count": 0,
        "tripadvisor_feedback_message": None,
        "tripadvisor_feedback_retry_count": 0,
        "utilities_feedback_message": None,
        "utilities_feedback_retry_count": 0,
        "conversational_feedback_message": None,
        "conversational_feedback_retry_count": 0,
        "join_retry_count": 0,
        "execution_plan": [],
        "current_step": 0,
        "rfi_status": None,
        "rfi_context": "",
        "rfi_missing_fields": None,
        "rfi_question": None,
        "rfi_filtered_message": None,
        "rfi_ignored_parts": None,
        "needs_user_input": False,
        "user_email": user_email,
        "relevant_memories": [],  # Will be populated by memory_agent
        "session_id": session_id,  # Session ID for STM access
        "trip_planner_result": None  # Result from trip_planner node
    }
    
    if config is None:
        config = {"recursion_limit": 100}  # Increased to accommodate join_node retries and multi-step execution
    
    final_state = await app.ainvoke(initial_state, config)
    return final_state




