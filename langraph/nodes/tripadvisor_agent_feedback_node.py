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
    return """You are a TripAdvisor Agent Feedback Validator that ensures location/attraction/restaurant search results meet quality standards.

Your role:
- Validate that TripAdvisor search was properly executed
- Check if results contain necessary information
- Verify that any errors are legitimate and properly handled
- Ensure results align with user's request

VALIDATION RULES:

1. Result structure validation:
   - If error=true, must have error_message explaining the issue
   - If error=false, must have data array with locations/attractions/restaurants
   - Each item should have: name, address/location, rating (optional)

2. Data quality checks:
   - Items should have valid names
   - Location information should be present
   - Ratings should be reasonable if present
   - At least 1 result should be returned (if no error)

3. Search type validation:
   - If user searched for restaurants, results should be restaurants
   - If user searched for attractions, results should be attractions
   - If user searched for locations/cities, results should be locations
   - Results should match the search query

4. Error legitimacy:
   - Valid errors: location not found, no results, API timeout
   - Invalid errors: missing search query (should not happen at this stage)

5. Alignment with user request:
   - Results should match the location user asked about
   - If user requested specific type (restaurants/attractions), results should match
   - If user requested specific criteria (e.g., "best", "top-rated"), results should reflect that

Respond with JSON:
{
  "validation_status": "pass" | "need_retry",
  "feedback_message": "explanation of issue (if any)",
  "suggested_action": "what should be done to fix (if needed)"
}

Examples:

Example 1 - Valid restaurant results (PASS):
User: "Find restaurants in Paris"
Result: {"error": false, "data": [{"name": "Le Restaurant", "rating": 4.5, "address": "..."}], ...}
Response: {
  "validation_status": "pass",
  "feedback_message": "TripAdvisor search completed successfully with valid restaurant results"
}

Example 2 - Valid attraction results (PASS):
User: "Find attractions in Rome"
Result: {"error": false, "data": [{"name": "Colosseum", "rating": 4.8, "location": "..."}], ...}
Response: {
  "validation_status": "pass",
  "feedback_message": "TripAdvisor search completed successfully with valid attraction results"
}

Example 3 - Empty results without explanation (RETRY):
User: "Find restaurants in Paris"
Result: {"error": false, "data": []}
Response: {
  "validation_status": "need_retry",
  "feedback_message": "No results found but no error explanation provided",
  "suggested_action": "Retry search with broader criteria or provide clear explanation"
}

Example 4 - Wrong result type (RETRY):
User: "Find restaurants in Paris"
Result: {"error": false, "data": [{"name": "Eiffel Tower", "type": "attraction"}]}
Response: {
  "validation_status": "need_retry",
  "feedback_message": "Results do not match requested type - user asked for restaurants but got attractions",
  "suggested_action": "Retry search with correct search type parameter"
}

Example 5 - Valid error (PASS):
User: "Find restaurants in invalid-xyz-location"
Result: {"error": true, "error_message": "Location not found"}
Response: {
  "validation_status": "pass",
  "feedback_message": "Error properly reported - location not found"
}"""


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
    
    # Prepare validation context (truncate large data)
    data_sample = []
    if tripadvisor_result.get("data"):
        for item in tripadvisor_result.get("data", [])[:3]:
            sample = {
                "name": item.get("name", ""),
                "rating": item.get("rating", ""),
                "address": item.get("address", item.get("location", "")),
                "type": item.get("type", "")
            }
            data_sample.append(sample)
    
    validation_context = {
        "user_request": user_message,
        "result_summary": {
            "has_error": tripadvisor_result.get("error", False),
            "error_message": tripadvisor_result.get("error_message", ""),
            "result_count": len(tripadvisor_result.get("data", [])),
            "sample_results": data_sample,
            "search_type": tripadvisor_result.get("search_type", "")
        }
    }
    
    # Call LLM for validation
    messages = [
        {"role": "system", "content": get_tripadvisor_agent_feedback_prompt()},
        {"role": "user", "content": f"Validate these TripAdvisor search results:\n\n{json.dumps(validation_context, indent=2)}"}
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

