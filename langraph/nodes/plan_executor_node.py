"""Plan Executor node that executes the multi-step plan."""

import sys
import os

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import AgentState


async def plan_executor_node(state: AgentState) -> AgentState:
    """Execute the current step of the execution plan.
    
    This node:
    1. Checks if there's an execution plan
    2. Gets the current step
    3. Routes to the agents in that step (parallel execution)
    4. Increments step counter for next iteration
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with routing for current step
    """
    execution_plan = state.get("execution_plan", [])
    current_step = state.get("current_step", 0)
    
    print(f"\n=== Plan Executor: Executing step {current_step + 1}/{len(execution_plan)} ===")
    
    # If no plan or completed all steps, route to join_node
    if not execution_plan or current_step >= len(execution_plan):
        print("Plan Executor: All steps completed, routing to join_node")
        return {
            "route": "join_node",
            "ready_for_response": True
        }
    
    # Get current step
    step = execution_plan[current_step]
    agents = step.get("agents", [])
    description = step.get("description", "")
    
    print(f"Plan Executor: Step {current_step + 1} - {description}")
    print(f"Plan Executor: Running agents in parallel: {agents}")
    
    # Increment step counter for next iteration
    updated_state = {
        "route": agents,  # List of agents to run in parallel
        "current_step": current_step + 1
    }
    
    return updated_state

