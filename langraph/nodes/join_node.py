"""Join node that waits for all required nodes in the current step to complete."""

import asyncio
import time
from datetime import datetime
from state import AgentState


async def join_node(state: AgentState) -> AgentState:
    """Join node that waits until all pending nodes for the current step complete.
    
    This node:
    1. Checks if all pending_nodes have completed (by checking if their results exist)
    2. When all nodes complete, marks the current step as finished
    3. Routes back to main_agent for next step decision
    
    Args:
        state: Current agent state (should have merged state from all parallel nodes)
        
    Returns:
        Updated agent state with route back to main_agent when step completes
    """
    updated_state = state.copy()
    
    # Get execution state
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    pending_nodes = state.get("pending_nodes", [])
    results = state.get("results", {})
    
    # If no plan exists, fall back to legacy behavior
    if not plan:
        # Legacy mode: check old result fields
        return await _legacy_join_node(state)
    
    # Check if we have a current step
    if current_step >= len(plan):
        # Plan complete, route to conversational agent
        updated_state["route"] = "conversational_agent"
        updated_state["ready_for_response"] = True
        return updated_state
    
    step = plan[current_step]
    step_id = step.get("id")
    step_nodes = step.get("nodes", [])
    
    # Determine which nodes we're waiting for
    nodes_to_wait_for = pending_nodes if pending_nodes else step_nodes
    
    if not nodes_to_wait_for:
        # No nodes to wait for, step is complete
        finished_steps = state.get("finished_steps", [])
        if step_id not in finished_steps:
            finished_steps.append(step_id)
        updated_state["finished_steps"] = finished_steps
        # CRITICAL FIX: Clear pending_nodes after step completes
        updated_state["pending_nodes"] = []
        if "_parallel_mode" in updated_state:
            del updated_state["_parallel_mode"]
        updated_state["route"] = "main_agent"
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] Join node: Step {step_id} complete, routing back to main agent")
        return updated_state
    
    # Check which nodes have completed
    # Each node should write its result to results[node_name] or results[node_name + "_result"]
    completed_nodes = []
    missing_nodes = []
    
    for node_name in nodes_to_wait_for:
        # Check multiple possible result keys
        result_keys = [
            node_name,  # e.g., "flight_agent"
            node_name.replace("_agent", ""),  # e.g., "flight"
            node_name.replace("_agent", "_result"),  # e.g., "flight_result"
            f"{node_name}_result"  # e.g., "flight_agent_result"
        ]
        
        found = False
        for key in result_keys:
            if key in results and results[key] is not None:
                completed_nodes.append(node_name)
                found = True
                break
        
        if not found:
            missing_nodes.append(node_name)
    
    # If all nodes completed, mark step as finished and route back to main agent
    if not missing_nodes:
        finished_steps = state.get("finished_steps", [])
        if step_id not in finished_steps:
            finished_steps.append(step_id)
        updated_state["finished_steps"] = finished_steps
        # CRITICAL FIX: Clear pending_nodes after step completes to prevent reuse
        updated_state["pending_nodes"] = []
        # Also clear the parallel mode flag
        if "_parallel_mode" in updated_state:
            del updated_state["_parallel_mode"]
        updated_state["route"] = "main_agent"
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] Join node: All nodes completed for step {step_id} (nodes: {completed_nodes}), routing back to main agent")
        return updated_state
    
    # Some nodes still missing, wait and retry
    join_retry_count = state.get("join_retry_count", 0)
    MAX_RETRIES = 20  # Maximum retries (10 seconds with 0.5s delay)
    
    if join_retry_count < MAX_RETRIES:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] Join node: Waiting for nodes {missing_nodes} to complete... (retry {join_retry_count + 1}/{MAX_RETRIES}, completed: {completed_nodes})")
        await asyncio.sleep(0.5)  # Wait for parallel nodes to complete
        updated_state["join_retry_count"] = join_retry_count + 1
        updated_state["route"] = "join_node"  # Route back to self to retry
        return updated_state
    else:
        print(f"Join node: Max retries reached. Proceeding with missing nodes: {missing_nodes}")
        # Mark step as finished anyway (with partial results)
        finished_steps = state.get("finished_steps", [])
        if step_id not in finished_steps:
            finished_steps.append(step_id)
        updated_state["finished_steps"] = finished_steps
        # CRITICAL FIX: Clear pending_nodes even on timeout
        updated_state["pending_nodes"] = []
        if "_parallel_mode" in updated_state:
            del updated_state["_parallel_mode"]
        updated_state["route"] = "main_agent"
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] Join node: Max retries reached. Proceeding with missing nodes: {missing_nodes}")
        return updated_state


async def _legacy_join_node(state: AgentState) -> AgentState:
    """Legacy join node behavior for backward compatibility."""
    updated_state = state.copy()
    
    # Check if all required results are present (legacy fields)
    needs_flights = state.get("needs_flights", False)
    needs_hotels = state.get("needs_hotels", False)
    needs_visa = state.get("needs_visa", False)
    needs_tripadvisor = state.get("needs_tripadvisor", False)
    needs_utilities = state.get("needs_utilities", False)
    
    flight_result = state.get("flight_result")
    hotel_result = state.get("hotel_result")
    visa_result = state.get("visa_result")
    tripadvisor_result = state.get("tripadvisor_result")
    utilities_result = state.get("utilities_result")
    
    missing_results = []
    
    if needs_flights and flight_result is None:
        missing_results.append("flights")
    if needs_hotels and hotel_result is None:
        missing_results.append("hotels")
    if needs_visa and visa_result is None:
        missing_results.append("visa")
    if needs_tripadvisor and tripadvisor_result is None:
        missing_results.append("tripadvisor")
    if needs_utilities and utilities_result is None:
        missing_results.append("utilities")
    
    if missing_results:
        join_retry_count = state.get("join_retry_count", 0)
        MAX_RETRIES = 20
        
        if join_retry_count < MAX_RETRIES:
            print(f"Join node (legacy): Missing results {missing_results}, waiting... (retry {join_retry_count + 1}/{MAX_RETRIES})")
            await asyncio.sleep(0.5)
            updated_state["join_retry_count"] = join_retry_count + 1
            updated_state["route"] = "join_node"
            return updated_state
        else:
            print(f"Join node (legacy): Max retries reached. Proceeding with missing results: {missing_results}")
    
    # Collect all available results
    collected_info = {}
    if flight_result is not None:
        collected_info["flight_result"] = flight_result
    if hotel_result is not None:
        collected_info["hotel_result"] = hotel_result
    if visa_result is not None:
        collected_info["visa_result"] = visa_result
    if tripadvisor_result is not None:
        collected_info["tripadvisor_result"] = tripadvisor_result
    if utilities_result is not None:
        collected_info["utilities_result"] = utilities_result
    
    # Add error indicators for missing results
    if missing_results:
        for missing in missing_results:
            if missing == "flights" and "flight_result" not in collected_info:
                collected_info["flight_result"] = {"error": True, "error_message": "Flight search did not complete"}
            elif missing == "hotels" and "hotel_result" not in collected_info:
                collected_info["hotel_result"] = {"error": True, "error_message": "Hotel search did not complete"}
            elif missing == "visa" and "visa_result" not in collected_info:
                collected_info["visa_result"] = {"error": True, "error_message": "Visa check did not complete"}
            elif missing == "tripadvisor" and "tripadvisor_result" not in collected_info:
                collected_info["tripadvisor_result"] = {"error": True, "error_message": "TripAdvisor search did not complete"}
            elif missing == "utilities" and "utilities_result" not in collected_info:
                collected_info["utilities_result"] = {"error": True, "error_message": "Utilities query did not complete"}
    
    updated_state["collected_info"] = collected_info
    updated_state["route"] = "conversational_agent"
    updated_state["ready_for_response"] = True
    
    return updated_state
