"""Request For Information (RFI) node - validates logical field completeness before Main Agent."""

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


def get_rfi_prompt() -> str:
    """Get the system prompt for the RFI Validator."""
    return """You are a Request For Information (RFI) Validator that checks if the user provided minimum LOGICAL information to understand their travel request.

Your role:
- Check if user provided enough basic information to understand their intent
- You do NOT know about specific tools or technical requirements
- You only check LOGICAL requirements (what a human would need to know)
- If critical information is missing, identify what needs to be asked

WHAT YOU CHECK (Logical Requirements Only):

1. **Flights:**
   - Need: Origin city/airport AND destination city/airport
   - Need: Travel dates (departure date minimum, return date if round-trip)
   - Examples of INCOMPLETE: "Find me flights" (no origin/destination/dates)
   - Examples of COMPLETE: "Flights from Dubai to Paris on January 15"

2. **Hotels:**
   - Need: Location (city or specific area)
   - Dates are OPTIONAL for general browsing, REQUIRED for booking/prices
   - Examples of INCOMPLETE: "Find hotels" (no location)
   - Examples of COMPLETE: "Hotels in Paris" or "Hotels in Paris for Jan 15-20"

3. **Visa:**
   - Need: Nationality/citizenship AND destination country
   - Examples of INCOMPLETE: "Do I need a visa?" (no nationality or destination)
   - Examples of COMPLETE: "UAE citizen traveling to Lebanon, need visa?"

4. **Restaurants/Attractions (TripAdvisor):**
   - Need: Location (city/area)
   - Examples of INCOMPLETE: "Find good restaurants" (no location)
   - Examples of COMPLETE: "Best restaurants in Beirut"

5. **Utilities (weather, currency, etc):**
   - Weather: Need location (can be multiple: "weather in Paris and London")
   - Currency: Need from/to currencies
   - eSIM: Need country/countries (can be multiple: "eSIM for Lebanon and UAE" is COMPLETE)
   - Holidays: Need country

IMPORTANT RULES:
- User must provide LOGICAL minimum to understand intent
- Don't ask for tool-specific details (passenger counts, room numbers, etc) - that comes later
- If user request is clear enough for a human to understand, it's good enough
- Multiple requests can be in one message (e.g., "flights and hotels in Paris")
- Multiple countries/locations are acceptable (e.g., "eSIM for Lebanon and UAE" is COMPLETE - don't ask which one)
- Check EACH request type separately
- If user mentions multiple countries/locations, they want ALL of them - don't ask for clarification

MISSING INFO HANDLING:
- If critical info missing: ask ONLY for that specific missing piece
- Be natural and conversational
- Don't overwhelm user with all possible details
- Ask for ONE thing at a time if multiple things missing

Respond with JSON:
{
  "status": "complete" | "missing_info",
  "missing_fields": ["list of what's missing"],
  "question_to_user": "natural question to ask user (if missing_info)",
  "analysis": "brief explanation of what you checked"
}

Examples:

Example 1 - Complete request:
User: "I'm a UAE citizen going to Beirut. Find flights and hotels for January 15-20."
Response: {
  "status": "complete",
  "missing_fields": [],
  "question_to_user": "",
  "analysis": "User provided: origin (UAE), destination (Beirut), dates (Jan 15-20), nationality (UAE). All logical requirements met for flights, hotels, and potential visa check."
}

Example 2 - Missing origin:
User: "Find flights to Paris"
Response: {
  "status": "missing_info",
  "missing_fields": ["origin_city", "travel_dates"],
  "question_to_user": "I'd be happy to help you find flights to Paris! Where will you be flying from, and what are your travel dates?",
  "analysis": "Destination (Paris) provided but missing origin city and travel dates."
}

Example 3 - Hotels OK without dates:
User: "Show me hotels in Dubai"
Response: {
  "status": "complete",
  "missing_fields": [],
  "question_to_user": "",
  "analysis": "Location (Dubai) provided. For general hotel browsing, this is sufficient. Dates can be asked later if user wants pricing."
}

Example 4 - Visa missing nationality:
User: "Do I need a visa for France?"
Response: {
  "status": "missing_info",
  "missing_fields": ["nationality"],
  "question_to_user": "To check visa requirements for France, I need to know your nationality. What country are you a citizen of?",
  "analysis": "Destination (France) provided but nationality missing for visa check."
}

Example 5 - Multiple requests, partial info:
User: "Find me flights, hotels, and check visa requirements"
Response: {
  "status": "missing_info",
  "missing_fields": ["origin", "destination", "dates", "nationality"],
  "question_to_user": "I'd love to help you plan your trip! To get started, could you tell me: Where are you traveling from and to? What are your travel dates? And what is your nationality?",
  "analysis": "User wants flights, hotels, and visa info but didn't provide any specific details. Need all basic info."
}

Example 6 - eSIM with multiple countries (COMPLETE):
User: "get me esim bundles for Lebanon and UAE"
Response: {
  "status": "complete",
  "missing_fields": [],
  "question_to_user": "",
  "analysis": "User provided both countries (Lebanon and UAE) for eSIM bundles. This is complete - the system can fetch bundles for both countries."
}

Example 7 - eSIM with single country (COMPLETE):
User: "eSIM bundles for Japan"
Response: {
  "status": "complete",
  "missing_fields": [],
  "question_to_user": "",
  "analysis": "User provided country (Japan) for eSIM bundles. This is sufficient."
}"""


async def rfi_node(state: AgentState) -> AgentState:
    """RFI node that validates if user provided minimum logical information.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with routing decision
    """
    user_message = state.get("user_message", "")
    rfi_context = state.get("rfi_context", "")  # For follow-up questions
    
    print(f"\n=== RFI Validator ===")
    
    # Build the validation message
    if rfi_context:
        # This is a follow-up after asking user for missing info
        validation_message = f"""Original user message: {user_message}

Follow-up context: {rfi_context}

Check if the user now provided the missing information."""
    else:
        # First time checking
        validation_message = f"""User message: {user_message}

Check if this message contains enough logical information to understand the travel request."""
    
    # Call LLM for validation
    messages = [
        {"role": "system", "content": get_rfi_prompt()},
        {"role": "user", "content": validation_message}
    ]
    
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        validation_result = json.loads(response.choices[0].message.content)
        status = validation_result.get("status", "complete")
        missing_fields = validation_result.get("missing_fields", [])
        question = validation_result.get("question_to_user", "")
        analysis = validation_result.get("analysis", "")
        
        print(f"RFI: Status = {status}")
        print(f"RFI: {analysis}")
        
        # Route based on validation status
        if status == "complete":
            # User provided enough info, proceed to main agent
            print("RFI: Information complete, routing to Main Agent")
            return {
                "route": "main_agent",
                "rfi_status": "complete",
                "rfi_context": ""
            }
            
        elif status == "missing_info":
            # Critical info missing, ask user through conversational agent
            print(f"RFI: Missing info - {missing_fields}")
            print(f"RFI: Asking user: {question}")
            return {
                "route": "conversational_agent",
                "rfi_status": "missing_info",
                "rfi_missing_fields": missing_fields,
                "rfi_question": question,
                "last_response": question,  # Set the question as response
                "needs_user_input": True  # Flag that we're waiting for user
            }
        
        else:
            # Unknown status, proceed with caution
            print(f"RFI: Unknown status '{status}', proceeding to Main Agent")
            return {
                "route": "main_agent",
                "rfi_status": "complete"
            }
            
    except Exception as e:
        print(f"RFI: Validation error - {e}, proceeding to Main Agent")
        # On error, proceed to avoid blocking
        return {
            "route": "main_agent",
            "rfi_status": "error"
        }

