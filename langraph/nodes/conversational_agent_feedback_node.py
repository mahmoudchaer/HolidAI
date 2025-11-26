"""Feedback validation node for Conversational Agent."""

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


def get_conversational_agent_feedback_prompt() -> str:
    """Get the system prompt for the Conversational Agent Feedback Validator."""
    return """You are a Conversational Agent Feedback Validator that ensures the final user response meets quality standards.

Your role:
- Validate that the final response is comprehensive and helpful
- Check if response properly uses all collected information
- Verify that response is conversational and user-friendly
- Ensure no critical information was left out or misrepresented

VALIDATION RULES:

1. Response completeness:
   - Response should address the user's original query
   - All relevant collected information should be included
   - No critical data should be missing (flights, hotels, visa info, etc.)
   - **IMPORTANT**: If is_preview_truncated=true, only validate beginning and ending
   - Long responses (2000+ chars) are ACCEPTABLE if they properly present data

2. Data presentation quality:
   - Information should be presented in a natural, conversational way
   - No raw JSON or technical data should be visible
   - Data should be formatted nicely (dates, prices, etc.)
   - Links (especially eSIM links) should be clickable markdown format

3. Accuracy checks:
   - Response should not contradict the collected data
   - Prices, dates, and names should match source data
   - No hallucinated information that wasn't in collected data

4. User experience:
   - Response should be friendly and helpful
   - Should feel like talking to a knowledgeable travel assistant
   - Should be concise but comprehensive
   - Should avoid technical jargon unless necessary

5. Critical issues to catch:
   - Response includes "Collected_info:" or JSON structure (should never happen)
   - Missing key information that was collected (e.g., user asked for hotels but response doesn't mention them)
   - Contradictory information (e.g., says "no visa required" when data shows visa is required)
   - Empty or generic response when specific data was available
   - Missing links when eSIM bundles or other bookable items were provided
   - **IMPORTANT**: For FLIGHTS, booking links and Google Flights URLs are available in flight data and can be included in text when relevant
   - **IMPORTANT**: Only require links for eSIM bundles and hotel bookings (when _booking_intent is true)

Respond with JSON:
{
  "validation_status": "pass" | "need_regenerate",
  "feedback_message": "explanation of issue (if any)",
  "suggested_fix": "what should be improved (if needed)"
}

Examples:

Example 1 - Good response (PASS):
User: "Find flights from Dubai to Paris"
Collected: {"flight_result": {"outbound": [{"airline": "Emirates", "price": 450}]}}
Response: "I found several flight options from Dubai to Paris! Emirates offers flights starting at 450 USD..."
Validation: {
  "validation_status": "pass",
  "feedback_message": "Response is comprehensive, conversational, and uses collected data properly"
}

Example 2 - Missing collected data (REGENERATE):
User: "Find flights and hotels in Paris"
Collected: {"flight_result": {...}, "hotel_result": {"hotels": [...]}}
Response: "I found some great flights to Paris!" (no mention of hotels)
Validation: {
  "validation_status": "need_regenerate",
  "feedback_message": "Response mentions flights but completely omits hotel information that was collected",
  "suggested_fix": "Include all collected information - both flights and hotels"
}

Example 3 - Shows JSON to user (REGENERATE):
User: "Find hotels in Paris"
Response: "Collected_info: {\"hotels\": [...]} Here are the hotels..."
Validation: {
  "validation_status": "need_regenerate",
  "feedback_message": "Response exposes raw JSON structure to user",
  "suggested_fix": "Remove all JSON and technical details, present only the extracted information naturally"
}

Example 4 - Missing links for eSIM (REGENERATE):
User: "Find eSIM for France"
Collected: {"utilities_result": {"bundles": [{"provider": "Airalo", "link": "https://..."}]}}
Response: "I found eSIM bundles: Airalo offers 5GB for $10"
Validation: {
  "validation_status": "need_regenerate",
  "feedback_message": "Response doesn't include purchase links for eSIM bundles",
  "suggested_fix": "Add clickable markdown links for each eSIM bundle using [text](url) format"
}

Example 4b - Flight with booking link (PASS):
User: "Find flights to Dubai"
Collected: {"flight_result": {"outbound": [{"airline": "Emirates", "price": 270, "booking_link": "https://...", "google_flights_url": "https://..."}]}}
Response: "I found Emirates flight for $270. You can [book here](booking_link) or [view on Google Flights](google_flights_url)"
Validation: {
  "validation_status": "pass",
  "feedback_message": "Response properly includes booking links from flight data"
}

Example 5 - Contradictory information (REGENERATE):
User: "Do I need visa as UAE citizen to Lebanon?"
Collected: {"visa_result": {"result": "UAE citizens do not require a visa..."}}
Response: "You will need to apply for a visa to enter Lebanon..."
Validation: {
  "validation_status": "need_regenerate",
  "feedback_message": "Response contradicts collected data - says visa required when data says not required",
  "suggested_fix": "Correct the response to match the actual visa requirement data"
}

Example 6 - Generic when specific data available (REGENERATE):
User: "Find hotels in Paris"
Collected: {"hotel_result": {"hotels": [{"name": "Hotel A", "rating": 4.5}, {"name": "Hotel B"}]}}
Response: "There are many hotels available in Paris."
Validation: {
  "validation_status": "need_regenerate",
  "feedback_message": "Response is too generic when specific hotel data was collected",
  "suggested_fix": "Present the actual hotels with names, ratings, and details from collected data"
}"""


async def conversational_agent_feedback_node(state: AgentState) -> AgentState:
    """Conversational Agent feedback node that validates the final user response.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with validation results and routing decision
    """
    user_message = state.get("user_message", "")
    last_response = state.get("last_response", "")
    collected_info = state.get("collected_info", {})
    conversational_feedback_retry_count = state.get("conversational_feedback_retry_count", 0)
    
    print(f"\n=== Conversational Agent Feedback Validator ===")
    
    # Check for infinite loops
    if conversational_feedback_retry_count >= MAX_FEEDBACK_RETRIES:
        print(f"Conversational Feedback: Max retries ({MAX_FEEDBACK_RETRIES}) reached, accepting response")
        return {
            "route": "end",
            "conversational_feedback_retry_count": conversational_feedback_retry_count + 1
        }
    
    # If no response, nothing to validate
    if not last_response:
        print("Conversational Feedback: No response to validate")
        return {"route": "end"}
    
    # If RFI is asking for missing info, skip validation and just END
    # (The response is asking the user for more info, not a final answer)
    rfi_status = state.get("rfi_status", "")
    if rfi_status == "missing_info":
        print("Conversational Feedback: RFI asking for missing info, skipping validation")
        return {"route": "end"}
    
    # Prepare validation context (summarize collected info to avoid token limits)
    collected_summary = {
        "has_flight_data": bool(collected_info.get("flight_result")),
        "has_hotel_data": bool(collected_info.get("hotel_result")),
        "has_visa_data": bool(collected_info.get("visa_result")),
        "has_tripadvisor_data": bool(collected_info.get("tripadvisor_result")),
        "has_utilities_data": bool(collected_info.get("utilities_result"))
    }
    
    # Add brief samples if data exists
    if collected_info.get("flight_result"):
        fr = collected_info["flight_result"]
        collected_summary["flight_sample"] = {
            "has_error": fr.get("error", False),
            "outbound_count": len(fr.get("outbound", []))
        }
    
    if collected_info.get("hotel_result"):
        hr = collected_info["hotel_result"]
        collected_summary["hotel_sample"] = {
            "has_error": hr.get("error", False),
            "hotel_count": len(hr.get("hotels", []))
        }
    
    if collected_info.get("visa_result"):
        vr = collected_info["visa_result"]
        collected_summary["visa_sample"] = {
            "has_error": vr.get("error", False),
            "has_result": bool(vr.get("result") or vr.get("data"))
        }
    
    if collected_info.get("utilities_result"):
        ur = collected_info["utilities_result"]
        collected_summary["utilities_sample"] = {
            "has_error": ur.get("error", False),
            "has_bundles": bool(ur.get("bundles")),
            "has_holidays": bool(ur.get("holidays"))
        }
    
    # Truncate response if too long (keep first 2500 chars for validation)
    # Also include last 500 chars to check if it ends properly
    response_length = len(last_response)
    if response_length > 2500:
        response_sample = last_response[:2000] + "\n\n[... middle section truncated ...]\n\n" + last_response[-500:]
        is_preview = True
    else:
        response_sample = last_response
        is_preview = False
    
    validation_context = {
        "user_request": user_message,
        "collected_info_summary": collected_summary,
        "response_preview": response_sample,
        "response_length": response_length,
        "is_preview_truncated": is_preview,
        "note": "If is_preview_truncated=true, the full response is longer but properly formatted. Only validate beginning and ending."
    }
    
    # Call LLM for validation
    messages = [
        {"role": "system", "content": get_conversational_agent_feedback_prompt()},
        {"role": "user", "content": f"Validate this final user response:\n\n{json.dumps(validation_context, indent=2)}"}
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
        suggested_fix = validation_result.get("suggested_fix", "")
        
        print(f"Conversational Feedback: Status = {status}")
        print(f"Conversational Feedback: {feedback_msg}")
        
        # Route based on validation status
        if status == "pass":
            # Response is good, route to final planner agent
            return {
                "route": "final_planner_agent",
                "conversational_feedback_message": None,
                "conversational_feedback_retry_count": 0
            }
            
        elif status == "need_regenerate":
            # Response needs improvement, regenerate
            print(f"Conversational Feedback: Requesting response regeneration")
            full_feedback = f"{feedback_msg}\n\n{suggested_fix}" if suggested_fix else feedback_msg
            
            # Clear the bad response and route back to conversational agent
            return {
                "route": "conversational_agent",
                "last_response": "",
                "conversational_feedback_message": full_feedback,
                "conversational_feedback_retry_count": conversational_feedback_retry_count + 1
            }
        
        else:
            # Unknown status, accept response
            print(f"Conversational Feedback: Unknown status '{status}', accepting response")
            return {
                "route": "end",
                "conversational_feedback_message": None,
                "conversational_feedback_retry_count": conversational_feedback_retry_count + 1
            }
            
    except Exception as e:
        print(f"Conversational Feedback: Validation error - {e}, accepting response")
        return {
            "route": "end",
            "conversational_feedback_message": None,
            "conversational_feedback_retry_count": conversational_feedback_retry_count + 1
        }

