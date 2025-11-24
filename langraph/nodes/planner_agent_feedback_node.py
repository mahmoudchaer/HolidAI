"""Feedback validation node for Planner Agent."""

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


def get_planner_agent_feedback_prompt() -> str:
    """Get the system prompt for the Planner Agent Feedback Validator."""
    return """You are a Planner Agent Feedback Validator that ensures planner operations were executed correctly.

Your role:
- Validate that planner operations (add, update, delete, retrieve) were properly executed
- Check if the user's intent was correctly understood and fulfilled
- Verify that the correct items were selected from available results
- Ensure operations align with what the user requested

VALIDATION RULES:

1. Intent Understanding:
   - Did the agent correctly identify the user's intent (add/update/delete/view)?
   - Was the correct tool called for the operation?

2. Item Selection:
   - If user said "option 2", was the 2nd item from the relevant result array selected?
   - If user said "hotel X" or "flight Y", was the correct item identified?
   - Are the extracted details complete and accurate?

3. Operation Execution:
   - Was the tool call successful?
   - Were all required parameters provided (title, details, type, etc.)?
   - Is the title descriptive and meaningful?

4. User Satisfaction:
   - Does the operation match what the user requested?
   - Would the user be satisfied with this result?

Respond with JSON:
{
  "validation_status": "pass" | "need_retry",
  "feedback_message": "explanation of issue (if any)",
  "suggested_action": "what should be done to fix (if needed)"
}

Examples:

Example 1 - Valid add operation (PASS):
User: "I want option 2"
Result: Successfully added flight option 2 with complete details
Response: {
  "validation_status": "pass",
  "feedback_message": "Planner operation completed successfully - option 2 was correctly identified and added"
}

Example 2 - Missing details (RETRY):
User: "Save hotel option 1"
Result: Added hotel but details are incomplete (missing price, dates)
Response: {
  "validation_status": "need_retry",
  "feedback_message": "Hotel was added but details are incomplete. Missing critical information like price or dates.",
  "suggested_action": "Retry with complete hotel details extracted from the hotel_result"
}

Example 3 - Wrong item selected (RETRY):
User: "I want option 2"
Result: Added option 1 instead of option 2
Response: {
  "validation_status": "need_retry",
  "feedback_message": "Incorrect item selected - user requested option 2 but option 1 was added",
  "suggested_action": "Retry and select the correct item (option 2) from the results"
}

Example 4 - No operation performed when needed (RETRY):
User: "Save this flight"
Result: No tool was called, no operation performed
Response: {
  "validation_status": "need_retry",
  "feedback_message": "User requested to save a flight but no planner operation was performed",
  "suggested_action": "Call agent_add_plan_item_tool to save the flight"
}"""


async def planner_agent_feedback_node(state: AgentState) -> AgentState:
    """Planner Agent feedback node that validates planner operations.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with validation results and routing decision
    """
    user_message = state.get("user_message", "")
    needs_planner = state.get("needs_planner", False)
    planner_feedback_retry_count = state.get("planner_feedback_retry_count", 0)
    last_response = state.get("last_response", "")
    travel_plan_items = state.get("travel_plan_items", [])
    
    print(f"\n=== Planner Agent Feedback Validator ===")
    
    # If planner wasn't needed, skip validation
    if not needs_planner:
        print("Planner Feedback: No planner operations needed, skipping validation")
        return {
            "planner_feedback_message": None,
            "planner_feedback_retry_count": 0,
            "route": "conversational_agent"
        }
    
    # Check for infinite loops
    if planner_feedback_retry_count >= MAX_FEEDBACK_RETRIES:
        print(f"Planner Feedback: Max retries ({MAX_FEEDBACK_RETRIES}) reached, accepting results")
        return {
            "planner_feedback_retry_count": planner_feedback_retry_count + 1,
            "route": "conversational_agent"
        }
    
    # Prepare validation context
    validation_context = {
        "user_request": user_message,
        "planner_summary": last_response,
        "current_plan_items_count": len(travel_plan_items),
        "operation_performed": bool(last_response)
    }
    
    # Call LLM for validation
    messages = [
        {"role": "system", "content": get_planner_agent_feedback_prompt()},
        {"role": "user", "content": f"Validate this planner operation:\n\n{json.dumps(validation_context, indent=2)}"}
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
        suggested_action = validation_result.get("suggested_action", "")
        
        print(f"Planner Feedback: Status = {status}")
        print(f"Planner Feedback: {feedback_msg}")
        
        # Route based on validation status
        if status == "pass":
            # Operations are valid, continue to conversational agent
            return {
                "planner_feedback_message": None,
                "planner_feedback_retry_count": 0,
                "route": "conversational_agent"
            }
            
        elif status == "need_retry":
            # Operations are inadequate, retry planner
            print(f"Planner Feedback: Requesting retry of planner operation")
            full_feedback = f"{feedback_msg}\n\n{suggested_action}" if suggested_action else feedback_msg
            
            return {
                "planner_feedback_message": full_feedback,
                "planner_feedback_retry_count": planner_feedback_retry_count + 1,
                "route": "planner_agent"  # Retry planner
            }
        
        else:
            # Unknown status, accept results
            print(f"Planner Feedback: Unknown status '{status}', accepting results")
            return {
                "planner_feedback_message": None,
                "planner_feedback_retry_count": planner_feedback_retry_count + 1,
                "route": "conversational_agent"
            }
            
    except Exception as e:
        print(f"Planner Feedback: Validation error - {e}, accepting results")
        # On error, accept results to avoid blocking
        return {
            "planner_feedback_message": None,
            "planner_feedback_retry_count": planner_feedback_retry_count + 1,
            "route": "conversational_agent"
        }

