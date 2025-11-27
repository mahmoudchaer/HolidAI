"""Feedback validation node for Flight Agent."""

import sys
import os
import json
import time
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from agent_logger import log_llm_call, log_feedback_failure

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


def get_flight_agent_feedback_prompt() -> str:
    """Get the system prompt for the Flight Agent Feedback Validator."""
    return """You are a Flight Agent Feedback Validator that ensures flight search results meet quality standards.

Your role:
- Validate that flight search was properly executed
- Check if results contain necessary information
- Verify that any errors are legitimate and properly handled
- Ensure results align with user's request
- **IMPORTANT**: Understand tool limitations and user's actual request before judging

CRITICAL - CONTEXT AWARENESS:
- If user did NOT provide dates → empty flight results are EXPECTED (tool requires dates)
- If user asked general question → empty results are OK
- ONLY flag as error if user provided complete info but got empty results
- Check if the user actually requested flights with enough details

VALIDATION RULES:

1. User Request Analysis (CHECK THIS FIRST):
   - Did user provide origin/destination?
   - Did user provide travel dates?
   - If dates missing → empty results are ACCEPTABLE (tool needs dates)
   - If only partial info → empty results are ACCEPTABLE

2. Result structure validation:
   - If error=true, check error_code:
     * VALIDATION_ERROR → ALWAYS retry (parameters need correction)
     * Other error codes → may be acceptable depending on context
   - If error=true, must have error_message explaining the issue
   - If error=false AND user provided dates, should have flight data
   - Flight data should include: airline, price, times, route

3. Data quality checks (ONLY if flights returned):
   - Flights should have valid prices (not null/undefined)
   - Routes should match the requested departure/arrival
   - Dates should be reasonable

4. Error legitimacy:
   - **CRITICAL**: If error_code is "VALIDATION_ERROR" → ALWAYS retry (this means parameters were wrong)
   - Valid: no flights found for those dates, invalid dates, API timeout
   - Valid: empty results if user didn't provide dates
   - Invalid: error with complete user input for no reason
   - **VALIDATION_ERROR examples**: Invalid trip_type (e.g., "round" instead of "round-trip"), missing required params, invalid date format

5. Alignment check:
   - If user gave dates, results should match
   - If user gave trip type, results should match
   - If user gave NO dates → empty results are FINE

Respond with JSON:
{
  "validation_status": "pass" | "need_retry",
  "feedback_message": "explanation of issue (if any)",
  "suggested_action": "what should be done to fix (if needed)"
}

Examples:

Example 1 - Valid results (PASS):
User: "Find flights from Dubai to Beirut"
Result: {"error": false, "outbound": [{"airline": "Emirates", "price": 450, ...}], ...}
Response: {
  "validation_status": "pass",
  "feedback_message": "Flight search completed successfully with valid results"
}

Example 2 - Empty results with vague dates (PASS):
User: "Find flights from London to Dubai in November 2025"
Result: {"error": false, "outbound": [], "return": []}
Response: {
  "validation_status": "pass",
  "feedback_message": "User provided vague date (month/year only), empty results are acceptable"
}

Example 3 - Empty results with no dates (PASS):
User: "Find flights from Dubai to Paris"
Result: {"error": false, "outbound": []}
Response: {
  "validation_status": "pass",
  "feedback_message": "User did not provide travel dates, so empty flight results are expected and acceptable"
}

Example 4 - Valid error (PASS):
User: "Find flights for invalid date"
Result: {"error": true, "error_message": "Invalid date format"}
Response: {
  "validation_status": "pass",
  "feedback_message": "Error properly reported - invalid date format"
}

Example 6 - Validation error (ALWAYS RETRY):
User: "Find flights from BEY to DXB"
Result: {"error": true, "error_code": "VALIDATION_ERROR", "error_message": "Invalid trip type: 'round'. Must be 'one-way' or 'round-trip'."}
Response: {
  "validation_status": "need_retry",
  "feedback_message": "Tool validation error: Invalid trip type 'round'. The tool requires 'one-way' or 'round-trip'.",
  "suggested_action": "Correct the trip_type parameter to 'one-way' or 'round-trip' and retry the search"
}

Example 5 - Missing required data with specific dates (RETRY):
User: "Find flights from Dubai to Beirut on December 25, 2025"
Result: {"error": false, "outbound": [{"airline": "Emirates"}]} (missing price)
Response: {
  "validation_status": "need_retry",
  "feedback_message": "User provided specific dates but flight results are missing critical information (prices)",
  "suggested_action": "Retry search to retrieve complete flight information including prices"
}"""


async def flight_agent_feedback_node(state: AgentState) -> AgentState:
    """Flight Agent feedback node that validates flight search results.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with validation results and routing decision
    """
    user_message = state.get("user_message", "")
    flight_result = state.get("flight_result", {})
    flight_feedback_retry_count = state.get("flight_feedback_retry_count", 0)
    
    print(f"\n=== Flight Agent Feedback Validator ===")
    
    # Check for infinite loops
    if flight_feedback_retry_count >= MAX_FEEDBACK_RETRIES:
        print(f"Flight Feedback: Max retries ({MAX_FEEDBACK_RETRIES}) reached, accepting results")
        return {
            "flight_feedback_retry_count": flight_feedback_retry_count + 1
        }
    
    # If no result, nothing to validate
    if not flight_result:
        print("Flight Feedback: No flight result to validate")
        return {}
    
    # CRITICAL: Check for validation errors immediately - these should ALWAYS trigger retry
    if flight_result.get("error") and flight_result.get("error_code") == "VALIDATION_ERROR":
        error_message = flight_result.get("error_message", "")
        suggestion = flight_result.get("suggestion", "")
        print(f"Flight Feedback: VALIDATION_ERROR detected - {error_message}")
        print(f"Flight Feedback: Automatically triggering retry with feedback")
        
        # Create detailed feedback message for the agent
        feedback_msg = f"Tool validation error occurred: {error_message}"
        if suggestion:
            feedback_msg += f"\n\nSuggestion: {suggestion}"
        feedback_msg += "\n\nPlease correct the parameters and retry. Common issues:\n"
        feedback_msg += "- trip_type must be 'one-way' or 'round-trip' (not 'round' or other variations)\n"
        feedback_msg += "- All required parameters must be provided\n"
        feedback_msg += "- Date format must be YYYY-MM-DD\n"
        feedback_msg += "- Airport codes should be valid IATA codes"
        
        return {
            "flight_result": None,
            "flight_feedback_message": feedback_msg,
            "flight_feedback_retry_count": flight_feedback_retry_count + 1
        }
    
    # Prepare validation context (truncate large data to avoid token limits)
    validation_context = {
        "user_request": user_message,
        "result_summary": {
            "has_error": flight_result.get("error", False),
            "error_code": flight_result.get("error_code", ""),
            "error_message": flight_result.get("error_message", ""),
            "suggestion": flight_result.get("suggestion", ""),
            "outbound_count": len(flight_result.get("outbound", [])),
            "return_count": len(flight_result.get("return", [])),
            "sample_outbound": flight_result.get("outbound", [])[:2] if flight_result.get("outbound") else [],
            "departure": flight_result.get("departure", ""),
            "arrival": flight_result.get("arrival", ""),
            "currency": flight_result.get("currency", "")
        }
    }
    
    # Call LLM for validation
    messages = [
        {"role": "system", "content": get_flight_agent_feedback_prompt()},
        {"role": "user", "content": f"Validate these flight search results:\n\n{json.dumps(validation_context, indent=2)}"}
    ]
    
    try:
        session_id = state.get("session_id", "unknown")
        user_email = state.get("user_email")
        llm_start_time = time.time()
        
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        llm_latency_ms = (time.time() - llm_start_time) * 1000
        
        # Log LLM call
        prompt_preview = str(messages[-1].get("content", "")) if messages else ""
        response_preview = response.choices[0].message.content if response.choices[0].message.content else ""
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens if hasattr(response, 'usage') and response.usage else None,
            "completion_tokens": response.usage.completion_tokens if hasattr(response, 'usage') and response.usage else None,
            "total_tokens": response.usage.total_tokens if hasattr(response, 'usage') and response.usage else None
        } if hasattr(response, 'usage') and response.usage else None
        
        log_llm_call(
            session_id=session_id,
            user_email=user_email,
            agent_name="flight_agent_feedback",
            model="gpt-4.1",
            prompt_preview=prompt_preview,
            response_preview=response_preview,
            token_usage=token_usage,
            latency_ms=llm_latency_ms
        )
        
        validation_result = json.loads(response.choices[0].message.content)
        status = validation_result.get("validation_status", "pass")
        feedback_msg = validation_result.get("feedback_message", "")
        suggested_action = validation_result.get("suggested_action", "")
        
        print(f"Flight Feedback: Status = {status}")
        print(f"Flight Feedback: {feedback_msg}")
        
        # Log feedback failure if status indicates failure
        if status != "pass":
            log_feedback_failure(
                session_id=session_id,
                user_email=user_email,
                feedback_node="flight_agent_feedback",
                reason=f"Status: {status}, Message: {feedback_msg}"
            )
        
        # Route based on validation status
        if status == "pass":
            # Results are valid, continue to next step
            return {
                "flight_feedback_message": None,
                "flight_feedback_retry_count": 0
            }
            
        elif status == "need_retry":
            # Results are inadequate, retry flight search
            print(f"Flight Feedback: Requesting retry of flight search")
            full_feedback = f"{feedback_msg}\n\n{suggested_action}" if suggested_action else feedback_msg
            
            # Clear the bad result and increment retry counter
            # The plan executor will re-run this agent
            return {
                "flight_result": None,
                "flight_feedback_message": full_feedback,
                "flight_feedback_retry_count": flight_feedback_retry_count + 1
                # Note: Don't decrement current_step - retry routes directly to agent, not through plan_executor
            }
        
        else:
            # Unknown status, accept results
            print(f"Flight Feedback: Unknown status '{status}', accepting results")
            return {
                "flight_feedback_message": None,
                "flight_feedback_retry_count": flight_feedback_retry_count + 1
            }
            
    except Exception as e:
        print(f"Flight Feedback: Validation error - {e}, accepting results")
        # On error, accept results to avoid blocking
        return {
            "flight_feedback_message": None,
            "flight_feedback_retry_count": flight_feedback_retry_count + 1
        }

