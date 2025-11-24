"""Feedback validation node for Plan Executor."""

import sys
import os
import json
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import AgentState

# Load environment variables
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MAX_FEEDBACK_RETRIES = 2


def get_plan_executor_feedback_prompt() -> str:
    """Get the system prompt for the Plan Executor Feedback Validator."""
    return """You are a Plan Executor Feedback Validator that verifies execution plan structure and feasibility.

Your role:
- Validate that the execution plan is properly structured
- Ensure each step has valid agents assigned
- Check that step dependencies make sense
- Verify that the plan can be executed sequentially

Available agents to validate:
- flight_agent: Searches for flights
- hotel_agent: Searches for hotels
- visa_agent: Checks visa requirements
- tripadvisor_agent: Searches locations, attractions, restaurants
- utilities_agent: Handles weather, currency, eSIM, holidays, date/time
- planner_agent: Manages travel plan items (add/update/delete flights, hotels, activities)

VALIDATION RULES:

1. Structure validation:
   - Each step must have a step_number
   - Each step must have an agents array with at least one valid agent
   - Each step must have a description

2. Agent validation:
   - All agent names must be from the available agents list
   - No duplicate or unknown agents in a step

3. Sequence validation:
   - Step numbers should be sequential (1, 2, 3, ...)
   - Dependencies should be logical (later steps can depend on earlier steps)

4. Common issues to catch:
   - Empty agents array in a step
   - Invalid agent names
   - Non-sequential step numbers
   - Missing required fields

Respond with JSON:
{
  "validation_status": "pass" | "need_fix",
  "feedback_message": "explanation of issue (if any)",
  "suggested_fix": "how to fix the plan (if needed)"
}

Examples:

Example 1 - Valid plan (PASS):
Plan:
  Step 1: [flight_agent, hotel_agent] - Search for travel options
  Step 2: [utilities_agent] - Convert prices to AED
Response: {
  "validation_status": "pass",
  "feedback_message": "Plan structure is valid and executable"
}

Example 2 - Invalid agent (FIX):
Plan:
  Step 1: [invalid_agent] - Do something
Response: {
  "validation_status": "need_fix",
  "feedback_message": "Step 1 contains invalid agent 'invalid_agent'",
  "suggested_fix": "Replace 'invalid_agent' with a valid agent from the available list"
}

Example 3 - Empty agents (FIX):
Plan:
  Step 1: [] - Search for flights
Response: {
  "validation_status": "need_fix",
  "feedback_message": "Step 1 has no agents assigned",
  "suggested_fix": "Add at least one agent to Step 1 based on the description"
}"""


async def plan_executor_feedback_node(state: AgentState) -> AgentState:
    """Plan Executor feedback node that validates execution plan structure.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with validation results and routing decision
    """
    execution_plan = state.get("execution_plan", [])
    plan_executor_retry_count = state.get("plan_executor_retry_count", 0)
    
    print(f"\n=== Plan Executor Feedback Validator ===")
    
    # Check for infinite loops
    if plan_executor_retry_count >= MAX_FEEDBACK_RETRIES:
        print(f"Plan Executor Feedback: Max retries ({MAX_FEEDBACK_RETRIES}) reached, proceeding anyway")
        return {
            "route": "plan_executor",
            "plan_executor_retry_count": plan_executor_retry_count + 1
        }
    
    # If no plan, nothing to validate - proceed
    if not execution_plan:
        print("Plan Executor Feedback: No execution plan to validate, proceeding")
        return {
            "route": "plan_executor"
        }
    
    # Prepare validation context
    validation_context = {
        "execution_plan": [
            {
                "step": step.get("step_number"),
                "agents": step.get("agents"),
                "description": step.get("description")
            }
            for step in execution_plan
        ]
    }
    
    # Call LLM for validation
    messages = [
        {"role": "system", "content": get_plan_executor_feedback_prompt()},
        {"role": "user", "content": f"Validate this execution plan structure:\n\n{json.dumps(validation_context, indent=2)}"}
    ]
    
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        validation_result = json.loads(response.choices[0].message.content)
        status = validation_result.get("validation_status", "pass")
        feedback_msg = validation_result.get("feedback_message", "")
        suggested_fix = validation_result.get("suggested_fix", "")
        
        print(f"Plan Executor Feedback: Status = {status}")
        print(f"Plan Executor Feedback: {feedback_msg}")
        
        # Route based on validation status
        if status == "pass":
            # Plan structure is valid, proceed to execution
            return {
                "route": "plan_executor",
                "plan_executor_feedback_message": None,
                "plan_executor_retry_count": 0
            }
            
        elif status == "need_fix":
            # Plan structure is invalid, send back to main agent
            print(f"Plan Executor Feedback: Sending back to main agent for fix")
            full_feedback = f"{feedback_msg}\n\nSuggested fix: {suggested_fix}" if suggested_fix else feedback_msg
            return {
                "route": "main_agent",
                "plan_executor_feedback_message": full_feedback,
                "execution_plan": [],  # Clear invalid plan
                "plan_executor_retry_count": plan_executor_retry_count + 1
            }
        
        else:
            # Unknown status, proceed with caution
            print(f"Plan Executor Feedback: Unknown status '{status}', proceeding")
            return {
                "route": "plan_executor",
                "plan_executor_feedback_message": None,
                "plan_executor_retry_count": plan_executor_retry_count + 1
            }
            
    except Exception as e:
        print(f"Plan Executor Feedback: Validation error - {e}, proceeding")
        # On error, proceed to avoid blocking
        return {
            "route": "plan_executor",
            "plan_executor_feedback_message": None,
            "plan_executor_retry_count": plan_executor_retry_count + 1
        }

