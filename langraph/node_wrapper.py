"""Wrapper for LangGraph nodes to add enter/exit logging."""

import time
import functools
from agent_logger import log_node_enter, log_node_exit


def wrap_node(node_func, node_name: str):
    """Wrap a node function to add enter/exit logging.
    
    Args:
        node_func: The original node function
        node_name: Name of the node for logging
        
    Returns:
        Wrapped node function
    """
    @functools.wraps(node_func)
    async def wrapped_node(state):
        # Extract session_id and user_email from state
        session_id = state.get("session_id", "unknown")
        user_email = state.get("user_email")
        
        # Log node enter
        log_node_enter(session_id, user_email, node_name)
        
        # Execute node and measure latency
        start_time = time.time()
        try:
            result = await node_func(state)
            latency_ms = (time.time() - start_time) * 1000
            
            # Log node exit
            log_node_exit(session_id, user_email, node_name, latency_ms)
            
            return result
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            # Log exit even on error
            log_node_exit(session_id, user_email, node_name, latency_ms)
            raise
    
    return wrapped_node

