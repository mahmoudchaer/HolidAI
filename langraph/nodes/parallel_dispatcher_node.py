"""Parallel dispatcher node that enables parallel execution of multiple worker nodes."""

from datetime import datetime
from state import AgentState


async def parallel_dispatcher_node(state: AgentState) -> AgentState:
    """Parallel dispatcher that sets up state for parallel execution.
    
    This node doesn't directly execute nodes in parallel, but sets up the state
    so that LangGraph can route to multiple nodes simultaneously through
    multiple edges defined in the graph.
    
    Args:
        state: Current agent state with route set to a list of node names
        
    Returns:
        Updated state that will trigger parallel execution through graph edges
    """
    route = state.get("route", [])
    pending_nodes = state.get("pending_nodes", [])
    
    # CRITICAL FIX: Prioritize route over pending_nodes
    # route is the fresh value from main_agent for the current step
    # pending_nodes might be stale from a previous step
    # Only use pending_nodes if route is not a list (fallback)
    if isinstance(route, list) and len(route) > 0:
        nodes_to_execute = route
    elif isinstance(pending_nodes, list) and len(pending_nodes) > 0:
        nodes_to_execute = pending_nodes
    else:
        nodes_to_execute = []
    
    if not isinstance(nodes_to_execute, list):
        # Fallback: if route is a string, convert to list
        nodes_to_execute = [nodes_to_execute] if nodes_to_execute else []
    
    updated_state = state.copy()
    updated_state["pending_nodes"] = nodes_to_execute.copy()
    
    # Mark that we're in parallel execution mode
    # The graph edges will handle routing to all nodes in parallel
    updated_state["_parallel_mode"] = True
    
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] Parallel dispatcher: Setting up {len(nodes_to_execute)} nodes for parallel execution: {nodes_to_execute}")
    
    # Don't set route - the graph edges from parallel_dispatcher to worker nodes
    # will handle the routing. LangGraph executes all edges in parallel.
    # Each worker node will check pending_nodes and execute if needed.
    
    return updated_state

