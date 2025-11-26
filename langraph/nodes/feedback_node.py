"""Feedback validation node for LangGraph orchestration."""

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


def get_feedback_prompt() -> str:
    """Get the system prompt for the Feedback Validator."""
    return """You are a Feedback Validator that checks if execution plans are LOGICAL before execution.

Your ONLY role:
- Validate that the execution plan makes logical sense
- Check if dependencies are respected
- Determine if we should proceed or fix the plan

DO NOT check for missing user information - each agent will handle that themselves.

Available agents:
- flight_agent: Searches for flights
- hotel_agent: Searches for hotels or gets hotel details
- visa_agent: Checks visa requirements
- tripadvisor_agent: Searches for locations, attractions, restaurants
- utilities_agent: Handles holidays, weather, currency, eSIM, date/time

VALIDATION RULES (PLAN LOGIC ONLY):

1. Dependency validation:
   - If user wants to AVOID holidays → holidays MUST be fetched BEFORE booking
   - If currency conversion is needed → it must come AFTER getting the prices
   - If booking depends on finding a city → city search must come first

2. Tool sequencing:
   - utilities_agent can call multiple tools in one step (holidays + eSIM together)
   - Independent tasks can run in parallel (eSIM doesn't depend on booking)
   - Dependent tasks must be sequential

3. Common illogical patterns to catch:
   - User says "avoid holidays" but no holiday check before booking
   - User wants currency conversion but no source data in earlier steps
   - Plan has circular dependencies

Respond with JSON:
{
  "validation_status": "pass" | "need_plan_fix",
  "feedback_message": "explanation of issue (if any)"
}

Examples:

Example 1 - Good plan (PASS):
User: "Find hotels in Paris"
Plan: Step 1: [hotel_agent]
Response: {
  "validation_status": "pass",
  "feedback_message": "Plan is valid - simple hotel search"
}

Example 2 - Illogical plan (FIX):
User: "Find hotels in Paris avoiding holidays"
Plan: Step 1: [hotel_agent] - No holiday check!
Response: {
  "validation_status": "need_plan_fix",
  "feedback_message": "User wants to avoid holidays but plan doesn't fetch holidays before booking. Add utilities_agent with get_holidays in Step 1 before hotel_agent."
}

Example 3 - Good dependency (PASS):
User: "Get flight prices and convert to AED"
Plan:
  Step 1: [flight_agent]
  Step 2: [utilities_agent] - convert to AED
Response: {
  "validation_status": "pass",
  "feedback_message": "Plan respects dependencies - gets prices before conversion"
}

Example 4 - Missing dependency (FIX):
User: "Convert hotel prices to AED"
Plan: Step 1: [utilities_agent] - convert to AED (no hotel search!)
Response: {
  "validation_status": "need_plan_fix",
  "feedback_message": "Cannot convert hotel prices without first getting hotel data. Add hotel_agent in Step 1 before conversion."
}

Focus ONLY on plan logic, not missing user parameters."""


async def feedback_node(state: AgentState) -> AgentState:
    """Feedback validation node that checks execution plan validity.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with validation results and routing decision
    """
    user_message = state.get("user_message", "")
    execution_plan = state.get("execution_plan", [])
    feedback_retry_count = state.get("feedback_retry_count", 0)
    
    print(f"\n=== Feedback Validator ===")
    
    # Check for infinite loops
    if feedback_retry_count >= MAX_FEEDBACK_RETRIES:
        print(f"Feedback: Max retries ({MAX_FEEDBACK_RETRIES}) reached, proceeding anyway")
        return {
            "route": "plan_executor_feedback",
            "validation_passed": True,
            "feedback_retry_count": feedback_retry_count + 1
        }
    
    # Prepare validation context
    validation_context = {
        "user_query": user_message,
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
        {"role": "system", "content": get_feedback_prompt()},
        {"role": "user", "content": f"Validate this execution plan:\n\n{json.dumps(validation_context, indent=2)}"}
    ]
    
    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        validation_result = json.loads(response.choices[0].message.content)
        status = validation_result.get("validation_status", "pass")
        feedback_msg = validation_result.get("feedback_message", "")
        
        print(f"Feedback: Status = {status}")
        print(f"Feedback: {feedback_msg}")
        
        # Route based on validation status
        if status == "pass":
            # Plan logic is valid, proceed to plan executor feedback for structure validation
            return {
                "route": "plan_executor_feedback",
                "feedback_message": None,
                "feedback_retry_count": 0
            }
            
        elif status == "need_plan_fix":
            # Plan is illogical, send back to main agent with feedback
            print(f"Feedback: Sending back to main agent for plan fix")
            return {
                "route": "main_agent",
                "feedback_message": feedback_msg,
                "execution_plan": [],  # Clear invalid plan
                "feedback_retry_count": feedback_retry_count + 1
            }
        
        else:
            # Unknown status, proceed with caution
            print(f"Feedback: Unknown status '{status}', proceeding to plan executor feedback")
            return {
                "route": "plan_executor_feedback",
                "feedback_message": None,
                "feedback_retry_count": feedback_retry_count + 1
            }
            
    except Exception as e:
        print(f"Feedback: Validation error - {e}, proceeding to plan executor feedback")
        # On error, proceed to avoid blocking
        return {
            "route": "plan_executor_feedback",
            "validation_passed": True,
            "feedback_message": None,
            "feedback_retry_count": feedback_retry_count + 1
        }

