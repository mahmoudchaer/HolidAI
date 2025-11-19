"""Conversational Agent node for LangGraph orchestration - generates final user response."""

import sys
import os
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import AgentState

# Load environment variables from .env file in main directory
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))



def truncate_large_results(collected_info: dict, max_items: int = 20) -> dict:
    """Truncate large result arrays to avoid context overflow.
    
    Args:
        collected_info: Dictionary with collected results
        max_items: Maximum number of items to keep in arrays
        
    Returns:
        Truncated copy of collected_info
    """
    import copy
    truncated = copy.deepcopy(collected_info)
    
    # Truncate hotel images if present
    if "hotel_result" in truncated and isinstance(truncated["hotel_result"], dict):
        hotels = truncated["hotel_result"].get("hotels", [])
        for hotel in hotels:
            # Keep only first 3 images per hotel
            if "hotelImages" in hotel and isinstance(hotel["hotelImages"], list):
                hotel["hotelImages"] = hotel["hotelImages"][:3]
            # Truncate room types
            if "roomTypes" in hotel and isinstance(hotel["roomTypes"], list):
                hotel["roomTypes"] = hotel["roomTypes"][:2]
    
    # Truncate eSIM bundles if present
    if "utilities_result" in truncated and isinstance(truncated["utilities_result"], dict):
        if "bundles" in truncated["utilities_result"] and isinstance(truncated["utilities_result"]["bundles"], list):
            bundles = truncated["utilities_result"]["bundles"]
            if len(bundles) > max_items:
                truncated["utilities_result"]["bundles"] = bundles[:max_items]
                truncated["utilities_result"]["truncated"] = True
                truncated["utilities_result"]["total_bundles"] = len(bundles)
    
    # Truncate flight options if present
    if "flight_result" in truncated and isinstance(truncated["flight_result"], dict):
        if "outbound" in truncated["flight_result"] and isinstance(truncated["flight_result"]["outbound"], list):
            outbound = truncated["flight_result"]["outbound"]
            if len(outbound) > max_items:
                truncated["flight_result"]["outbound"] = outbound[:max_items]
                truncated["flight_result"]["truncated"] = True
    
    # Truncate TripAdvisor locations if present
    if "tripadvisor_result" in truncated and isinstance(truncated["tripadvisor_result"], dict):
        if "data" in truncated["tripadvisor_result"] and isinstance(truncated["tripadvisor_result"]["data"], list):
            data = truncated["tripadvisor_result"]["data"]
            if len(data) > max_items:
                truncated["tripadvisor_result"]["data"] = data[:max_items]
                truncated["tripadvisor_result"]["truncated"] = True
    
    return truncated


def get_conversational_agent_prompt() -> str:
    """Get the system prompt for the Conversational Agent."""
    return """You are a helpful travel assistant that provides friendly, natural, and conversational responses to users about their travel queries.

Your role:
- Take the user's original message and synthesize it with the information gathered from specialized agents
- Generate a natural, conversational response that feels human and helpful
- Present information in a clear, organized manner
- Be friendly, professional, and concise
- Use the actual data provided in the collected_info section - do not make up information

CRITICAL RULES - READ CAREFULLY:
1. NEVER include "Collected_info:" or any JSON structure in your response
2. NEVER show the raw JSON data to the user
3. ONLY provide the actual information extracted from the JSON, formatted naturally
4. Start your response directly with the information - do not mention "Collected_info" or "Based on the information gathered"
5. The JSON data below is for YOUR reference only - the user should NEVER see it

IMPORTANT:
- You MUST use the actual data provided in the collected_info section
- If visa_result, flight_result, hotel_result, or tripadvisor_result are present, they contain real information you need to share
- Do NOT say you don't have information if it's provided in the collected_info section - ALWAYS check the collected_info JSON before saying information is unavailable

- For flight_result: If it has an "outbound" array with items, those are real flight options you found - present them to the user with details like airline, departure/arrival times, prices, etc. Only report an error if the result has "error": true AND no outbound flights data.

- For visa_result: If it has a "result" field with content, that contains the visa requirement information - present it to the user. Preserve any markdown formatting (like **bold** markers) that may be present. Only report an error if the result has "error": true AND no result data.

- For hotel_result: If it has a "hotels" array with items, those are real hotels you found - present them to the user. 
  ⚠️ CRITICAL: Hotels may or may not have price information depending on the search type:
    * If hotels have "roomTypes" or "rates" fields with prices → show the actual prices
    * If hotels DON'T have price fields → DO NOT make up prices! Just show hotel information (name, rating, location, amenities)
    * NEVER hallucinate or invent prices - only show prices if they exist in the data
  Only report an error if the result has "error": true AND no hotels data.

- For tripadvisor_result: If it has a "data" array with items, those are real locations/restaurants you found - present them to the user. Only report an error if the result has "error": true AND no data.

- For utilities_result: This contains utility information (weather, currency conversion, date/time, eSIM bundles, or holidays). Present the information naturally based on what tool was used:
  * MULTIPLE RESULTS: If utilities_result has "multiple_results": true, it contains a "results" array where each item has "tool", "args", and "result". Process each result and present all information together naturally.
  * For weather: Show temperature, conditions, etc. If multiple weather results, show each location separately.
  * For currency: Show the conversion result.
  * For date/time: Show the current date and time.
  * For eSIM bundles: If utilities_result has a "bundles" array, present each bundle with provider name, plan details, validity, price, and MOST IMPORTANTLY - include the purchase link as a clickable markdown link. Format like: "[Provider Name - Plan]($link)" or "Provider: [Purchase here]($link)". ALWAYS include the links from the "link" field in each bundle.
    If eSIM data is unavailable (error with "recommended_providers"), present the recommended provider links as clickable options: "Try these eSIM providers: [Airalo](url), [Holafly](url), etc."
  * For holidays: If utilities_result has a "holidays" array, present each holiday with its name, date, type (e.g., "National holiday", "Observance"), and description. Format dates in a readable way (e.g., "January 1, 2024" instead of "2024-01-01"). Group holidays by month if there are many.
    ⚠️ CRITICAL: If the user asked to avoid holidays AND you're showing flights/hotels, you MUST explain which dates were holidays and why the selected dates avoid them. Example: "I found that January 1st is New Year's Day (national holiday) in France, so I selected dates from January 8-14 which avoid all holidays."
    Only report an error if the result has "error": true AND no actual data.

- Format dates in a natural, readable way (e.g., "December 12, 2025" instead of "2025-12-12")
- Extract and present flight details (airline, times, prices) from the flight_result data
- Extract and present visa requirements from the visa_result data
- Extract and present hotel names, prices, addresses, and other relevant details from the hotel_result data
- Extract and present restaurant/location names, addresses, and other relevant details from the tripadvisor_result data

TRANSPARENCY IN REASONING:
- When the user has specific constraints (avoid holidays, specific budget, dates, etc.), ALWAYS explain your thought process
- Show what you checked, what you found, and WHY you selected the specific options you're recommending
- Example: "You wanted to avoid holidays, so I checked January 2026 and found that January 1st is New Year's Day. I selected flights and hotels from January 8-14 which avoid all holidays."

Your response should start directly with the information, like:
"I've found some great options for your trip to Beirut! As a citizen of the United Arab Emirates, you do not require a visa..."

NOT like:
"Collected_info: { ... } Based on the information gathered..."

Remember: The JSON is invisible to the user - only show the extracted information in a natural, conversational format."""


async def conversational_agent_node(state: AgentState) -> AgentState:
    """Conversational Agent node that generates the final user response.
    
    Args:
        state: Current agent state with all collected information
        
    Returns:
        Updated agent state with final response
    """
    user_message = state.get("user_message", "")
    context = state.get("context", {})
    collected_info = state.get("collected_info", {})
    
    # Also check context for results
    if context.get("flight_result"):
        collected_info["flight_result"] = context.get("flight_result")
    if context.get("hotel_result"):
        collected_info["hotel_result"] = context.get("hotel_result")
    if context.get("visa_result"):
        collected_info["visa_result"] = context.get("visa_result")
    if context.get("tripadvisor_result"):
        collected_info["tripadvisor_result"] = context.get("tripadvisor_result")
    if context.get("utilities_result"):
        collected_info["utilities_result"] = context.get("utilities_result")
    
    # Debug: Log what we're passing to the LLM
    if collected_info.get("hotel_result"):
        hotel_result = collected_info["hotel_result"]
        if isinstance(hotel_result, dict):
            hotels_count = len(hotel_result.get("hotels", []))
            has_error = hotel_result.get("error", False)
            print(f"Conversational agent: Received hotel_result with {hotels_count} hotel(s), error: {has_error}")
    if collected_info.get("tripadvisor_result"):
        tripadvisor_result = collected_info["tripadvisor_result"]
        if isinstance(tripadvisor_result, dict):
            data_count = len(tripadvisor_result.get("data", []))
            has_error = tripadvisor_result.get("error", False)
            print(f"Conversational agent: Received tripadvisor_result with {data_count} location(s), error: {has_error}")
    if collected_info.get("flight_result"):
        flight_result = collected_info["flight_result"]
        if isinstance(flight_result, dict):
            has_error = flight_result.get("error", False)
            outbound = flight_result.get("outbound", [])
            outbound_count = len(outbound) if isinstance(outbound, list) else 0
            print(f"Conversational agent: Received flight_result with {outbound_count} flight option(s), error: {has_error}")
    if collected_info.get("visa_result"):
        visa_result = collected_info["visa_result"]
        if isinstance(visa_result, dict):
            has_error = visa_result.get("error", False)
            has_result = "result" in visa_result or "data" in visa_result
            print(f"Conversational agent: Received visa_result, has data: {has_result}, error: {has_error}")
    if collected_info.get("utilities_result"):
        utilities_result = collected_info["utilities_result"]
        if isinstance(utilities_result, dict):
            has_error = utilities_result.get("error", False)
            print(f"Conversational agent: Received utilities_result, error: {has_error}")
    
    # Prepare messages for LLM
    import json
    
    # Truncate large results to avoid context overflow
    truncated_info = truncate_large_results(collected_info, max_items=20)
    
    messages = [
        {"role": "system", "content": get_conversational_agent_prompt()},
        {
            "role": "user", 
            "content": f"""User's original message: {user_message}

Below is the data collected from specialized agents (THIS IS FOR YOUR REFERENCE ONLY - DO NOT INCLUDE IT IN YOUR RESPONSE):
{json.dumps(truncated_info, indent=2, ensure_ascii=False) if truncated_info else "No information was collected from specialized agents."}

IMPORTANT INSTRUCTIONS:
- Extract the relevant information from the JSON above
- Present it in a natural, conversational way
- DO NOT include "Collected_info:", "Based on the information gathered", or any JSON structure in your response
- Start your response directly with the information (e.g., "I've found some great options..." or "Here's what I found...")
- The user should never see the JSON data - only the formatted information
- For eSIM bundles: ALWAYS include clickable links using markdown format [text](url) for each bundle's purchase link
- If data was truncated (indicated by "truncated": true or "limited": true), mention that more options are available
- Make sure all links are properly formatted as markdown links so they appear as clickable in the UI"""
        }
    ]
    
    # Helper function to clean response and remove any JSON/Collected_info references
    def clean_response(text: str) -> str:
        """Remove any 'Collected_info:' or JSON structures from the response."""
        if not text:
            return text
        
        # First, try to find and remove everything from "Collected_info:" to the first actual content
        text_lower = text.lower()
        collected_info_index = text_lower.find('collected_info')
        
        if collected_info_index != -1:
            # Find where the JSON block ends (look for closing brace followed by actual content)
            # Try to find the end of the JSON structure
            remaining_text = text[collected_info_index:]
            
            # Look for patterns like "}\n\n" or "}\nBased on" or "}\nI've" etc.
            # Find the last closing brace before actual content
            brace_count = 0
            json_end = -1
            in_string = False
            escape_next = False
            
            for i, char in enumerate(remaining_text):
                if escape_next:
                    escape_next = False
                    continue
                if char == '\\':
                    escape_next = True
                    continue
                if char == '"' and not escape_next:
                    in_string = not in_string
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            # Found the end of the JSON object
                            # Look ahead for actual content (not just whitespace/braces)
                            ahead = remaining_text[i+1:].strip()
                            if ahead and not ahead.startswith('{') and not ahead.startswith('}'):
                                json_end = collected_info_index + i + 1
                                break
            
            if json_end != -1:
                # Extract everything after the JSON
                cleaned = text[json_end:].strip()
                # Remove leading empty lines
                while cleaned.startswith('\n'):
                    cleaned = cleaned[1:]
                text = cleaned
        
        # Additional cleanup: remove any lines that are pure JSON structure
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            # Skip lines that are clearly JSON structure
            if (stripped.startswith('{') or 
                stripped.startswith('}') or 
                (stripped.startswith('"') and ':' in stripped and (stripped.endswith(',') or stripped.endswith('"')))):
                continue
            # Skip lines that are just "Collected_info:"
            if 'collected_info' in stripped.lower() and len(stripped) < 50:
                continue
            cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines).strip()
        
        # Final check: if the response still starts with JSON-like content, try to find where actual content begins
        if result.startswith('{') or result.startswith('"'):
            # Try to find the first line that doesn't look like JSON
            lines = result.split('\n')
            for i, line in enumerate(lines):
                stripped = line.strip()
                if (not stripped.startswith('{') and 
                    not stripped.startswith('}') and 
                    not stripped.startswith('"') and
                    'collected_info' not in stripped.lower() and
                    len(stripped) > 10):  # Actual content is usually longer
                    result = '\n'.join(lines[i:]).strip()
                    break
        
        return result
    
    # Call LLM to generate response
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7
        )
        
        message = response.choices[0].message
        raw_response = message.content or "I apologize, but I couldn't generate a response. Please try again."
        
        # Clean the response to remove any JSON/Collected_info references
        final_response = clean_response(raw_response)
    
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        # Log the error for debugging
        print(f"Error in conversational_agent_node: {error_msg}")
        print(f"Traceback: {error_trace}")
        
        # Handle context length errors specifically
        if "context_length" in error_msg.lower() or "maximum context length" in error_msg.lower():
            # Try with simplified messages - just pass a summary
            simplified_messages = [
                {"role": "system", "content": get_conversational_agent_prompt()},
                {
                    "role": "user",
                    "content": f"""User's original message: {user_message}

The system has collected information from specialized agents. Please provide a helpful, natural response based on the available information."""
                }
            ]
            
            try:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=simplified_messages,
                    temperature=0.7
                )
                message = response.choices[0].message
                raw_response = message.content or "I apologize, but I couldn't generate a response. Please try again."
                final_response = clean_response(raw_response)
            except Exception:
                final_response = "I have the information you requested, but there was a technical issue formatting the response. Please try rephrasing your query or ask for specific details."
        else:
            # Other errors
            final_response = f"I encountered an error while generating the response: {error_msg}. Please try again."
    
    updated_state = state.copy()
    updated_state["last_response"] = final_response
    updated_state["route"] = "end"  # End the workflow
    
    return updated_state








