"""Feedback validation node for Hotel Agent."""

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


def get_hotel_agent_feedback_prompt() -> str:
    """Get the system prompt for the Hotel Agent Feedback Validator."""
    return """You are a Hotel Agent Feedback Validator. Your ONLY job is to catch ACTUAL ERRORS, not judge formatting or data structure.

**YOUR ROLE**: Catch major failures only - you are NOT a grumpy judge!

**CRITICAL - TOOL CAPABILITIES**:
- `get_list_of_hotels`: Returns hotel names, addresses, ratings - **NO PRICES** (tool limitation!)
- `get_hotel_rates`: Returns prices for specific dates - needs check-in/checkout dates
- **User asking "find hotels" WITHOUT specific dates** → Tool will use `get_list_of_hotels` → **NO PRICES IS CORRECT**
- **User asking "hotel prices for Jan 10-15"** → Tool will use `get_hotel_rates` → Prices expected

**WHAT TO FLAG (only these 3 things)**:
1. ❌ **Empty results with no explanation**: User asked for hotels, got zero hotels, no error message
2. ❌ **Tool failed completely**: Error flag is true but unclear why
3. ❌ **Wrong location**: User asked for Paris, got Berlin hotels

**WHAT TO IGNORE (pass these)**:
- ✅ No prices when user didn't specify dates (tool limitation - correct behavior!)
- ✅ "Location field is empty" but address/city/lat/long exist (data is there, just different fields!)
- ✅ Rating is 0 (some hotels don't have ratings - normal!)
- ✅ "Not specifying dates explicitly" (conversational agent can read the data!)
- ✅ Any formatting complaints (LLM can read any format!)

**DEFAULT TO PASS** - If hotel data exists with names and locations, it's good enough!

Respond with JSON:
{
  "validation_status": "pass" | "need_retry",
  "feedback_message": "brief explanation"
}

Examples:

Example 1 - Hotels without prices, NO dates given (PASS):
User: "Find hotels in Paris"
Result: {"error": false, "hotels": [{"name": "Hotel Paris", "address": "123 Rue..."}, ...]}
Response: {"validation_status": "pass", "feedback_message": "Hotels found successfully"}

Example 2 - Hotels without prices, dates mentioned (PASS still - tool limitation):
User: "Find hotels in Paris for January 2026"
Result: {"error": false, "hotels": [{"name": "Hotel Paris", "address": "..."}, ...]}
Response: {"validation_status": "pass", "feedback_message": "Hotels found - price check requires specific dates"}

Example 3 - Empty results (RETRY):
User: "Find hotels in Paris"
Result: {"error": false, "hotels": []}
Response: {"validation_status": "need_retry", "feedback_message": "No hotels returned"}

Example 4 - Error (PASS):
User: "Find hotels in invalid-city"
Result: {"error": true, "error_message": "City not found"}
Response: {"validation_status": "pass", "feedback_message": "Error handled properly"}"""


async def hotel_agent_feedback_node(state: AgentState) -> AgentState:
    """Hotel Agent feedback node that validates hotel search results.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with validation results and routing decision
    """
    user_message = state.get("user_message", "")
    hotel_result = state.get("hotel_result", {})
    hotel_feedback_retry_count = state.get("hotel_feedback_retry_count", 0)
    
    print(f"\n=== Hotel Agent Feedback Validator ===")
    
    # Check for infinite loops
    if hotel_feedback_retry_count >= MAX_FEEDBACK_RETRIES:
        print(f"Hotel Feedback: Max retries ({MAX_FEEDBACK_RETRIES}) reached, accepting results")
        return {
            "hotel_feedback_retry_count": hotel_feedback_retry_count + 1
        }
    
    # If no result, nothing to validate
    if not hotel_result:
        print("Hotel Feedback: No hotel result to validate")
        return {}
    
    # Prepare validation context (truncate large data)
    hotels_sample = []
    if hotel_result.get("hotels"):
        for hotel in hotel_result.get("hotels", [])[:2]:
            # Check various location fields
            location_info = []
            if hotel.get("address"):
                location_info.append(hotel.get("address"))
            if hotel.get("city"):
                location_info.append(hotel.get("city"))
            if hotel.get("country"):
                location_info.append(hotel.get("country"))
            
            sample = {
                "name": hotel.get("name", ""),
                "rating": hotel.get("rating", ""),
                "has_prices": "roomTypes" in hotel or "rates" in hotel,
                "location": ", ".join(location_info) if location_info else "Not specified",
                "has_location_data": bool(hotel.get("address") or hotel.get("city") or hotel.get("latitude"))
            }
            hotels_sample.append(sample)
    
    validation_context = {
        "user_request": user_message,
        "result_summary": {
            "has_error": hotel_result.get("error", False),
            "error_message": hotel_result.get("error_message", ""),
            "hotel_count": len(hotel_result.get("hotels", [])),
            "sample_hotels": hotels_sample,
            "location": hotel_result.get("location", "")
        }
    }
    
    # Call LLM for validation
    messages = [
        {"role": "system", "content": get_hotel_agent_feedback_prompt()},
        {"role": "user", "content": f"Validate these hotel search results:\n\n{json.dumps(validation_context, indent=2)}"}
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
        suggested_action = validation_result.get("suggested_action", "")
        
        print(f"Hotel Feedback: Status = {status}")
        print(f"Hotel Feedback: {feedback_msg}")
        
        # Route based on validation status
        if status == "pass":
            # Results are valid, continue
            return {
                "hotel_feedback_message": None,
                "hotel_feedback_retry_count": 0
            }
            
        elif status == "need_retry":
            # Results are inadequate, retry hotel search
            print(f"Hotel Feedback: Requesting retry of hotel search")
            full_feedback = f"{feedback_msg}\n\n{suggested_action}" if suggested_action else feedback_msg
            
            return {
                "hotel_result": None,
                "hotel_feedback_message": full_feedback,
                "hotel_feedback_retry_count": hotel_feedback_retry_count + 1
                # Note: Don't decrement current_step - retry routes directly to agent, not through plan_executor
            }
        
        else:
            # Unknown status, accept results
            print(f"Hotel Feedback: Unknown status '{status}', accepting results")
            return {
                "hotel_feedback_message": None,
                "hotel_feedback_retry_count": hotel_feedback_retry_count + 1
            }
            
    except Exception as e:
        print(f"Hotel Feedback: Validation error - {e}, accepting results")
        return {
            "hotel_feedback_message": None,
            "hotel_feedback_retry_count": hotel_feedback_retry_count + 1
        }

