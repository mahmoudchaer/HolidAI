"""Shared state definition for LangGraph orchestration."""

from typing import TypedDict, Dict, Any, Optional, List, Annotated


def reducer(left: Any, right: Any) -> Any:
    """Reducer function for merging state updates.
    
    For parallel nodes updating different fields, we want to preserve non-None values.
    If left is None, use right. If right is None, use left. Otherwise, use right (latest).
    This ensures that when parallel nodes update different result fields, both are preserved.
    
    Special handling for:
    - results: Merge dictionaries (both left and right results are preserved)
    - finished_steps: Merge lists and remove duplicates
    - user_questions: Merge lists and remove duplicates
    - pending_nodes: REPLACE entirely (not merge) - this is set by main_agent/parallel_dispatcher
    """
    # If right is None, keep left (preserve existing value)
    if right is None:
        return left
    
    # Special handling for dictionary results - merge them
    if isinstance(left, dict) and isinstance(right, dict):
        merged = left.copy()
        merged.update(right)
        return merged
    
    # Special handling for list fields - merge and deduplicate
    # BUT: pending_nodes should be replaced, not merged (it's set by orchestrator)
    if isinstance(left, list) and isinstance(right, list):
        merged = list(left)
        for item in right:
            if item not in merged:
                merged.append(item)
        return merged
    
    # Otherwise, use right (latest value)
    return right


def pending_nodes_reducer(left: Any, right: Any) -> Any:
    """Special reducer for pending_nodes that REPLACES instead of merging.
    
    pending_nodes should always be replaced entirely, not merged, because:
    - It's set by main_agent for each step
    - It's cleared by join_node when step completes
    - Merging would cause stale values to persist across steps
    """
    # Always use right (latest value) - replace entirely
    # If right is None or empty list, that's intentional (clearing)
    return right


class AgentState(TypedDict):
    """Shared state for LangGraph agents with dynamic multi-step planning.
    
    Attributes:
        user_message: The original user message/query (read-only, never updated in parallel)
        context: Additional context passed between agents
        route: Current routing decision (can be a list for parallel execution)
        last_response: Last response from an agent
        collected_info: Information collected from specialized agents (legacy, kept for compatibility)
        agents_called: List of agents that have been called (legacy, kept for compatibility)
        ready_for_response: Whether we have enough info to generate final response
        needs_flights: Whether flight information is needed (legacy, kept for compatibility)
        needs_hotels: Whether hotel information is needed (legacy, kept for compatibility)
        needs_visa: Whether visa information is needed (legacy, kept for compatibility)
        needs_tripadvisor: Whether TripAdvisor information is needed (legacy, kept for compatibility)
        needs_utilities: Whether utilities information is needed (legacy, kept for compatibility)
        flight_result: Flight search results (legacy, kept for compatibility)
        hotel_result: Hotel search results (legacy, kept for compatibility)
        visa_result: Visa requirement results (legacy, kept for compatibility)
        tripadvisor_result: TripAdvisor results (legacy, kept for compatibility)
        utilities_result: Utilities results (legacy, kept for compatibility)
        join_retry_count: Counter for join_node retries to prevent infinite loops
        
        # New execution state fields for dynamic multi-step planning
        plan: List of execution plan steps, each with id, nodes, requires, produces
        current_step: Current step index in the plan
        results: Dictionary storing results from all executed nodes (keyed by node name or result key)
        pending_nodes: List of node names that are currently executing for the current step
        finished_steps: List of step IDs that have been completed
        user_questions: List of questions to ask the user (if any)
    """
    user_message: Annotated[str, reducer]  # Read-only, but needs reducer for parallel execution
    context: Annotated[Dict[str, Any], reducer]
    route: Annotated[Any, reducer]  # Can be str or List[str] for parallel execution
    last_response: Annotated[str, reducer]
    collected_info: Annotated[Dict[str, Any], reducer]
    agents_called: Annotated[List[str], reducer]
    ready_for_response: Annotated[bool, reducer]
    needs_flights: Annotated[bool, reducer]
    needs_hotels: Annotated[bool, reducer]
    needs_visa: Annotated[bool, reducer]
    needs_tripadvisor: Annotated[bool, reducer]
    needs_utilities: Annotated[bool, reducer]
    flight_result: Annotated[Optional[Dict[str, Any]], reducer]
    hotel_result: Annotated[Optional[Dict[str, Any]], reducer]
    visa_result: Annotated[Optional[Dict[str, Any]], reducer]
    tripadvisor_result: Annotated[Optional[Dict[str, Any]], reducer]
    utilities_result: Annotated[Optional[Dict[str, Any]], reducer]
    join_retry_count: Annotated[int, reducer]
    
    # New execution state fields
    plan: Annotated[List[Dict[str, Any]], reducer]  # List of plan steps
    current_step: Annotated[int, reducer]  # Current step index
    results: Annotated[Dict[str, Any], reducer]  # Results dictionary
    pending_nodes: Annotated[List[str], pending_nodes_reducer]  # Nodes currently executing (REPLACE, don't merge)
    finished_steps: Annotated[List[int], reducer]  # Completed step IDs
    user_questions: Annotated[List[str], reducer]  # Questions to ask user

