"""Shared state definition for LangGraph orchestration."""

from typing import TypedDict, Dict, Any, Optional, List, Annotated


def reducer(left: Any, right: Any) -> Any:
    """Reducer function for merging state updates.
    
    For parallel nodes updating different fields, we want to preserve non-None values.
    If left is None, use right. If right is None, use left. Otherwise, use right (latest).
    This ensures that when parallel nodes update different result fields, both are preserved.
    """
    # If right is None, keep left (preserve existing value)
    if right is None:
        return left
    # Otherwise, use right (latest value)
    return right


class ExecutionStep(TypedDict):
    """A single step in the execution plan.
    
    Attributes:
        step_number: The order of this step (1-indexed)
        agents: List of agent node names to call in parallel
        description: Human-readable description of what this step does
        depends_on: Optional list of step numbers this step depends on
    """
    step_number: int
    agents: List[str]
    description: str
    depends_on: Optional[List[int]]


class AgentState(TypedDict):
    """Shared state for LangGraph agents.
    
    Attributes:
        user_message: The original user message/query (read-only, never updated in parallel)
        context: Additional context passed between agents
        route: Current routing decision (can be a list for parallel execution)
        last_response: Last response from an agent
        collected_info: Information collected from specialized agents
        agents_called: List of agents that have been called
        ready_for_response: Whether we have enough info to generate final response
        needs_flights: Whether flight information is needed
        needs_hotels: Whether hotel information is needed
        needs_visa: Whether visa information is needed
        needs_tripadvisor: Whether TripAdvisor information is needed
        needs_utilities: Whether utilities information is needed (weather, currency, date/time)
        flight_result: Flight search results (set by flight_agent_node) - can be updated in parallel
        hotel_result: Hotel search results (set by hotel_agent_node) - can be updated in parallel
        visa_result: Visa requirement results (set by visa_agent_node) - can be updated in parallel
        tripadvisor_result: TripAdvisor results (set by tripadvisor_agent_node) - can be updated in parallel
        utilities_result: Utilities results (set by utilities_agent_node) - can be updated in parallel
        join_retry_count: Counter for join_node retries to prevent infinite loops
        execution_plan: List of execution steps to run sequentially
        current_step: Current step number being executed (0-indexed into execution_plan)
        feedback_message: Feedback message from main agent validation (for plan logic issues)
        feedback_retry_count: Counter for main agent feedback retries to prevent infinite loops
        plan_executor_feedback_message: Feedback for plan executor validation
        plan_executor_retry_count: Counter for plan executor feedback retries
        flight_feedback_message: Feedback for flight agent validation
        flight_feedback_retry_count: Counter for flight agent feedback retries
        hotel_feedback_message: Feedback for hotel agent validation
        hotel_feedback_retry_count: Counter for hotel agent feedback retries
        visa_feedback_message: Feedback for visa agent validation
        visa_feedback_retry_count: Counter for visa agent feedback retries
        tripadvisor_feedback_message: Feedback for tripadvisor agent validation
        tripadvisor_feedback_retry_count: Counter for tripadvisor agent feedback retries
        utilities_feedback_message: Feedback for utilities agent validation
        utilities_feedback_retry_count: Counter for utilities agent feedback retries
        conversational_feedback_message: Feedback for conversational agent validation
        conversational_feedback_retry_count: Counter for conversational agent feedback retries
        rfi_status: RFI validation status (complete, missing_info, unsafe, out_of_scope, error)
        rfi_context: Context for RFI follow-up questions
        rfi_missing_fields: List of missing fields identified by RFI
        rfi_question: Question to ask user when info is missing
        rfi_filtered_message: Message about filtered non-travel parts (if any)
        rfi_ignored_parts: List of non-travel parts that were filtered out
        needs_user_input: Flag indicating we're waiting for user input
        travel_plan_items: List of travel plan items retrieved from database
        planner_feedback_message: Feedback for planner validation
        planner_feedback_retry_count: Counter for planner feedback retries
        needs_planner: Whether planner operations are needed
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
    execution_plan: Annotated[List[Dict[str, Any]], reducer]  # List of ExecutionStep dicts
    current_step: Annotated[int, reducer]  # Current step being executed
    feedback_message: Annotated[Optional[str], reducer]  # Feedback from main agent validation
    feedback_retry_count: Annotated[int, reducer]  # Counter for main agent feedback retries
    plan_executor_feedback_message: Annotated[Optional[str], reducer]  # Feedback for plan executor
    plan_executor_retry_count: Annotated[int, reducer]  # Counter for plan executor feedback retries
    flight_feedback_message: Annotated[Optional[str], reducer]  # Feedback for flight agent
    flight_feedback_retry_count: Annotated[int, reducer]  # Counter for flight agent feedback retries
    hotel_feedback_message: Annotated[Optional[str], reducer]  # Feedback for hotel agent
    hotel_feedback_retry_count: Annotated[int, reducer]  # Counter for hotel agent feedback retries
    visa_feedback_message: Annotated[Optional[str], reducer]  # Feedback for visa agent
    visa_feedback_retry_count: Annotated[int, reducer]  # Counter for visa agent feedback retries
    tripadvisor_feedback_message: Annotated[Optional[str], reducer]  # Feedback for tripadvisor agent
    tripadvisor_feedback_retry_count: Annotated[int, reducer]  # Counter for tripadvisor agent feedback retries
    utilities_feedback_message: Annotated[Optional[str], reducer]  # Feedback for utilities agent
    utilities_feedback_retry_count: Annotated[int, reducer]  # Counter for utilities agent feedback retries
    conversational_feedback_message: Annotated[Optional[str], reducer]  # Feedback for conversational agent
    conversational_feedback_retry_count: Annotated[int, reducer]  # Counter for conversational agent feedback retries
    rfi_status: Annotated[Optional[str], reducer]  # RFI validation status
    rfi_context: Annotated[Optional[str], reducer]  # Context for RFI follow-up questions
    rfi_missing_fields: Annotated[Optional[List[str]], reducer]  # Missing fields identified by RFI
    rfi_question: Annotated[Optional[str], reducer]  # Question to ask user when info is missing
    rfi_filtered_message: Annotated[Optional[str], reducer]  # Message about filtered non-travel parts
    rfi_ignored_parts: Annotated[Optional[List[str]], reducer]  # Non-travel parts that were filtered out
    needs_user_input: Annotated[bool, reducer]  # Flag indicating we're waiting for user input
    user_email: Annotated[Optional[str], reducer]  # User's email for memory storage
    relevant_memories: Annotated[Optional[List[str]], reducer]  # Relevant memories retrieved for this query
    session_id: Annotated[Optional[str], reducer]  # Session ID for STM access
    travel_plan_items: Annotated[Optional[List[Dict[str, Any]]], reducer]  # Travel plan items from database
    planner_feedback_message: Annotated[Optional[str], reducer]  # Feedback for planner validation
    planner_feedback_retry_count: Annotated[int, reducer]  # Counter for planner feedback retries
    needs_planner: Annotated[bool, reducer]  # Whether planner operations are needed

