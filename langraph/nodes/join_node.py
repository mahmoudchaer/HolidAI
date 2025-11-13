"""Join node that waits for all required agent results before proceeding."""

from state import AgentState


async def join_node(state: AgentState) -> AgentState:
    """Join node that waits until all required results are present.
    
    In LangGraph, when multiple parallel nodes route to the same target node,
    LangGraph merges their state updates before calling the target node.
    However, if a node routes to join_node before all parallel nodes finish,
    we need to wait. This node should only proceed when all required results are present.
    
    Args:
        state: Current agent state (should have merged state from all parallel nodes)
        
    Returns:
        Updated agent state with route to conversational_agent when ready
    """
    import asyncio
    updated_state = state.copy()
    
    # Check if all required results are present
    needs_flights = state.get("needs_flights", False)
    needs_hotels = state.get("needs_hotels", False)
    needs_visa = state.get("needs_visa", False)
    needs_tripadvisor = state.get("needs_tripadvisor", False)
    
    # Get actual result values
    flight_result = state.get("flight_result")
    hotel_result = state.get("hotel_result")
    visa_result = state.get("visa_result")
    tripadvisor_result = state.get("tripadvisor_result")
    
    # Debug: Print actual state values
    print(f"Join node: Checking state - needs_flights={needs_flights}, needs_hotels={needs_hotels}, needs_visa={needs_visa}, needs_tripadvisor={needs_tripadvisor}")
    print(f"Join node: Results present - flight_result={'present' if flight_result is not None else 'None'}, hotel_result={'present' if hotel_result is not None else 'None'}, visa_result={'present' if visa_result is not None else 'None'}, tripadvisor_result={'present' if tripadvisor_result is not None else 'None'}")
    if hotel_result is not None:
        hotels_count = len(hotel_result.get("hotels", [])) if isinstance(hotel_result, dict) else 0
        print(f"Join node: hotel_result details - hotels count: {hotels_count}, error: {hotel_result.get('error', 'N/A') if isinstance(hotel_result, dict) else 'N/A'}")
    
    # Check which results are still missing
    missing_results = []
    
    if needs_flights and flight_result is None:
        missing_results.append("flights")
    
    if needs_hotels and hotel_result is None:
        missing_results.append("hotels")
    
    if needs_visa and visa_result is None:
        missing_results.append("visa")
    
    if needs_tripadvisor and tripadvisor_result is None:
        missing_results.append("tripadvisor")
    
    # Even with add_edge, join_node might be called before all parallel nodes complete
    # We need to wait and retry if results are missing
    # The issue is that when tripadvisor_agent finishes first, it routes to join_node,
    # but hotel_agent might still be running, so the state doesn't have hotel_result yet
    if missing_results:
        join_retry_count = state.get("join_retry_count", 0)
        MAX_RETRIES = 20  # Maximum retries (10 seconds with 0.5s delay)
        
        if join_retry_count < MAX_RETRIES:
            print(f"Join node: Missing results {missing_results}, waiting for parallel nodes to complete... (retry {join_retry_count + 1}/{MAX_RETRIES})")
            # Print full state for debugging
            print(f"Join node: Full state keys: {list(state.keys())}")
            print(f"Join node: State values - hotel_result type: {type(state.get('hotel_result'))}, tripadvisor_result type: {type(state.get('tripadvisor_result'))}")
            await asyncio.sleep(0.5)  # Wait for parallel nodes to complete
            updated_state["join_retry_count"] = join_retry_count + 1
            updated_state["route"] = "join_node"
            return updated_state
        else:
            print(f"Join node: Max retries reached. Proceeding with missing results: {missing_results}")
    
    # Collect all available results into collected_info for conversational agent
    # Include results even if they have errors - the conversational agent can handle them
    collected_info = {}
    if state.get("flight_result") is not None:
        collected_info["flight_result"] = state.get("flight_result")
    if state.get("hotel_result") is not None:
        hotel_result = state.get("hotel_result")
        collected_info["hotel_result"] = hotel_result
        # Debug: Log hotel result status
        if isinstance(hotel_result, dict):
            hotels_count = len(hotel_result.get("hotels", []))
            has_error = hotel_result.get("error", False)
            print(f"Join node: Hotel result has {hotels_count} hotel(s), error: {has_error}")
    if state.get("visa_result") is not None:
        collected_info["visa_result"] = state.get("visa_result")
    if state.get("tripadvisor_result") is not None:
        collected_info["tripadvisor_result"] = state.get("tripadvisor_result")
    
    # If some results are missing (None), add error indicators
    # Only add error if the result is actually None (not present), not if it exists but has an error flag
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
    
    updated_state["collected_info"] = collected_info
    updated_state["route"] = "conversational_agent"
    updated_state["ready_for_response"] = True
    
    return updated_state

