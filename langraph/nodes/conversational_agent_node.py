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


def _parse_price(price):
    """Parse price from flight data."""
    if isinstance(price, (int, float)):
        return float(price)
    if isinstance(price, str):
        # Remove currency symbols and commas
        cleaned = price.replace("$", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except:
            return float('inf')
    return float('inf')


def _filter_flights_intelligently(user_message: str, outbound_flights: list, return_flights: list) -> tuple:
    """
    Intelligently filter flights based on user's message intent.
    Uses LLM to understand filtering criteria, then applies filters.
    
    Returns:
        (filtered_outbound, filtered_return) - filtered flight lists
    """
    if not outbound_flights and not return_flights:
        return outbound_flights, return_flights
    
    # Use LLM to understand filtering intent
    try:
        filter_prompt = f"""Analyze the user's message and determine if they want to filter flight results.

User message: "{user_message}"

Determine the filtering criteria from the user's intent:
1. Do they want ONLY the cheapest option(s)? (e.g., "cheapest one", "cheapest", "lowest price", "cheapest flight", "show me the cheapest")
2. Do they want direct flights only? (e.g., "direct", "non-stop", "no layovers", "direct flights only")
3. Do they want morning/afternoon/evening flights? (e.g., "morning flights", "early departure", "afternoon only")
4. Do they want specific airlines? (e.g., "Emirates only", "not Turkish Airlines", "only MEA")
5. Do they want flights under a certain price? (e.g., "under $500", "less than $300", "budget under 400")
6. Do they want shortest duration? (e.g., "fastest", "quickest", "shortest", "fastest option")

IMPORTANT:
- If user says "cheapest one" or similar, they want ONLY the cheapest option(s), not all flights
- For round-trip: "cheapest one" means cheapest outbound AND cheapest return (keep_count=1 for each)
- Understand context: "cheapest" after seeing flight results means filter to show only cheapest
- Be intelligent: understand variations like "show me cheapest", "get cheapest", "lowest price option"

Respond with JSON:
{{
  "filter_type": "cheapest" | "direct_only" | "morning" | "afternoon" | "evening" | "airline" | "max_price" | "shortest_duration" | "none",
  "filter_value": "value if needed (e.g., airline name, max price number, etc.)",
  "apply_to": "both" | "outbound" | "return",
  "keep_count": number of results to keep (e.g., 1 for "cheapest one", 3 for "top 3 cheapest")
}}

If no clear filtering intent, return {{"filter_type": "none"}}."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes user intent for filtering flight results. Respond only with valid JSON."},
                {"role": "user", "content": filter_prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        filter_decision = response.choices[0].message.content
        import json
        filter_criteria = json.loads(filter_decision)
        
        filter_type = filter_criteria.get("filter_type", "none")
        keep_count = filter_criteria.get("keep_count", 1)
        apply_to = filter_criteria.get("apply_to", "both")
        
        print(f"[FILTER] Detected filter type: {filter_type}, keep_count: {keep_count}, apply_to: {apply_to}")
        
        if filter_type == "none":
            return outbound_flights, return_flights
        
        filtered_outbound = outbound_flights.copy() if outbound_flights else []
        filtered_return = return_flights.copy() if return_flights else []
        
        # Apply filters to outbound
        if apply_to in ["both", "outbound"] and filtered_outbound:
            if filter_type == "cheapest":
                # Sort by price and keep only the cheapest
                filtered_outbound.sort(key=lambda f: _parse_price(f.get("price", float('inf'))))
                filtered_outbound = filtered_outbound[:keep_count]
            elif filter_type == "direct_only":
                # Keep only direct flights (no layovers)
                filtered_outbound = [f for f in filtered_outbound if not f.get("layovers") or len(f.get("layovers", [])) == 0]
            elif filter_type == "shortest_duration":
                # Sort by duration and keep shortest
                filtered_outbound.sort(key=lambda f: f.get("total_duration", float('inf')))
                filtered_outbound = filtered_outbound[:keep_count]
            elif filter_type == "max_price":
                max_price = float(filter_criteria.get("filter_value", float('inf')))
                filtered_outbound = [f for f in filtered_outbound if _parse_price(f.get("price", float('inf'))) <= max_price]
            elif filter_type == "airline":
                airline_name = filter_criteria.get("filter_value", "").lower()
                filtered_outbound = [f for f in filtered_outbound if any(
                    segment.get("airline", "").lower() == airline_name 
                    for segment in f.get("flights", [])
                )]
            elif filter_type in ["morning", "afternoon", "evening"]:
                # Filter by departure time
                hour_ranges = {
                    "morning": (0, 12),
                    "afternoon": (12, 17),
                    "evening": (17, 24)
                }
                start_hour, end_hour = hour_ranges.get(filter_type, (0, 24))
                def _get_departure_hour(flight):
                    """Extract hour from departure time."""
                    try:
                        first_segment = flight.get("flights", [{}])[0]
                        time_str = first_segment.get("departure_airport", {}).get("time", "")
                        # Handle format like "2025-12-25 05:15" or "05:15"
                        if " " in time_str:
                            time_str = time_str.split(" ")[-1]
                        hour = int(time_str.split(":")[0])
                        return hour
                    except:
                        return 0
                filtered_outbound = [f for f in filtered_outbound if start_hour <= _get_departure_hour(f) < end_hour]
        
        # Apply filters to return
        if apply_to in ["both", "return"] and filtered_return:
            if filter_type == "cheapest":
                filtered_return.sort(key=lambda f: _parse_price(f.get("price", float('inf'))))
                filtered_return = filtered_return[:keep_count]
            elif filter_type == "direct_only":
                filtered_return = [f for f in filtered_return if not f.get("layovers") or len(f.get("layovers", [])) == 0]
            elif filter_type == "shortest_duration":
                filtered_return.sort(key=lambda f: f.get("total_duration", float('inf')))
                filtered_return = filtered_return[:keep_count]
            elif filter_type == "max_price":
                max_price = float(filter_criteria.get("filter_value", float('inf')))
                filtered_return = [f for f in filtered_return if _parse_price(f.get("price", float('inf'))) <= max_price]
            elif filter_type == "airline":
                airline_name = filter_criteria.get("filter_value", "").lower()
                filtered_return = [f for f in filtered_return if any(
                    segment.get("airline", "").lower() == airline_name 
                    for segment in f.get("flights", [])
                )]
            elif filter_type in ["morning", "afternoon", "evening"]:
                hour_ranges = {
                    "morning": (0, 12),
                    "afternoon": (12, 17),
                    "evening": (17, 24)
                }
                start_hour, end_hour = hour_ranges.get(filter_type, (0, 24))
                def _get_departure_hour(flight):
                    """Extract hour from departure time."""
                    try:
                        first_segment = flight.get("flights", [{}])[0]
                        time_str = first_segment.get("departure_airport", {}).get("time", "")
                        # Handle format like "2025-12-25 05:15" or "05:15"
                        if " " in time_str:
                            time_str = time_str.split(" ")[-1]
                        hour = int(time_str.split(":")[0])
                        return hour
                    except:
                        return 0
                filtered_return = [f for f in filtered_return if start_hour <= _get_departure_hour(f) < end_hour]
        
        print(f"[FILTER] Filtered results: {len(filtered_outbound)} outbound, {len(filtered_return)} return")
        return filtered_outbound, filtered_return
        
    except Exception as e:
        print(f"[FILTER] Error in intelligent filtering: {e}")
        import traceback
        traceback.print_exc()
        # Return original if filtering fails
        return outbound_flights, return_flights


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


def get_conversational_agent_prompt(memories: list = None) -> str:
    """Get the system prompt for the Conversational Agent.
    
    Args:
        memories: List of relevant memories about the user
    """
    memory_section = ""
    if memories and len(memories) > 0:
        memory_section = "\n\nIMPORTANT - Relevant memories about this user (USE THESE IN YOUR RESPONSE):\n" + "\n".join([f"- {mem}" for mem in memories]) + "\n\nWhen providing recommendations:\n- ALWAYS consider and apply these user preferences/constraints\n- NATURALLY mention in your response that the results are based on their preferences\n- For example: 'Based on your preference for morning flights, here are some great options...' or 'I've filtered these restaurants based on your vegetarian preference...'\n- Make it clear that you're using their stored preferences to personalize the results\n- Be natural and conversational - don't make it sound robotic"
        print(f"[MEMORY] Including {len(memories)} memories in conversational agent prompt")
    else:
        print(f"[MEMORY] No memories to include in conversational agent prompt")
    
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

- For flight_result: If it has an "outbound" array with items, those are outbound flight options. If it has a "return" array, those are return flight options.
  ⚠️ IMPORTANT FOR ROUND-TRIP FLIGHTS: 
    * For round-trip flights, the system makes TWO separate one-way calls
    * "outbound" array contains flights from origin to destination (e.g., Beirut → Paris)
    * "return" array contains flights from destination back to origin (e.g., Paris → Beirut)
    * Each array is independent - they are NOT combined packages
    * The frontend will display them in separate sections: "Outbound Flights" and "Return Flights"
    * DO NOT combine them or say "round-trip package" - they are separate one-way flights
  ⚠️ IMPORTANT FOR AIRLINE LOGOS: Each flight segment may have an "airline_logo" field with an image URL
    * If a segment has "airline_logo", include it in markdown format BEFORE the airline name
    * Format like: "![Airline](logo_url) **Airline Name** Flight XX"
    * This will display the airline logo in the chat
  Only report an error if the result has "error": true AND no outbound flights data.

- For visa_result: **CRITICAL**: Check the "result" field FIRST - if it has content (even if "error": true), that contains the visa requirement information. You MUST present ALL available visa information in detail:
  * **Present all sections**: Include all sections from the result field:
    - Travel Summary (whether visa is required or not)
    - Visa Requirements section (all details about visa types, application process, requirements)
    - Passport Requirements section (validity, expiration rules, etc.)
    - Other Conditions/Documents section (any additional requirements, documents needed, special conditions)
    - Any additional important details or notes
  * **Show complete information**: Don't just summarize - present the full details from each section. If the result says "A visa is required" and provides details about the visa application process, passport validity, required documents, etc., include ALL of that information.
  * **Preserve structure**: Keep the logical structure and organization of the information (use section headers, bullet points, etc. as appropriate)
  * **Preserve markdown formatting**: Keep important markdown formatting (like **bold** markers, emojis, section headers) that may be present in the original result
  * **Skip only promotional content**: You can skip promotional content (like eSIM ads) that appears in the result, but include ALL actual visa-related information
  Only report an error if the result has "error": true AND the "result" field is empty or missing.

- For hotel_result: If it has a "hotels" array with items, those are real hotels you found - present them to the user. 
  ⚠️ CRITICAL: Hotels may or may not have price information depending on the search type:
    * If hotels have "roomTypes" or "rates" fields with prices → show the actual prices
    * If hotels DON'T have price fields → DO NOT make up prices! Just show hotel information (name, rating, location, amenities)
    * NEVER hallucinate or invent prices - only show prices if they exist in the data
  Only report an error if the result has "error": true AND no hotels data.

- For tripadvisor_result: If it has a "data" array with items, those are real locations/restaurants you found.
  ⚠️ CRITICAL - READ CAREFULLY: 
    * Your response MUST be VERY SHORT - just 1 sentence maximum
    * Example: "Here are some great restaurants in Paris!" or "I found some excellent restaurants in Paris for you!"
    * DO NOT write ANY text about individual restaurants
    * DO NOT list restaurant names, addresses, or descriptions
    * DO NOT mention photos at all (even if photos are present in the data)
    * DO NOT write anything else - just the simple greeting sentence
    * The frontend will automatically display beautiful cards with ALL information (name, rating, address, photos if available)
    * The [LOCATION_DATA] tag will be added automatically - you don't need to do anything
    * If you write too much, the frontend won't display the cards properly
    * IMPORTANT: Always return a greeting sentence even if photos are not present - locations should still be displayed
    * Example GOOD response: "Here are some excellent restaurants in Paris!"
    * Example BAD response: "I found 10 restaurants. Restaurant 1 is located at... Photo 1, Photo 2..."
  Only report an error if the result has "error": true AND no data.

- For utilities_result: This contains utility information (weather, currency conversion, date/time, eSIM bundles, or holidays). Present the information naturally based on what tool was used:
  * **CRITICAL - MULTIPLE RESULTS**: If utilities_result has "multiple_results": true, it contains a "results" array where each item has "tool", "args", and "result". You MUST check each item in the "results" array:
    - For eSIM bundles: Look for items where "tool" == "get_esim_bundles", then check the nested "result" object for a "bundles" array (path: utilities_result.results[].result.bundles)
    - For holidays: Look for items where "tool" == "get_holidays", then check the nested "result" object for a "holidays" array (path: utilities_result.results[].result.holidays)
    - Process each result and present all information together naturally.
  * **SINGLE RESULT**: If utilities_result does NOT have "multiple_results": true, check directly:
    - For eSIM bundles: Check utilities_result["bundles"] array
    - For holidays: Check utilities_result["holidays"] array
  * For weather: Show temperature, conditions, etc. If multiple weather results, show each location separately.
  * For currency: Show the conversion result.
  * For date/time: Show the current date and time.
  * For eSIM bundles: When you find bundles (either in utilities_result["bundles"] OR in utilities_result.results[].result.bundles), you MUST present ALL available bundles, not just a summary. For each bundle, include:
    - Provider name
    - Plan name/details (e.g., "Europe 100GB – 10 Days")
    - Validity period
    - Price
    - Purchase link as a clickable markdown link: Format like "[Provider Name - Plan Name]($link)" or "Plan Name for $price - [Purchase here]($link)"
    Present them in a clear list format, showing all bundles that are available. DO NOT summarize or say "there are multiple plans available" - actually list them all. If there are many bundles (20+), you can group them by provider or data size, but still show all of them.
    If eSIM data is unavailable (error with "recommended_providers"), present the recommended provider links as clickable options: "Try these eSIM providers: [Airalo](url), [Holafly](url), etc."
  * For holidays: When you find holidays (either in utilities_result["holidays"] OR in utilities_result.results[].result.holidays), present each holiday with its name, date, type (e.g., "National holiday", "Observance"), and description. Format dates in a readable way (e.g., "January 1, 2024" instead of "2024-01-01"). Group holidays by month if there are many.
    ⚠️ CRITICAL: If the user asked to avoid holidays AND you're showing flights/hotels, you MUST explain which dates were holidays and why the selected dates avoid them. Example: "I found that January 1st is New Year's Day (national holiday) in France, so I selected dates from January 8-14 which avoid all holidays."
    Only report an error if the result has "error": true AND no actual data found in either location (direct or nested).

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

Remember: The JSON is invisible to the user - only show the extracted information in a natural, conversational format.""" + memory_section


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
    conversational_feedback_message = state.get("conversational_feedback_message")
    rfi_filtered_message = state.get("rfi_filtered_message")  # Message about filtered non-travel parts
    rfi_status = state.get("rfi_status")  # Check if query was rejected (unsafe/out_of_scope)
    last_response = state.get("last_response", "")  # May contain rejection message from RFI
    relevant_memories = state.get("relevant_memories") or []  # Relevant memories for this user
    
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
    
    # If query was rejected by RFI (unsafe or out of scope), just return the rejection message
    if rfi_status in ["unsafe", "out_of_scope"] and last_response:
        print(f"Conversational Agent: Query was {rfi_status}, returning rejection message")
        updated_state = state.copy()
        updated_state["last_response"] = last_response
        updated_state["route"] = "end"
        return updated_state
    
    # If RFI is asking for missing info, return the pre-prepared question without calling LLM
    # This prevents the LLM from seeing the original user message and answering filtered parts
    if rfi_status == "missing_info" and last_response:
        print("Conversational Agent: RFI asking for missing info, returning pre-prepared question")
        updated_state = state.copy()
        updated_state["last_response"] = last_response
        updated_state["route"] = "end"
        return updated_state
    
    # Prepare messages for LLM
    import json
    
    # Truncate large results to avoid context overflow
    truncated_info = truncate_large_results(collected_info, max_items=20)
    
    user_content = f"""User's original message: {user_message}

Below is the data collected from specialized agents (THIS IS FOR YOUR REFERENCE ONLY - DO NOT INCLUDE IT IN YOUR RESPONSE):
{json.dumps(truncated_info, indent=2, ensure_ascii=False) if truncated_info else "No information was collected from specialized agents."}

IMPORTANT INSTRUCTIONS:
- Extract the relevant information from the JSON above
- Present it in a natural, conversational way
- DO NOT include "Collected_info:", "Based on the information gathered", or any JSON structure in your response
- Start your response directly with the information (e.g., "I've found some great options..." or "Here's what I found...")
- The user should never see the JSON data - only the formatted information
- **If there are errors in the collected data (error: true), explain the specific error to the user in a helpful way, including the error_message and suggestion if available**
- For eSIM bundles: ALWAYS include clickable links using markdown format [text](url) for each bundle's purchase link
- If data was truncated (indicated by "truncated": true or "limited": true), mention that more options are available
- Make sure all links are properly formatted as markdown links so they appear as clickable in the UI"""
    
    # If there's feedback from the feedback node, include it
    if conversational_feedback_message:
        user_content += f"""

FEEDBACK FROM VALIDATOR:
{conversational_feedback_message}

Please revise your response based on this feedback to fix the issues mentioned."""
        print(f"Conversational Agent: Received feedback - {conversational_feedback_message}")
    
    messages = [
        {"role": "system", "content": get_conversational_agent_prompt(memories=relevant_memories)},
        {"role": "user", "content": user_content}
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
    
    # Initialize final_response to avoid UnboundLocalError
    final_response = ""
    
    # CRITICAL: For TripAdvisor results ONLY, skip LLM and generate greeting directly
    tripadvisor_result = collected_info.get("tripadvisor_result")
    if tripadvisor_result and isinstance(tripadvisor_result, dict) and not tripadvisor_result.get("error"):
        locations = tripadvisor_result.get("data", [])
        if locations and len(locations) > 0:
            # Skip LLM entirely - just generate a simple greeting
            import re
            city_name = "this location"
            city_match = re.search(r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', user_message)
            if city_match:
                city_name = city_match.group(1)
            
            location_type = "recommendations"
            user_msg_lower = user_message.lower()
            if "restaurant" in user_msg_lower:
                location_type = "restaurants"
            elif "museum" in user_msg_lower:
                location_type = "museums"
            elif "attraction" in user_msg_lower:
                location_type = "attractions"
            
            if location_type == "recommendations":
                final_response = f"Here are some great recommendations in {city_name}!"
            else:
                final_response = f"Here are some great {location_type} in {city_name}!"
            
            print(f"[CONVERSATIONAL] ✅ SKIPPED LLM for TripAdvisor - generated greeting: '{final_response}'")
        else:
            # No locations, proceed with normal LLM call
            tripadvisor_result = None
    
    # Call LLM to generate response (skip if we already generated TripAdvisor greeting)
    if not (tripadvisor_result and isinstance(tripadvisor_result, dict) and not tripadvisor_result.get("error") and tripadvisor_result.get("data")):
        import traceback
        try:
            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=messages,
                temperature=0.7
            )
            
            message = response.choices[0].message
            raw_response = message.content or "I apologize, but I couldn't generate a response. Please try again."
            
            # Clean the response to remove any JSON/Collected_info references
            final_response = clean_response(raw_response)
        except Exception as e:
            error_msg = str(e)
            error_trace = traceback.format_exc()
            # Log the error for debugging
            print(f"Error in conversational_agent_node: {error_msg}")
            print(f"Traceback: {error_trace}")
            
            # Handle context length errors specifically
            if "context_length" in error_msg.lower() or "maximum context length" in error_msg.lower():
                # Try with simplified messages - just pass a summary
                simplified_messages = [
                    {"role": "system", "content": get_conversational_agent_prompt(memories=relevant_memories)},
                    {
                        "role": "user",
                        "content": f"""User's original message: {user_message}

The system has collected information from specialized agents. Please provide a helpful, natural response based on the available information."""
                    }
                ]
                
                try:
                    response = client.chat.completions.create(
                        model="gpt-4.1-mini",
                        messages=simplified_messages,
                        temperature=0.7
                    )
                    message = response.choices[0].message
                    raw_response = message.content or "I apologize, but I couldn't generate a response. Please try again."
                    final_response = clean_response(raw_response)
                except Exception as inner_e:
                    print(f"Error in simplified message retry: {str(inner_e)}")
                    final_response = "I have the information you requested, but there was a technical issue formatting the response. Please try rephrasing your query or ask for specific details."
            else:
                # Other errors
                final_response = f"I encountered an error while generating the response: {error_msg}. Please try again."
    
    # Prepend filtered message if any non-travel parts were filtered
    if rfi_filtered_message and final_response:
        # Only add if the filtered message isn't already in the response
        if rfi_filtered_message not in final_response:
            final_response = f"{rfi_filtered_message}\n\n{final_response}"
    
    # Add structured data markers for frontend rendering
    # This allows the frontend to display rich UI components for flights and locations
    if collected_info.get("tripadvisor_result"):
        tripadvisor_result = collected_info["tripadvisor_result"]
        print(f"[CONVERSATIONAL] DEBUG: tripadvisor_result exists: {tripadvisor_result is not None}")
        print(f"[CONVERSATIONAL] DEBUG: tripadvisor_result type: {type(tripadvisor_result)}")
        
        if isinstance(tripadvisor_result, dict) and not tripadvisor_result.get("error"):
            locations = tripadvisor_result.get("data", [])
            print(f"[CONVERSATIONAL] DEBUG: locations count: {len(locations) if locations else 0}, type: {type(locations)}")
            
            if locations and len(locations) > 0:
                import json
                print(f"[CONVERSATIONAL] ✅ Adding {len(locations)} locations to [LOCATION_DATA] tag")
                print(f"[CONVERSATIONAL] DEBUG: First location keys: {list(locations[0].keys()) if locations else 'N/A'}")
                
                # ALWAYS add the location data tag AFTER the greeting - this is CRITICAL for frontend display
                location_json = json.dumps(locations, ensure_ascii=False)
                final_response += f"\n\n[LOCATION_DATA]{location_json}[/LOCATION_DATA]"
                print(f"[CONVERSATIONAL] ✅ Successfully added [LOCATION_DATA] tag with {len(locations)} locations")
                print(f"[CONVERSATIONAL] DEBUG: Tag length: {len(location_json)} chars, final_response length: {len(final_response)} chars")
            else:
                print(f"[CONVERSATIONAL] ⚠️ WARNING: tripadvisor_result has no locations data (data={locations}, type={type(locations)})")
                print(f"[CONVERSATIONAL] Full tripadvisor_result: {json.dumps(tripadvisor_result, indent=2, default=str)}")
        else:
            print(f"[CONVERSATIONAL] ⚠️ WARNING: tripadvisor_result is invalid or has error: {tripadvisor_result.get('error') if isinstance(tripadvisor_result, dict) else 'not a dict'}")
    else:
        print(f"[CONVERSATIONAL] DEBUG: No tripadvisor_result in collected_info. Keys: {list(collected_info.keys())}")
    
    if collected_info.get("flight_result"):
        flight_result = collected_info["flight_result"]
        if isinstance(flight_result, dict) and not flight_result.get("error"):
            import json
            # Flight agent now makes 2 separate calls for round-trip, so we just use what we have
            outbound_flights = flight_result.get("outbound", [])
            return_flights = flight_result.get("return", [])
            
            print(f"[CONVERSATIONAL] Flight results: {len(outbound_flights)} outbound, {len(return_flights)} return")
            
            # Intelligently filter flights based on user's message intent
            filtered_outbound, filtered_return = _filter_flights_intelligently(
                user_message, outbound_flights, return_flights
            )
            
            # Combine both outbound and return flights for display
            all_flights = []
            if filtered_outbound:
                # Ensure outbound flights are marked
                for flight in filtered_outbound:
                    if not flight.get("direction"):
                        flight["direction"] = "outbound"
                    if not flight.get("type"):
                        flight["type"] = "Outbound flight"
                all_flights.extend(filtered_outbound)
            if filtered_return:
                # Ensure return flights are marked
                for flight in filtered_return:
                    if not flight.get("direction"):
                        flight["direction"] = "return"
                    if not flight.get("type"):
                        flight["type"] = "Return flight"
                all_flights.extend(filtered_return)
            
            if all_flights:
                # Append structured flight data at the end
                final_response += f"\n\n[FLIGHT_DATA]{json.dumps(all_flights, ensure_ascii=False)}[/FLIGHT_DATA]"
    
    updated_state = state.copy()
    updated_state["last_response"] = final_response
    updated_state["route"] = "end"  # End the workflow
    
    return updated_state








