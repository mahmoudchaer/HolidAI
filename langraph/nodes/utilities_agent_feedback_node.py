"""Feedback validation node for Utilities Agent."""

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


def get_utilities_agent_feedback_prompt() -> str:
    """Get the system prompt for the Utilities Agent Feedback Validator."""
    return """You are a Utilities Agent Feedback Validator that ensures utility function results meet quality standards.

Your role:
- Validate that utilities operations were properly executed
- Check if results contain necessary information
- Verify that any errors are legitimate and properly handled
- Ensure results align with user's request

The Utilities Agent handles multiple tools:
- get_holidays: Returns holidays for a country
- weather: Returns weather information for a location
- currency_conversion: Converts currency amounts
- date_time: Returns current date/time for a location
- esim_bundles: Returns eSIM data bundles for a country

VALIDATION RULES:

**CRITICAL**: The validation context includes:
- user_request: The full original user query (may contain multiple tasks)
- current_step_task: What THIS specific execution was asked to do
- **ONLY validate against current_step_task, NOT the full user_request**

1. Result structure validation:
   - If error=true, must have error_message explaining the issue
   - If error=false, must have appropriate data based on tool used in THIS step
   - May have multiple_results=true if multiple tools were called

2. Tool-specific validation:
   
   a) get_holidays:
      - Must have "holidays" array (can be empty - not all months have holidays)
      - **IMPORTANT**: Empty holidays array (count: 0) is ACCEPTABLE and valid
      - Only flag as error if error=true with error_message
      - Each holiday (if present) should have: name, date, type
      - Dates should be valid and formatted correctly
   
   b) weather:
      - Must have temperature, conditions
      - Location should match requested location
   
   c) currency_conversion:
      - Must have converted amount
      - Should include from/to currencies
      - Conversion rate should be reasonable
      - **IMPORTANT**: If step task mentions "convert eSIM prices" and eSIM bundles with prices are provided, that's SUFFICIENT (conversational agent will handle conversion)
   
   d) date_time:
      - Must have current date and time
      - Timezone should match location if specified
   
   e) esim_bundles:
      - Must have "bundles" array with bundle objects
      - Each bundle should have: provider, data, price, validity
      - If error with recommended_providers, that's acceptable

3. Multiple results handling:
   - If multiple_results=true, must have "results" array
   - Each result should have tool name and result data
   - All results should be valid individually
   - **Remember**: Only validate tools that were requested in current_step_task

4. Error legitimacy:
   - **CRITICAL**: If error_code is "DATA_UNAVAILABLE", ALWAYS accept (data simply doesn't exist) - DO NOT RETRY
   - Valid errors: API timeout, invalid parameters, no data available (all should be ACCEPTED, not retried)
   - Invalid errors: missing required parameters (should not happen at this stage)
   - **IMPORTANT**: Programming errors (TypeError, AttributeError) should trigger retry
   - **IMPORTANT**: If error_code is "UNEXPECTED_ERROR" with traceback, it's likely a bug - retry might not help
   - If error exists but result has useful fallback data, that's acceptable (PASS)
   - **CRITICAL**: Empty results (holidays_count: 0, no bundles, etc.) WITHOUT error=true are VALID - don't retry!

Respond with JSON:
{
  "validation_status": "pass" | "need_retry",
  "feedback_message": "explanation of issue (if any)",
  "suggested_action": "what should be done to fix (if needed)"
}

Examples:

Example 1 - Valid holidays (PASS):
User: "Get holidays for France in January 2026"
Result: {"error": false, "holidays": [{"name": "New Year", "date": "2026-01-01", "type": "national"}], ...}
Response: {
  "validation_status": "pass",
  "feedback_message": "Holidays retrieved successfully"
}

Example 2 - Valid weather (PASS):
User: "What's the weather in Paris?"
Result: {"error": false, "temperature": 15, "conditions": "Partly cloudy", "location": "Paris"}
Response: {
  "validation_status": "pass",
  "feedback_message": "Weather information retrieved successfully"
}

Example 3 - Valid currency conversion (PASS):
User: "Convert 100 USD to EUR"
Result: {"error": false, "amount": 92.5, "from": "USD", "to": "EUR"}
Response: {
  "validation_status": "pass",
  "feedback_message": "Currency conversion completed successfully"
}

Example 4 - Valid eSIM with recommended providers (PASS):
User: "Find eSIM for France"
Result: {"error": true, "error_message": "API error", "recommended_providers": [...]}
Response: {
  "validation_status": "pass",
  "feedback_message": "eSIM search error handled with recommended provider fallback"
}

Example 5 - Empty holidays is valid (PASS):
User: "Get holidays for France in January 2026"
Result: {"error": false, "holidays": [], "count": 0}
Response: {
  "validation_status": "pass",
  "feedback_message": "Holidays query completed successfully - no holidays in specified period"
}

Example 6 - Missing critical data with error (PASS):
User: "Get holidays for InvalidCountry"
Result: {"error": true, "error_message": "Country not found"}
Response: {
  "validation_status": "pass",
  "feedback_message": "Error properly reported - invalid country"
}

Example 7 - Valid multiple results (PASS):
User: "Get holidays and weather for France"
Result: {"error": false, "multiple_results": true, "results": [
  {"tool": "get_holidays", "result": {"holidays": [...]}},
  {"tool": "weather", "result": {"temperature": 15}}
]}
Response: {
  "validation_status": "pass",
  "feedback_message": "Multiple utility operations completed successfully"
}

Example 8 - Valid multiple results with data indicators (PASS):
User: "Get holidays and eSIM for France"
Result summary: {
  "has_multiple_results": true,
  "results_count": 2,
  "results_summary": [
    {"tool": "get_holidays", "has_error": false, "has_holidays": true, "holidays_count": 12},
    {"tool": "get_esim_bundles", "has_error": false, "has_bundles": true, "bundles_count": 50}
  ]
}
Response: {
  "validation_status": "pass",
  "feedback_message": "Multiple operations completed successfully - holidays and eSIM bundles retrieved"
}

Example 9 - Empty holidays with eSIM is still valid (PASS):
User: "Get holidays and eSIM for France in January 2026"
Result summary: {
  "has_multiple_results": true,
  "results_count": 2,
  "results_summary": [
    {"tool": "get_holidays", "has_error": false, "has_holidays": false, "holidays_count": 0},
    {"tool": "get_esim_bundles", "has_error": false, "has_bundles": true, "bundles_count": 50}
  ]
}
Response: {
  "validation_status": "pass",
  "feedback_message": "Operations completed - no holidays found for specified period (which is valid), eSIM bundles retrieved successfully"
}

Example 10 - Step-specific validation (PASS):
User (full request): "Find flights and hotels, check visa, get eSIM bundles, and convert prices to AED"
Current step task: "Get eSIM bundles for France"
Result summary: {
  "has_error": false,
  "has_bundles": true,
  "bundles_count": 30
}
Response: {
  "validation_status": "pass",
  "feedback_message": "eSIM bundles retrieved successfully. Other tasks (flights, hotels, visa, conversion) are handled in separate steps."
}

Example 11 - Convert eSIM prices step (PASS):
User (full request): "Get eSIM bundles for France and convert the eSIM prices to AED"
Current step task: "Convert eSIM bundle prices to AED currency"
Result summary: {
  "has_error": false,
  "has_bundles": true,
  "bundles_count": 30,
  "bundles_have_prices": true
}
Response: {
  "validation_status": "pass",
  "feedback_message": "eSIM bundles with prices retrieved successfully. The conversational agent will handle the currency conversion to AED."
}

Example 12 - DATA_UNAVAILABLE is legitimate (PASS):
User: "Get eSIM bundles for Dubai"
Current step task: "Get eSIM bundles for Dubai"
Result summary: {
  "has_error": true,
  "error_code": "DATA_UNAVAILABLE",
  "error_message": "eSIM data not available for 'Dubai' in our database."
}
Response: {
  "validation_status": "pass",
  "feedback_message": "DATA_UNAVAILABLE error is legitimate - the data simply doesn't exist in the database. The conversational agent will inform the user."
}

**NOTE**: If step task mentions "convert eSIM prices" and eSIM bundles with prices are provided, NO explicit currency_conversion tool call is needed. The conversational agent handles simple arithmetic conversions.
"""


async def utilities_agent_feedback_node(state: AgentState) -> AgentState:
    """Utilities Agent feedback node that validates utility operation results.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with validation results and routing decision
    """
    user_message = state.get("user_message", "")
    utilities_result = state.get("utilities_result", {})
    utilities_feedback_retry_count = state.get("utilities_feedback_retry_count", 0)
    
    print(f"\n=== Utilities Agent Feedback Validator ===")
    
    # Check for infinite loops
    if utilities_feedback_retry_count >= MAX_FEEDBACK_RETRIES:
        print(f"Utilities Feedback: Max retries ({MAX_FEEDBACK_RETRIES}) reached, accepting results")
        return {
            "utilities_feedback_retry_count": utilities_feedback_retry_count + 1
        }
    
    # If no result, nothing to validate
    if not utilities_result:
        print("Utilities Feedback: No result to validate")
        return {}
    
    # Check for programming errors (UNEXPECTED_ERROR) - these won't be fixed by retrying
    if utilities_result.get("error_code") == "UNEXPECTED_ERROR":
        print("Utilities Feedback: UNEXPECTED_ERROR detected (likely a bug), accepting results to avoid infinite retry")
        return {
            "utilities_feedback_message": None,
            "utilities_feedback_retry_count": 0
        }
    
    # Check for DATA_UNAVAILABLE errors - these are legitimate and won't be fixed by retrying
    if utilities_result.get("error_code") == "DATA_UNAVAILABLE":
        print(f"Utilities Feedback: DATA_UNAVAILABLE error detected - {utilities_result.get('error_message', '')} - accepting as legitimate")
        return {
            "utilities_feedback_message": None,
            "utilities_feedback_retry_count": 0
        }
    
    # Check for DATA_UNAVAILABLE in multiple results
    if utilities_result.get("multiple_results"):
        all_data_unavailable = True
        for result_item in utilities_result.get("results", []):
            tool_result = result_item.get("result", {})
            if tool_result.get("error_code") != "DATA_UNAVAILABLE":
                all_data_unavailable = False
                break
        if all_data_unavailable:
            print("Utilities Feedback: All results have DATA_UNAVAILABLE error - accepting as legitimate")
            return {
                "utilities_feedback_message": None,
                "utilities_feedback_retry_count": 0
            }
    
    # Prepare validation context (truncate large data)
    result_summary = {
        "has_error": utilities_result.get("error", False),
        "error_message": utilities_result.get("error_message", ""),
        "error_code": utilities_result.get("error_code", ""),
        "has_multiple_results": utilities_result.get("multiple_results", False)
    }
    
    # Add specific data based on what's in the result
    if utilities_result.get("holidays"):
        result_summary["holidays_count"] = len(utilities_result.get("holidays", []))
        result_summary["sample_holidays"] = utilities_result.get("holidays", [])[:3]
    
    if utilities_result.get("bundles"):
        bundles = utilities_result.get("bundles", [])
        result_summary["bundles_count"] = len(bundles)
        result_summary["has_bundles"] = True
        # Check if bundles have prices
        if bundles and len(bundles) > 0:
            result_summary["bundles_have_prices"] = bool(bundles[0].get("price"))
    
    if utilities_result.get("temperature"):
        result_summary["has_weather"] = True
        result_summary["temperature"] = utilities_result.get("temperature")
    
    if utilities_result.get("amount"):
        result_summary["has_currency_conversion"] = True
        result_summary["amount"] = utilities_result.get("amount")
    
    if utilities_result.get("multiple_results"):
        result_summary["results_count"] = len(utilities_result.get("results", []))
        # Summarize each result with more details
        results_summary = []
        for result in utilities_result.get("results", [])[:5]:
            tool_result = result.get("result", {})
            summary = {
                "tool": result.get("tool", ""),
                "has_error": tool_result.get("error", False)
            }
            # Add tool-specific data indicators
            if result.get("tool") == "get_holidays":
                summary["has_holidays"] = bool(tool_result.get("holidays"))
                summary["holidays_count"] = len(tool_result.get("holidays", []))
            elif result.get("tool") == "get_esim_bundles":
                summary["has_bundles"] = bool(tool_result.get("bundles"))
                summary["bundles_count"] = len(tool_result.get("bundles", []))
                # Check if bundles have prices
                bundles = tool_result.get("bundles", [])
                if bundles and len(bundles) > 0:
                    summary["bundles_have_prices"] = bool(bundles[0].get("price"))
            elif result.get("tool") == "get_real_time_weather":
                summary["has_weather"] = bool(tool_result.get("temperature"))
            elif result.get("tool") == "convert_currencies":
                summary["has_conversion"] = bool(tool_result.get("amount"))
            
            results_summary.append(summary)
        result_summary["results_summary"] = results_summary
    
    # Get current step context to understand what THIS execution was supposed to do
    execution_plan = state.get("execution_plan", [])
    current_step_index = state.get("current_step", 1) - 1
    step_context = ""
    if execution_plan and 0 <= current_step_index < len(execution_plan):
        current_step = execution_plan[current_step_index]
        step_context = current_step.get("description", "")
    
    validation_context = {
        "user_request": user_message,
        "current_step_task": step_context,  # What THIS step was supposed to do
        "result_summary": result_summary
    }
    
    # Call LLM for validation
    messages = [
        {"role": "system", "content": get_utilities_agent_feedback_prompt()},
        {"role": "user", "content": f"Validate these utilities operation results:\n\n{json.dumps(validation_context, indent=2)}"}
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
        
        print(f"Utilities Feedback: Status = {status}")
        print(f"Utilities Feedback: {feedback_msg}")
        
        # Route based on validation status
        if status == "pass":
            # Results are valid, continue
            return {
                "utilities_feedback_message": None,
                "utilities_feedback_retry_count": 0
            }
            
        elif status == "need_retry":
            # Results are inadequate, retry operation
            print(f"Utilities Feedback: Requesting retry of utilities operation")
            full_feedback = f"{feedback_msg}\n\n{suggested_action}" if suggested_action else feedback_msg
            
            return {
                "utilities_result": None,
                "utilities_feedback_message": full_feedback,
                "utilities_feedback_retry_count": utilities_feedback_retry_count + 1
                # Note: Don't decrement current_step - retry routes directly to agent, not through plan_executor
            }
        
        else:
            # Unknown status, accept results
            print(f"Utilities Feedback: Unknown status '{status}', accepting results")
            return {
                "utilities_feedback_message": None,
                "utilities_feedback_retry_count": utilities_feedback_retry_count + 1
            }
            
    except Exception as e:
        print(f"Utilities Feedback: Validation error - {e}, accepting results")
        return {
            "utilities_feedback_message": None,
            "utilities_feedback_retry_count": utilities_feedback_retry_count + 1
        }

