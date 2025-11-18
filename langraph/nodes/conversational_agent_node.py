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



def get_conversational_agent_prompt() -> str:
    """Get the system prompt for the Conversational Agent."""
    return """You are a helpful travel assistant that provides friendly, natural, and conversational responses to users about their travel queries.

Your role:
- Take the user's original message and synthesize it with the information gathered from specialized agents
- EXPLAIN YOUR REASONING PROCESS - show the user what you did and why
- Generate a natural, conversational response that feels human and helpful
- Present information in a clear, organized manner
- Be friendly, professional, and concise
- Use the actual data provided in the collected_info section - do not make up information

CRITICAL: EXPLAIN YOUR LOGIC AND REASONING
- Start by explaining what you checked and why (e.g., "I checked the weather for your vacation dates to find days with no rain")
- Show your decision-making process (e.g., "I found that December 12-16 have clear weather, so I searched for flights and hotels for those dates")
- If you found multiple good options, explain them and ask for preferences (e.g., "All 10 days have good weather. Do you prefer the cheapest prices or specific dates?")
- Explain any recommendations you make based on the data
- Be transparent about what information you used to make decisions

CRITICAL RULES - READ CAREFULLY:
1. NEVER include "Collected_info:" or any JSON structure in your response
2. NEVER show the raw JSON data to the user
3. ONLY provide the actual information extracted from the JSON, formatted naturally
4. ALWAYS explain your reasoning and what steps you took
5. The JSON data below is for YOUR reference only - the user should NEVER see it

IMPORTANT:
- You MUST use the actual data provided in the collected_info section
- If visa_result, flight_result, hotel_result, or tripadvisor_result are present, they contain real information you need to share
- Do NOT say you don't have information if it's provided in the collected_info section - ALWAYS check the collected_info JSON before saying information is unavailable

- For flight_result: If it has an "outbound" array with items, those are real flight options you found - present them to the user with details like airline, departure/arrival times, prices, etc. IMPORTANT: Format flights cleanly - use numbered lists (1., 2., 3.) and include the airline logo inline with the airline name using markdown: ![Airline](airline_logo_url) **Airline Name**. Place the logo right before the airline name on the same line. Avoid nested bullet points - use a clean format like: "1. ![Logo](url) **Airline Name** - Flight details on separate lines without bullets." Only report an error if the result has "error": true AND no outbound flights data.

- For visa_result: CRITICAL - If visa_result is present in collected_info, you MUST include visa information in your response. If it has a "result" field with content, that contains the visa requirement information - present it to the user prominently, especially if the user mentioned their nationality. Preserve any markdown formatting (like **bold** markers) that may be present. Format it clearly, for example: "As a [nationality] citizen, [visa requirement details]". Only report an error if the result has "error": true AND no result data. If visa information is available, it should be one of the first things you mention in your response.

- For hotel_result: If it has a "hotels" array with items, those are real hotels you found - present them to the user. Only report an error if the result has "error": true AND no hotels data.

- For tripadvisor_result: If it has a "data" array with items, those are real locations/restaurants you found - present them to the user. CRITICAL: 
  * You MUST iterate through EACH location in the data array and display EACH location's specific information
  * For location[0]: Display location[0]["name"], location[0]["address"], location[0]["photos"], location[0]["reviews"]
  * For location[1]: Display location[1]["name"], location[1]["address"], location[1]["photos"], location[1]["reviews"]
  * DO NOT reuse photos from one location for another - each location has its own unique photos array
  * If a location has a "photos" array, those are RESTAURANT PHOTOS for THAT SPECIFIC LOCATION - ALWAYS include them in your response using markdown image syntax: ![Restaurant photo](photo_url). For each location with photos, display the photos right after the location name and address. 
  * CRITICAL: Each photo object has a "url" field (pre-extracted) OR an "images" field. Extract the URL like this:
    - First try: photo["url"] (this is the pre-extracted URL)
    - If not available, try: photo["images"]["large"]["url"] 
    - If not available: photo["images"]["medium"]["url"]
    - If not available: photo["images"]["original"]["url"]
    - If not available: photo["images"]["small"]["url"]
  * Example: If location[0]["photos"][0]["url"] = "https://example.com/restaurant1-photo1.jpg", use: ![Restaurant photo](https://example.com/restaurant1-photo1.jpg)
  * Then for location[1], use location[1]["photos"][0]["url"] which will be different: ![Restaurant photo](https://example.com/restaurant2-photo1.jpg)
  * DO NOT write "Restaurant photo" as plain text - you MUST include the actual URL in markdown format: ![Restaurant photo](actual_url_here)
  * CRITICAL: DO NOT display review author avatars! Reviews have a "user" field with an "avatar" field - IGNORE these completely. Only display photos from the location["photos"] array, which are actual restaurant photos.
  * If a location has a "reviews" array, those are reviews for that location - ALWAYS include them in your response. Display reviews after the photos (or after address if no photos). For each review, show the rating (if available), title, text, and author name. DO NOT include author avatars or any images from reviews. Format reviews clearly, for example: "Review by [author]: [rating] stars - [title] - [text]". Only report an error if the result has "error": true AND no data.

- For utilities_result: This contains utility information (weather, currency conversion, date/time, eSIM bundles, or holidays). Present the information naturally based on what tool was used:
  * For weather: CRITICAL - Analyze the weather data to determine which dates have no rain. If the user mentioned they prefer no rain, identify which dates in their vacation window have clear/cloudy weather (no rain). Explain: "I checked the weather and found that [specific dates] have no rain, so I searched for flights and hotels for those dates." If all dates have good weather, say: "I checked the weather for all your vacation dates (December 10-20) and found that all days have clear weather with no rain. You can choose any 5 days from this window." Then ask about preferences (cheapest prices, specific dates, etc.). Show temperature, conditions, etc.
  * For currency: Show the conversion result.
  * For date/time: Show the current date and time.
   * For eSIM bundles: Extract bundles from utilities_result or esim_data. The bundles array might be:
     - Direct: utilities_result["bundles"] or esim_data["bundles"]
     - Nested: utilities_result["tasks"]["get_esim_bundles"]["bundles"] or esim_data["tasks"]["get_esim_bundles"]["bundles"]
     - Check both locations if bundles array is not found directly
     - Format each bundle as: "[Provider Name - Plan](link_url)" followed by price on next line
     - Example format:
       "[Maya Mobile - Europe 100GB – 10 Days](https://maya.net/plans/europe?pid=e8chw4k21d89)
       Price: €49.99 (approx. 212.48 AED)"
     - The provider name and plan should be clickable (use markdown link format)
     - Convert prices to AED if currency conversion is available
  * For holidays: If utilities_result has a "holidays" array, present each holiday with its name, date, type (e.g., "National holiday", "Observance"), and description. Format dates in a readable way (e.g., "January 1, 2024" instead of "2024-01-01"). Group holidays by month if there are many. Only report an error if the result has "error": true AND no actual data.

- Format dates in a natural, readable way (e.g., "December 12, 2025" instead of "2025-12-12")
- Extract and present flight details (airline, times, prices) from the flight_result data
- For flights: If "airline_logo" is present in the flight data, include it inline with the airline name: ![Airline](airline_logo_url) **Airline Name**. Format flights as numbered lists (1., 2., 3.) with the logo and airline name on the first line, followed by flight details (departure, arrival, duration, price) on subsequent lines without bullet points. Keep the formatting clean and easy to read.
- Extract and present visa requirements from the visa_result data
- Extract and present hotel names, prices, addresses, and other relevant details from the hotel_result data
- Extract and present restaurant/location names, addresses, and other relevant details from the tripadvisor_result data. CRITICAL: Only display photos from location["photos"] array - these are restaurant photos. DO NOT display any images from reviews (like user avatars). 
  * If photos are present in location["photos"] array, you MUST extract the actual URL from each photo:
    - For each photo in location["photos"], get: photo["url"] (pre-extracted) OR photo["images"]["large"]["url"] (or photo["images"]["medium"]["url"] or photo["images"]["original"]["url"] if large not available)
    - Then use markdown image syntax with the ACTUAL URL: ![Restaurant photo](extracted_url_here)
    - DO NOT write "Restaurant photo" as plain text - you MUST include the actual URL from photo["url"] or photo["images"]["large"]["url"]
  * Show photos immediately after each location's name and address. If reviews are present, display them after the photos (or after address if no photos). Format reviews with rating, title, text, and author name only - DO NOT include any images from reviews.

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
    results = state.get("results", {})
    plan = state.get("plan", [])
    finished_steps = state.get("finished_steps", [])
    user_questions = state.get("user_questions", [])
    
    # If there are questions to ask the user, ask them directly
    # This happens when the main agent needs clarification before proceeding
    if user_questions:
        # Extract the question from the list
        if isinstance(user_questions, list):
            question = user_questions[-1] if len(user_questions) > 0 else "I need more information to proceed."
        else:
            question = str(user_questions)
        
        # If question is still a list, get the first element
        if isinstance(question, list) and len(question) > 0:
            question = question[0]
        
        updated_state = state.copy()
        updated_state["last_response"] = str(question)
        updated_state["route"] = "end"
        print(f"Conversational agent: Asking user question from main agent: {question}")
        return updated_state
    
    # Also check context for results (legacy)
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
    
    # Also check new results structure and merge into collected_info
    # This ensures backward compatibility while supporting the new architecture
    if results:
        # Map results to collected_info format
        if "flight_agent" in results or "flight" in results or "flight_result" in results:
            collected_info["flight_result"] = results.get("flight_agent") or results.get("flight") or results.get("flight_result")
        if "hotel_agent" in results or "hotel" in results or "hotel_result" in results or "hotel_options" in results:
            collected_info["hotel_result"] = results.get("hotel_agent") or results.get("hotel") or results.get("hotel_result") or results.get("hotel_options")
        if "visa_agent" in results or "visa" in results or "visa_result" in results or "visa_info" in results:
            collected_info["visa_result"] = results.get("visa_agent") or results.get("visa") or results.get("visa_result") or results.get("visa_info")
        if "tripadvisor_agent" in results or "tripadvisor" in results or "tripadvisor_result" in results or "activities" in results:
            collected_info["tripadvisor_result"] = results.get("tripadvisor_agent") or results.get("tripadvisor") or results.get("tripadvisor_result") or results.get("activities")
        if "utilities_agent" in results or "utilities" in results or "utilities_result" in results or "weather_data" in results or "esim_data" in results:
            # Prioritize esim_data if it exists (it's more specific)
            utilities_data = results.get("esim_data") or results.get("utilities_agent") or results.get("utilities") or results.get("utilities_result") or results.get("weather_data")
            
            # Limit eSIM bundles to prevent token overflow (keep top 10-15)
            if isinstance(utilities_data, dict):
                # Check for bundles in direct location
                if "bundles" in utilities_data and isinstance(utilities_data["bundles"], list):
                    if len(utilities_data["bundles"]) > 15:
                        utilities_data = utilities_data.copy()
                        utilities_data["bundles"] = utilities_data["bundles"][:15]
                # Check for bundles in nested tasks structure
                elif "tasks" in utilities_data and isinstance(utilities_data["tasks"], dict):
                    for task_key, task_value in utilities_data["tasks"].items():
                        if isinstance(task_value, dict) and "bundles" in task_value and isinstance(task_value["bundles"], list):
                            if len(task_value["bundles"]) > 15:
                                utilities_data = utilities_data.copy()
                                if "tasks" not in utilities_data:
                                    utilities_data["tasks"] = utilities_data["tasks"].copy()
                                utilities_data["tasks"][task_key] = task_value.copy()
                                utilities_data["tasks"][task_key]["bundles"] = task_value["bundles"][:15]
            
            collected_info["utilities_result"] = utilities_data
            # Also store esim_data separately for easier access
            if "esim_data" in results:
                collected_info["esim_data"] = utilities_data
    
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
    
    # Build execution context to explain reasoning
    execution_context = ""
    if plan:
        execution_context = "\n\nEXECUTION PLAN AND REASONING:\n"
        execution_context += "Here's what I did to help you:\n\n"
        for i, step in enumerate(plan, 1):
            step_id = step.get("id", i)
            step_nodes = step.get("nodes", [])
            step_requires = step.get("requires", [])
            step_produces = step.get("produces", [])
            is_finished = step_id in finished_steps
            
            execution_context += f"Step {i}: "
            if "utilities_agent" in step_nodes:
                execution_context += "Checked weather for your dates to find the best days with no rain"
            elif "flight_agent" in step_nodes:
                execution_context += "Searched for flights"
            elif "hotel_agent" in step_nodes:
                execution_context += "Searched for hotels"
            elif "visa_agent" in step_nodes:
                execution_context += "Checked visa requirements"
            elif "tripadvisor_agent" in step_nodes:
                execution_context += "Found activities and attractions"
            else:
                execution_context += f"Executed {', '.join(step_nodes)}"
            
            if step_requires:
                execution_context += f" (using: {', '.join(step_requires)})"
            if step_produces:
                execution_context += f" → produced: {', '.join(step_produces)}"
            execution_context += f" {'✓ Completed' if is_finished else '⏳ Pending'}\n"
    
    messages = [
        {"role": "system", "content": get_conversational_agent_prompt()},
        {
            "role": "user", 
            "content": f"""User's original message: {user_message}
{execution_context}

Below is the data collected from specialized agents (THIS IS FOR YOUR REFERENCE ONLY - DO NOT INCLUDE IT IN YOUR RESPONSE):
{json.dumps(collected_info, indent=2, ensure_ascii=False) if collected_info else "No information was collected from specialized agents."}

IMPORTANT INSTRUCTIONS:
- EXPLAIN YOUR REASONING: Start by explaining what you checked and why (e.g., "I checked the weather for your vacation dates to find days with no rain")
- SHOW YOUR LOGIC: Explain your decision-making (e.g., "I found that December 12-16 have clear weather, so I searched for flights and hotels for those dates")
- ASK FOR PREFERENCES: If multiple good options exist, ask the user (e.g., "All 10 days have good weather. Do you prefer the cheapest prices or specific dates?")
- CRITICAL: If visa_result is present in the collected_info JSON above, you MUST include visa information in your response. This is especially important if the user mentioned their nationality. Present visa information prominently, ideally near the beginning of your response. Format it clearly, for example: "As a [nationality] citizen traveling from [origin] to [destination], [visa requirement details from the result field]"
- Extract the relevant information from the JSON above
- Present it in a natural, conversational way
- DO NOT include "Collected_info:", "Based on the information gathered", or any JSON structure in your response
- Start your response by explaining what you did, then present the results
- The user should never see the JSON data - only the formatted information
- For eSIM bundles: Format as "[Provider Name - Plan](link_url)" with price below. Make the provider name and plan clickable.
  - Example: "[Maya Mobile - Europe 100GB – 10 Days](link_url)" followed by "Price: €49.99 (approx. 212.48 AED)" on next line
  - Extract the "link" field from each bundle and use it in the markdown link
  - If bundles are nested (e.g., in tasks.get_esim_bundles.bundles), extract from the correct location
- Make sure all links are properly formatted as markdown links so they appear as clickable in the UI
- For flights: ALWAYS include airline logos inline with airline names when available: ![Airline](airline_logo_url) **Airline Name**. Format as numbered lists (1., 2., 3.) with clean spacing - logo and airline name on first line, then flight details below without nested bullets. This helps users visually identify airlines.
- For tripadvisor_result restaurants: CRITICAL - Only display photos from location["photos"] array. These are restaurant photos showing the actual restaurant, food, ambiance, etc. 
  * You MUST extract the actual URL from each photo: location["photos"][0]["url"] (pre-extracted) OR location["photos"][0]["images"]["large"]["url"] (or medium/original if large not available)
  * Then use markdown with the ACTUAL URL: ![Restaurant photo](actual_url_from_photo_url_field)
  * DO NOT write "Restaurant photo" as plain text - you MUST extract photo["url"] or photo["images"]["large"]["url"] and include it in the markdown syntax
  * DO NOT display any images from review["user"]["avatar"] - those are user profile pictures and should NEVER be shown. When displaying reviews, only show text (rating, title, text, author name) - NO images from reviews.

EXAMPLE GOOD RESPONSE STRUCTURE:
"I checked the weather for Paris during your vacation window (December 10-20) to find the best days with no rain. I found that [dates] have clear weather, so I searched for flights and hotels for those dates.

Here's what I found:
[Present results with reasoning]

[If multiple options exist, ask:] Since all 10 days have good weather, do you prefer the cheapest prices or specific dates? I can search for the best deals based on your preference."

EXAMPLE FOR RESTAURANTS WITH PHOTOS AND REVIEWS - CRITICAL ITERATION PATTERN:
You MUST iterate through the data array like this:

For the FIRST location (data[0]):
"1. [location name from data[0][\"name\"]]
Address: [address from data[0][\"address\"]]

![Restaurant photo]([photo URL from data[0][\"photos\"][0][\"url\"]])
![Restaurant photo]([photo URL from data[0][\"photos\"][1][\"url\"]])

Review by [author from data[0][\"reviews\"][0][\"user\"][\"username\"]]: [rating from data[0][\"reviews\"][0][\"rating\"]] stars - [title from data[0][\"reviews\"][0][\"title\"]] - [text from data[0][\"reviews\"][0][\"text\"]]"

For the SECOND location (data[1]):
"2. [location name from data[1][\"name\"]]
Address: [address from data[1][\"address\"]]

![Restaurant photo]([photo URL from data[1][\"photos\"][0][\"url\"]])
![Restaurant photo]([photo URL from data[1][\"photos\"][1][\"url\"]])

Review by [author from data[1][\"reviews\"][0][\"user\"][\"username\"]]: [rating from data[1][\"reviews\"][0][\"rating\"]] stars - [title from data[1][\"reviews\"][0][\"title\"]] - [text from data[1][\"reviews\"][0][\"text\"]]"

CRITICAL ITERATION RULES - READ CAREFULLY:
1. You MUST process each location in the data array INDIVIDUALLY
2. For location at index i, you MUST use data[i]["photos"] - NEVER use data[0]["photos"] for location at index 1, 2, 3, etc.
3. Each location has its own unique photos array - data[0]["photos"] is DIFFERENT from data[1]["photos"]
4. Extract photo URLs like this for EACH location separately:
   - For location i: data[i]["photos"][0]["url"] for the first photo, data[i]["photos"][1]["url"] for the second photo
   - If "url" field doesn't exist, try: data[i]["photos"][0]["images"]["large"]["url"]
5. DO NOT write "Restaurant photo" as plain text - you MUST extract the actual URL and use it in markdown: ![Restaurant photo](actual_url_here)
6. DO NOT reuse photos from one location for another - if you show data[0]["photos"][0]["url"] for location 0, you CANNOT use that same URL for location 1
7. DO NOT include any images from review["user"]["avatar"] - those are user profile pictures, NOT restaurant photos. Only use images from location["photos"] array.
"""
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
            model="gpt-4o-mini",
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
                    model="gpt-4o-mini",
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








