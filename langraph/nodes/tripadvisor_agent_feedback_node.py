"""Feedback validation node for TripAdvisor Agent."""

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


def get_tripadvisor_agent_feedback_prompt() -> str:
    """Get the system prompt for the TripAdvisor Agent Feedback Validator."""
    return """You are a TripAdvisor Agent Feedback Validator. Your job is simple: check if the TripAdvisor search results make logical sense given what the user asked for and what TripAdvisor typically returns.

VALIDATION APPROACH (BE LENIENT):
- Look at the user's request and the results returned
- Ask yourself: "Do these results make sense for what TripAdvisor would return for this query?"
- If the results are reasonable (even if some fields are missing), PASS
- Only retry if results are clearly wrong or completely empty without explanation

GENERAL RULES:
1. If results have names and seem relevant to the user's query → PASS
2. If results are empty but there's an error message explaining why → PASS
3. If results are completely wrong (e.g., user asked for restaurants but got hotels) → RETRY
4. If results are empty with no explanation → RETRY
5. Missing address/location fields are OK if names are present and results seem valid
6. Missing ratings are always OK
7. Missing type fields are always OK

BE GENEROUS - TripAdvisor results can vary in structure. If the results seem usable, pass them through.

Respond with JSON:
{
  "validation_status": "pass" | "need_retry",
  "feedback_message": "brief explanation"
}

Examples:

Example 1 - Results make sense (PASS):
User: "Find restaurants in Dubai"
Result: {"error": false, "data": [{"name": "Restaurant A"}, {"name": "Restaurant B"}]}
Response: {"validation_status": "pass", "feedback_message": "Results are valid restaurant names for Dubai"}

Example 2 - Results make sense even with minimal data (PASS):
User: "Find restaurants in Dubai"
Result: {"error": false, "data": [{"name": "Restaurant X"}]}
Response: {"validation_status": "pass", "feedback_message": "Results contain restaurant names, which is sufficient"}

Example 3 - Completely wrong results (RETRY):
User: "Find restaurants in Dubai"
Result: {"error": false, "data": [{"name": "Dubai Airport", "type": "airport"}]}
Response: {"validation_status": "need_retry", "feedback_message": "Results don't match query - got airports instead of restaurants"}

Example 4 - Empty with no explanation (RETRY):
User: "Find restaurants in Dubai"
Result: {"error": false, "data": []}
Response: {"validation_status": "need_retry", "feedback_message": "No results found without explanation"}

Example 5 - Error properly reported (PASS):
User: "Find restaurants in invalid-location"
Result: {"error": true, "error_message": "Location not found"}
Response: {"validation_status": "pass", "feedback_message": "Error properly handled"}"""


async def tripadvisor_agent_feedback_node(state: AgentState) -> AgentState:
    """TripAdvisor Agent feedback node that validates search results.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with validation results and routing decision
    """
    user_message = state.get("user_message", "")
    tripadvisor_result = state.get("tripadvisor_result", {})
    tripadvisor_feedback_retry_count = state.get("tripadvisor_feedback_retry_count", 0)
    
    print(f"\n=== TripAdvisor Agent Feedback Validator ===")
    
    # Check for infinite loops
    if tripadvisor_feedback_retry_count >= MAX_FEEDBACK_RETRIES:
        print(f"TripAdvisor Feedback: Max retries ({MAX_FEEDBACK_RETRIES}) reached, accepting results")
        return {
            "tripadvisor_feedback_retry_count": tripadvisor_feedback_retry_count + 1
        }
    
    # If no result, nothing to validate
    if not tripadvisor_result:
        print("TripAdvisor Feedback: No result to validate")
        return {}
    
    # Prepare simple validation context - just what the LLM needs to make a logical decision
    data_sample = []
    if tripadvisor_result.get("data"):
        # Show first 3-5 results with whatever fields they have
        for item in tripadvisor_result.get("data", [])[:5]:
            sample = {
                "name": item.get("name", ""),
                "address": item.get("address") or item.get("location", ""),
                "rating": item.get("rating"),  # Optional
                "type": item.get("type", "")  # Optional
            }
            # Only include non-empty fields
            sample = {k: v for k, v in sample.items() if v}
            if sample:  # Only add if there's at least name
                data_sample.append(sample)
    
    validation_context = {
        "user_request": user_message,
        "tripadvisor_result": {
            "has_error": tripadvisor_result.get("error", False),
            "error_message": tripadvisor_result.get("error_message", ""),
            "result_count": len(tripadvisor_result.get("data", [])),
            "sample_results": data_sample[:3],  # Just first 3 for context
            "search_type": tripadvisor_result.get("search_type", "")
        }
    }
    
    # Call LLM for validation - simple, agentic approach
    messages = [
        {"role": "system", "content": get_tripadvisor_agent_feedback_prompt()},
        {"role": "user", "content": f"""User asked: "{user_message}"

TripAdvisor returned:
{json.dumps(validation_context, indent=2)}

Do these results make logical sense? If yes, pass. Only retry if results are clearly wrong or empty without explanation."""}
    ]
    
    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            temperature=0.2,  # Lower temperature for more consistent decisions
            response_format={"type": "json_object"}
        )
        
        validation_result = json.loads(response.choices[0].message.content)
        status = validation_result.get("validation_status", "pass")
        feedback_msg = validation_result.get("feedback_message", "")
        suggested_action = validation_result.get("suggested_action", "")
        
        print(f"TripAdvisor Feedback: Status = {status}")
        print(f"TripAdvisor Feedback: {feedback_msg}")
        
        # Route based on validation status
        if status == "pass":
            # Results are valid, continue
            return {
                "tripadvisor_feedback_message": None,
                "tripadvisor_feedback_retry_count": 0
            }
            
        elif status == "need_retry":
            # Results are inadequate, retry search
            print(f"TripAdvisor Feedback: Requesting retry of search")
            full_feedback = f"{feedback_msg}\n\n{suggested_action}" if suggested_action else feedback_msg
            
            return {
                "tripadvisor_result": None,
                "tripadvisor_feedback_message": full_feedback,
                "tripadvisor_feedback_retry_count": tripadvisor_feedback_retry_count + 1
                # Note: Don't decrement current_step - retry routes directly to agent, not through plan_executor
            }
        
        else:
            # Unknown status, accept results
            print(f"TripAdvisor Feedback: Unknown status '{status}', accepting results")
            return {
                "tripadvisor_feedback_message": None,
                "tripadvisor_feedback_retry_count": tripadvisor_feedback_retry_count + 1
            }
            
    except Exception as e:
        print(f"TripAdvisor Feedback: Validation error - {e}, accepting results")
        return {
            "tripadvisor_feedback_message": None,
            "tripadvisor_feedback_retry_count": tripadvisor_feedback_retry_count + 1
        }

