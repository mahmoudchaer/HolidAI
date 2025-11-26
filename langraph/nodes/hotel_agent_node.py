"""Hotel Agent node for LangGraph orchestration."""

import sys
import os
import json
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "mcp_system"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import AgentState
from clients.hotel_agent_client import HotelAgentClient
# Import memory_filter from the same directory
import sys
import os
_nodes_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _nodes_dir)
from memory_filter import filter_memories_for_agent

# Load environment variables from .env file in main directory
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _load_tool_docs() -> dict:
    """Load tool documentation from JSON file."""
    docs_path = project_root / "mcp_system" / "tool_docs" / "hotel_docs.json"
    try:
        with open(docs_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load hotel tool docs: {e}")
        return {}


def _format_tool_docs(docs: dict) -> str:
    """Format tool documentation for inclusion in prompt."""
    if not docs:
        return ""
    
    formatted = "\n\n=== TOOL DOCUMENTATION ===\n\n"
    
    for tool_name, tool_info in docs.items():
        formatted += f"Tool: {tool_name}\n"
        formatted += f"Description: {tool_info.get('description', 'N/A')}\n\n"
        
        if 'inputs' in tool_info:
            formatted += "Input Parameters:\n"
            for param, desc in tool_info['inputs'].items():
                formatted += f"  - {param}: {desc}\n"
            formatted += "\n"
        
        if 'outputs' in tool_info:
            formatted += "Output Fields:\n"
            for field, desc in tool_info['outputs'].items():
                formatted += f"  - {field}: {desc}\n"
            formatted += "\n"
        
        if 'examples' in tool_info and tool_info['examples']:
            formatted += "Examples:\n"
            for i, example in enumerate(tool_info['examples'][:2], 1):  # Show first 2 examples
                formatted += f"  Example {i}: {example.get('title', 'N/A')}\n"
                formatted += f"    {json.dumps(example.get('body', {}), indent=4)}\n"
            formatted += "\n"
        
        formatted += "---\n\n"
    
    return formatted


def get_hotel_agent_prompt(memories: list = None) -> str:
    """Get the system prompt for the Hotel Agent."""
    docs = _load_tool_docs()
    docs_text = _format_tool_docs(docs)
    
    memory_section = ""
    if memories and len(memories) > 0:
        memory_section = "\n\n⚠️ CRITICAL - USER PREFERENCES (MUST USE WHEN CALLING TOOLS):\n" + "\n".join([f"- {mem}" for mem in memories]) + "\n\nWhen calling tools, you MUST:\n- Filter search results based on these preferences (e.g., if user has budget constraints, use get_hotel_rates_by_price with appropriate price filters)\n- Include preference-related parameters in your tool calls (e.g., min_rating, star_rating, price constraints)\n- These preferences are about THIS USER - always apply them to tool parameters\n"
    
    base_prompt = """You are the Hotel Agent. You MUST use tools to search for hotels. Do NOT respond without calling a tool.

═══════════════════════════════════════════════════════════════════════════════
🚨🚨🚨 DECISION FLOWCHART - FOLLOW THIS EXACTLY 🚨🚨🚨
═══════════════════════════════════════════════════════════════════════════════

STEP 1: Read the user's query carefully.

STEP 2: Does the query contain ANY of these words/phrases?
   - "rooms" / "any rooms" / "rooms available" / "room availability"
   - "rates" / "get me rates" / "room rates" / "rates (rooms)"
   - "prices" / "pricing" / "costs" / "price"
   - "availability" / "available"
   - "prices and so one" / "prices for my trip"

STEP 3: 
   → IF YES → Check if user mentioned a SPECIFIC hotel name (e.g., "Le Meridien Fairway", "Hotel X")
   → IF SPECIFIC HOTEL NAME MENTIONED:
      → Step 3a: First call get_list_of_hotels with hotel_name to get hotel_id
      → Step 3b: Extract "id" field from result
      → Step 3c: Call get_hotel_rates with hotel_ids=[hotel_id] (NOT city_name!)
   → IF NO SPECIFIC HOTEL NAME (just city):
      → Call get_hotel_rates with city_name + country_code
   → IF NO (no pricing/rooms mentioned) → Continue to step 4

STEP 4: Does the user just want to browse/discover hotels (no pricing/rooms mentioned)?
   → IF YES → Use: get_list_of_hotels
   → IF NO → Continue to step 5

STEP 5: Does the user want to BOOK a specific hotel (after seeing results)?
   → IF YES → Use: book_hotel_room

═══════════════════════════════════════════════════════════════════════════════

🚨 CRITICAL REMINDERS:

- If user asks about rooms/rates/prices → get_hotel_rates is the ONLY correct tool
- get_list_of_hotels CANNOT answer questions about pricing or rooms
- **IF USER MENTIONS A SPECIFIC HOTEL NAME** (e.g., "Le Meridien Fairway", "Hotel X"):
  → You MUST first call get_list_of_hotels with hotel_name to get hotel_id
  → Then IMMEDIATELY call get_hotel_rates with hotel_ids=[hotel_id]
  → DO NOT call get_hotel_rates with city_name when a specific hotel is mentioned!
- If user wants to browse hotels in a city (no specific name) → call get_hotel_rates with city_name + country_code
- get_list_of_hotels is ONLY for browsing when user doesn't need pricing, OR as a helper step to get hotel_id

═══════════════════════════════════════════════════════════════════════════════

EXAMPLES (UNDERSTAND THE PATTERN):

✅ "any rooms in this hotel? Le Meridien Fairway prices and so one for my trip"
   → Pattern: "rooms" + "prices" + SPECIFIC HOTEL NAME → First get hotel_id with get_list_of_hotels, then get_hotel_rates with that hotel_id

✅ "get me rates (rooms) for this hotel"
   → Pattern: "rates" + "rooms" → Use get_hotel_rates

✅ "What are the prices for [hotel name]?"
   → Pattern: "prices" → Use get_hotel_rates

✅ "Are there rooms available at [hotel name]?"
   → Pattern: "rooms available" → Use get_hotel_rates

❌ "Find hotels in Dubai" (no pricing/rooms mentioned)
   → Pattern: Just browsing → Use get_list_of_hotels

═══════════════════════════════════════════════════════════════════════════════

TOOL CAPABILITIES (CRITICAL TO UNDERSTAND):

❌ get_list_of_hotels: 
   - Returns: Hotel metadata ONLY (name, address, rating, amenities, photos)
   - Does NOT return: Prices, rates, room availability, room types, booking options
   - Use ONLY when: User wants to browse/discover hotels WITHOUT needing pricing

✅ get_hotel_rates:
   - Returns: Hotels WITH pricing, room types, rates, availability, booking options
   - This is THE ONLY TOOL that returns pricing/room data
   - Use when: User asks about rooms, prices, rates, availability, costs

✅ get_hotel_rates_by_price:
   - Same as get_hotel_rates but sorted by price (cheapest first)
   - Use when: User wants cheapest options

═══════════════════════════════════════════════════════════════════════════════

WORKFLOW FOR get_hotel_rates (when user asks about rooms/prices/rates):

🚨 CRITICAL: If user asks about rooms/prices/rates, you MUST call get_hotel_rates.
DO NOT use get_list_of_hotels - it has NO pricing/room data!

How to call get_hotel_rates:

1. If you have hotel_id (from travel plan or previous results):
   → Call get_hotel_rates with hotel_ids parameter

2. If user mentions a SPECIFIC hotel name (e.g., "Le Meridien Fairway", "Hotel X"):
   → Step 1: Call get_list_of_hotels with hotel_name to find the hotel_id
   → Step 2: Extract the "id" field from the result
   → Step 3: IMMEDIATELY call get_hotel_rates with that hotel_id
   → This ensures you get rates for the EXACT hotel the user asked about!

3. If user wants to browse hotels in a city (no specific hotel name):
   → Call get_hotel_rates with city_name + country_code
   → This returns multiple hotels with pricing for comparison

Required parameters for get_hotel_rates: checkin, checkout, occupancies, guest_nationality
Extract dates from user message or use dates from travel plan/flight context

═══════════════════════════════════════════════════════════════════════════════

PARAMETERS:

Location: city_name + country_code (both required together)
- Dubai → AE, Beirut → LB, Paris → FR, London → GB, New York → US

Dates (for get_hotel_rates): Extract from user message or use dates from travel plan/flight context
- Format: YYYY-MM-DD
- If not specified but user wants pricing/rooms, use smart defaults (7 days from today, 3 nights)

guest_nationality: Required for get_hotel_rates. Extract from context or use "US" as default.

Use tool schemas to understand all parameters. ALWAYS call a tool - do not ask for clarification."""
    
    return base_prompt + memory_section + docs_text


async def hotel_agent_node(state: AgentState) -> AgentState:
    """Hotel Agent node that handles hotel search queries.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with response
    """
    from datetime import datetime
    start_time = datetime.now()
    print(f"[{start_time.strftime('%H:%M:%S.%f')[:-3]}] 🏨 HOTEL AGENT STARTED")
    
    user_message = state.get("user_message", "")
    all_memories = state.get("relevant_memories", [])
    previous_hotel_result = state.get("hotel_result")  # Get previous hotel search results
    
    # Debug: Log what we have
    print(f"[HOTEL AGENT DEBUG] User message: {user_message[:100]}")
    if previous_hotel_result:
        has_error = previous_hotel_result.get("error", False)
        hotels_count = len(previous_hotel_result.get("hotels", []))
        print(f"[HOTEL AGENT DEBUG] Previous hotel_result exists: error={has_error}, hotels_count={hotels_count}")
    else:
        print(f"[HOTEL AGENT DEBUG] No previous hotel_result in state")
    
    # Filter memories to only include hotel-related ones
    relevant_memories = filter_memories_for_agent(all_memories, "hotel")
    if all_memories and not relevant_memories:
        print(f"[MEMORY] Hotel agent: {len(all_memories)} total memories, 0 hotel-related (filtered out non-hotel memories)")
    elif relevant_memories:
        print(f"[MEMORY] Hotel agent: {len(all_memories)} total memories, {len(relevant_memories)} hotel-related")
    
    # Get current step context from execution plan
    execution_plan = state.get("execution_plan", [])
    current_step_index = state.get("current_step", 1) - 1  # current_step is 1-indexed
    
    # If we have an execution plan, use the step description as context
    step_context = ""
    if execution_plan and 0 <= current_step_index < len(execution_plan):
        current_step = execution_plan[current_step_index]
        step_context = current_step.get("description", "")
        print(f"🔍 HOTEL DEBUG - Step context: {step_context}")
    
    # Check if user message contains booking intent (override misleading step context)
    user_lower = user_message.lower()
    booking_keywords_in_message = ["book", "reserve", "confirm booking", "i'll take", "i want to book", "complete the booking", "book a room", "book the", "book a room in"]
    has_booking_intent = any(keyword in user_lower for keyword in booking_keywords_in_message)
    
    # If user says "book" but step context says "search", override the step context
    if has_booking_intent:
        if "search" in step_context.lower() or ("search" in step_context.lower() and "book" in step_context.lower()):
            print(f"🚨 OVERRIDE: User wants to BOOK - overriding misleading step context that mentions 'search'")
            # Extract hotel name from step context if mentioned
            hotel_name_match = None
            if "hotel" in step_context.lower():
                # Try to extract hotel name (e.g., "Hotel Napoleon Beirut")
                import re
                hotel_match = re.search(r'hotel\s+([A-Z][a-zA-Z\s]+)', step_context, re.IGNORECASE)
                if hotel_match:
                    hotel_name_match = hotel_match.group(1).strip()
            if hotel_name_match:
                step_context = f"User wants to BOOK {hotel_name_match}. Extract hotel_id and rate_id from previous results or search first if needed."
            else:
                step_context = f"User wants to BOOK a hotel room. Extract hotel_id and rate_id from previous results or search first if needed."
    
    # Try to extract hotel results from memories if not in state
    if not previous_hotel_result and relevant_memories:
        print(f"[HOTEL AGENT DEBUG] Trying to extract hotel results from memories...")
        # Look for hotel results in memory context
        for memory in relevant_memories:
            if isinstance(memory, str) and "hotel" in memory.lower():
                # Check if memory contains hotel list with hotel IDs
                # This is a fallback - ideally previous_hotel_result should be in state
                print(f"[HOTEL AGENT DEBUG] Found hotel-related memory, but cannot parse structured data from it")
    
    # Build the message to send to LLM
    # Include previous hotel results if available (for booking scenarios)
    previous_results_context = ""
    if previous_hotel_result and not previous_hotel_result.get("error"):
        hotels = previous_hotel_result.get("hotels", [])
        if hotels:
            previous_results_context = f"""

=== PREVIOUS HOTEL SEARCH RESULTS (for booking reference) ===
You have {len(hotels)} hotel(s) from a previous search. When user wants to book, extract hotel_id and rate_id from these results:

"""
            # Include first 3 hotels with key booking fields
            for i, hotel in enumerate(hotels[:3], 1):
                hotel_id = hotel.get("hotelId") or hotel.get("id") or hotel.get("hotel_id")
                hotel_name = hotel.get("name", "Unknown")
                
                # Try to find rate_id (optionRefId) in the hotel structure
                rate_id = None
                option_ref_id = None
                if "roomTypes" in hotel and isinstance(hotel["roomTypes"], list):
                    for room_type in hotel["roomTypes"]:
                        if "rates" in room_type and isinstance(room_type["rates"], list):
                            for rate in room_type["rates"]:
                                if "optionRefId" in rate:
                                    option_ref_id = rate["optionRefId"]
                                    break
                                if "rateId" in rate:
                                    rate_id = rate["rateId"]
                                    break
                            if option_ref_id or rate_id:
                                break
                
                if not option_ref_id and not rate_id:
                    option_ref_id = hotel.get("optionRefId")
                    rate_id = hotel.get("rateId")
                
                booking_rate_id = option_ref_id or rate_id
                
                previous_results_context += f"Hotel {i}: {hotel_name}\n"
                previous_results_context += f"  - hotel_id: {hotel_id}\n"
                if booking_rate_id:
                    previous_results_context += f"  - rate_id (optionRefId): {booking_rate_id}\n"
                else:
                    previous_results_context += f"  - rate_id: NOT FOUND (may need to search rates again)\n"
                previous_results_context += "\n"
            
            previous_results_context += """
🚨 CRITICAL FOR BOOKING REQUESTS:
- If user says "book", "reserve", "I'll take", "confirm booking" → YOU MUST use book_hotel_room (NOT get_hotel_rates!)
- When user says "book this hotel" or "book hotel X", match the hotel name to the list above
- Extract the hotel_id and rate_id (optionRefId) from the matching hotel
- Use these IDs in the book_hotel_room tool call
- If rate_id is not found, you may need to call get_hotel_rates again for that specific hotel_id
- DO NOT call get_hotel_rates when user wants to BOOK - they've already seen the hotels!

"""
    
    # Check if this is a booking request (user says "book")
    # Check booking intent from user message first
    user_lower = user_message.lower()
    booking_keywords = ["book", "reserve", "confirm booking", "i'll take", "i want to book", "complete the booking", "book a room", "book the", "book a room in"]
    is_booking_request = any(keyword in user_lower for keyword in booking_keywords)
    
    # Check if we have previous results
    has_previous_results = False
    if previous_hotel_result and not previous_hotel_result.get("error"):
        hotels = previous_hotel_result.get("hotels", [])
        if hotels:
            has_previous_results = True
            print(f"[HOTEL AGENT DEBUG] Booking request detected with {len(hotels)} previous hotel results available")
    
    if is_booking_request:
        # Emphasize booking when user says "book"
        if has_previous_results:
            booking_emphasis = """

🚨🚨🚨 BOOKING REQUEST DETECTED 🚨🚨🚨
User wants to COMPLETE A BOOKING, not search for hotels!
YOU MUST use book_hotel_room tool (NOT get_hotel_rates!)
Previous hotel results are available above - extract hotel_id and rate_id from them!

"""
            previous_results_context = booking_emphasis + previous_results_context
        else:
            # No previous results, but user wants to book - we need to search first OR extract from memories
            booking_emphasis = """

🚨🚨🚨 BOOKING REQUEST DETECTED 🚨🚨🚨
User wants to COMPLETE A BOOKING, not search for hotels!
However, no previous hotel results found in state. 

OPTIONS:
1. If hotel name is mentioned (e.g., "ODAN Apart"), you may need to search for rates first using get_hotel_rates with the hotel name
2. OR if you can extract hotel_id from memories/context, use book_hotel_room directly

⚠️ IMPORTANT: If you search first, make sure to extract hotel_id and rate_id from the results for the booking!

"""
            previous_results_context = booking_emphasis + previous_results_context
    
    if step_context:
        # Use step description as primary instruction, with user message as background
        # If booking is detected, emphasize it more strongly in the message
        if is_booking_request:
            agent_message = f"""Current task: {step_context}

🚨 CRITICAL: User wants to BOOK a hotel - this is a BOOKING request!
{previous_results_context}
User's request: {user_message}

INSTRUCTIONS:
- If you have previous hotel results above, extract hotel_id and rate_id and call book_hotel_room NOW
- If you don't have previous results, search first to get hotel_id and rate_id, THEN immediately call book_hotel_room
- DO NOT just search and stop - you MUST complete the booking!"""
        else:
            agent_message = f"""Current task: {step_context}

Background context from user: {user_message}
{previous_results_context}
Focus on the hotel search task described above."""
    else:
        # Include previous results context even without step context
        agent_message = user_message + previous_results_context
    updated_state = state.copy()
    
    # Always use LLM to extract parameters from user message
    # LLM has access to tool documentation and can intelligently extract parameters
    # Get tools available to hotel agent
    tools = await HotelAgentClient.list_tools()
    
    # Prepare messages for LLM
    prompt = get_hotel_agent_prompt(memories=relevant_memories)
    
    # If this is a booking request, add extra emphasis to the system prompt
    if is_booking_request:
        booking_system_override = """

🚨🚨🚨 CRITICAL: USER WANTS TO BOOK A HOTEL 🚨🚨🚨
The user has said they want to BOOK a specific hotel.
You MUST use book_hotel_room tool - NOT get_hotel_rates!
Previous hotel search results are available in the user message below.
Extract hotel_id and rate_id from those results and call book_hotel_room.

DO NOT call get_hotel_rates - the user has already seen the hotels!

"""
        prompt = booking_system_override + prompt
    
    # Enhance user message with hotel-related memories if available
    if relevant_memories:
        print(f"[MEMORY] Hotel agent using {len(relevant_memories)} hotel-related memories: {relevant_memories}")
        # Add memories to user message to ensure they're considered in tool calls
        memory_context = "\n\nIMPORTANT USER PREFERENCES (MUST APPLY TO TOOL CALLS):\n" + "\n".join([f"- {mem}" for mem in relevant_memories])
        agent_message = agent_message + memory_context
    
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": agent_message}
    ]
    
    # Log booking detection for debugging
    if is_booking_request:
        print(f"🚨 BOOKING REQUEST DETECTED - User message contains booking keywords")
        if previous_hotel_result:
            print(f"   Previous results: {len(previous_hotel_result.get('hotels', []))} hotels available")
        else:
            print(f"   Previous results: No previous hotel results found")
        print(f"   Expected tool: book_hotel_room (NOT get_hotel_rates)")
    
    # Build function calling schema for hotel tools
    functions = []
    
    def _sanitize_schema(schema: dict) -> dict:
        """Ensure arrays have 'items' and sanitize nested schemas."""
        if not isinstance(schema, dict):
            return schema
        sanitized = dict(schema)
        schema_type = sanitized.get("type")
        if schema_type == "array" and "items" not in sanitized:
            sanitized["items"] = {"type": "object"}  # safe default
        # Recurse into object properties
        if schema_type == "object":
            props = sanitized.get("properties", {})
            for key, val in list(props.items()):
                props[key] = _sanitize_schema(val)
            sanitized["properties"] = props
        # Recurse into array items
        if "items" in sanitized and isinstance(sanitized["items"], dict):
            sanitized["items"] = _sanitize_schema(sanitized["items"])
        return sanitized

    # Build function list - prioritize book_hotel_room if booking is detected
    tool_list = []
    for tool in tools:
        if tool["name"] in ["get_hotel_rates", "get_hotel_rates_by_price", "get_hotel_details", "get_list_of_hotels", "book_hotel_room"]:
            tool_list.append(tool)
    
    # If booking is detected, put book_hotel_room first in the list
    if is_booking_request:
        tool_list.sort(key=lambda t: 0 if t["name"] == "book_hotel_room" else 1)
        print(f"🚨 BOOKING DETECTED - Prioritizing book_hotel_room tool")
    
    for tool in tool_list:
        input_schema = tool.get("inputSchema", {})
        input_schema = _sanitize_schema(input_schema)
        
        # Override descriptions to make tool selection crystal clear
        description = tool.get("description", "Search for hotels")
        if tool["name"] == "get_list_of_hotels":
            description = "🔍 BROWSE hotels by location (NO dates needed). ⚠️⚠️⚠️ CRITICAL: This tool RETURNS NO PRICING DATA, NO ROOM AVAILABILITY, NO RATES, NO ROOM TYPES! ⚠️⚠️⚠️ It only returns hotel metadata (name, address, amenities, rating, photos). DO NOT USE THIS TOOL if the user asks about 'rooms', 'rates', 'prices', 'availability', 'costs', 'get me rates', 'any rooms', or mentions dates with a hotel name. For ANY pricing/room queries, you MUST use get_hotel_rates instead!"
        elif tool["name"] == "get_hotel_rates":
            if is_booking_request:
                description = "❌ DO NOT USE - User wants to BOOK, not search! Use book_hotel_room instead!"
            else:
                description = "💰💰💰 USE THIS TOOL when user asks about ROOMS, PRICES, RATES, or AVAILABILITY! ⚠️⚠️⚠️ THIS IS THE ONLY TOOL THAT RETURNS PRICING DATA, ROOM TYPES, RATES, AND AVAILABILITY! ⚠️⚠️⚠️ SEARCH for hotel rates with prices (dates REQUIRED). Returns hotels with roomTypes and rates including prices. If user says 'any rooms?', 'get me rates', 'prices', 'rates', 'availability', 'costs', or mentions dates with a hotel name, you MUST use this tool. get_list_of_hotels CANNOT provide pricing/rates/rooms - it only has metadata! For SPECIFIC hotels: first get hotel_id with get_list_of_hotels, then call this tool with hotel_ids. For city-wide searches: call with city_name + country_code."
        elif tool["name"] == "get_hotel_rates_by_price":
            if is_booking_request:
                description = "❌ DO NOT USE - User wants to BOOK, not search! Use book_hotel_room instead!"
            else:
                description = "💰 SEARCH for hotel RATES sorted by price (dates REQUIRED). Use ONLY when user wants cheapest options with dates. NOT for booking!"
        elif tool["name"] == "get_hotel_details":
            description = "🏨 Get details of a SPECIFIC hotel by ID (hotel_id REQUIRED). Use when you already have a hotel_id."
        elif tool["name"] == "book_hotel_room":
            if is_booking_request:
                description = "💳💳💳 USE THIS TOOL NOW! COMPLETE BOOKING - Book a hotel room with payment. User wants to BOOK a specific hotel. Extract hotel_id and rate_id from previous results above. REQUIRED parameters: hotel_id, rate_id, checkin, checkout, occupancies, guest info, payment info."
            else:
                description = "💳 COMPLETE BOOKING - Book a hotel room with payment (hotel_id and rate_id REQUIRED). USE THIS when user says 'book this hotel', 'book hotel X', 'reserve this room', or 'complete the booking' AFTER seeing hotel options. NOT for searching - that's get_hotel_rates! Requires rate_id (optionRefId) from previous get_hotel_rates response."
        
        functions.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": description,
                "parameters": input_schema
            }
        })
    
    # Call LLM with function calling - require tool use when functions are available
    if functions:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            tools=functions,
            tool_choice="required"  # Force tool call when tools are available
        )
    else:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages
        )
    
    message = response.choices[0].message
    
    # Check if LLM wants to call a tool
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        tool_name = tool_call.function.name
        
        # CRITICAL: If booking is detected but agent tries to search, warn and guide it
        if is_booking_request and tool_name in ["get_hotel_rates", "get_hotel_rates_by_price"]:
            print(f"⚠️⚠️⚠️ WARNING: Booking detected but agent chose {tool_name} instead of book_hotel_room!")
            print(f"   This is OK if hotel_id/rate_id are missing - agent needs to search first to get them")
            print(f"   After search completes, agent should call book_hotel_room with the extracted IDs")
        
        if tool_name in ["get_hotel_rates", "get_hotel_rates_by_price", "get_hotel_details", "get_list_of_hotels", "book_hotel_room"]:
            import json
            args = json.loads(tool_call.function.arguments)
            
            # LLM has extracted all parameters from user message - use them directly
            # Call the hotel tool via MCP
            try:
                # Make a copy of args to avoid modifying the original
                tool_args = args.copy()
                
                # Extract filter parameters (don't pass them to the tool)
                max_price = tool_args.pop("max_price", None) or tool_args.pop("budget", None)
                min_stars = tool_args.pop("min_stars", None) or tool_args.pop("star_rating", None) or tool_args.pop("stars", None)
                
                # If booking is detected and agent is searching, ensure location is correct
                if is_booking_request and tool_name in ["get_hotel_rates", "get_hotel_rates_by_price"]:
                    # Extract location from user message or step context
                    if "beirut" in user_lower or "beirut" in step_context.lower():
                        if "city_name" not in tool_args or not tool_args.get("city_name"):
                            tool_args["city_name"] = "Beirut"
                        if "country_code" not in tool_args or not tool_args.get("country_code"):
                            tool_args["country_code"] = "LB"
                        print(f"🔧 FIXED: Added location (Beirut, LB) to search for booking")
                    
                    # If hotel_ids is a hotel name (not an ID), remove it and use city/country instead
                    if "hotel_ids" in tool_args:
                        hotel_ids = tool_args.get("hotel_ids")
                        if isinstance(hotel_ids, str) and (" " in hotel_ids or len(hotel_ids) > 20):
                            # This looks like a hotel name, not an ID
                            print(f"🔧 FIXED: hotel_ids looks like a name '{hotel_ids}', removing it and using city/country search")
                            tool_args.pop("hotel_ids", None)
                            # Ensure city/country are set
                            if "city_name" not in tool_args:
                                tool_args["city_name"] = "Beirut"
                            if "country_code" not in tool_args:
                                tool_args["country_code"] = "LB"
                
                # Call the hotel tool without filter parameters
                hotel_result = await HotelAgentClient.invoke(tool_name, **tool_args)
                
                # Check if the tool call itself had an error
                if hotel_result.get("error"):
                    # Store error result with full error details (error_code, error_message, suggestion)
                    # Preserve all error information for better user feedback
                    error_result = {
                        "error": True,
                        "error_code": hotel_result.get("error_code", "UNKNOWN_ERROR"),
                        "error_message": hotel_result.get("error_message", "An error occurred during hotel search"),
                        "suggestion": hotel_result.get("suggestion", "Please try again or contact support"),
                        "hotels": []
                    }
                    updated_state["hotel_result"] = error_result
                    print(f"Hotel agent: Error occurred - {error_result.get('error_code')}: {error_result.get('error_message')}")
                    # No need to set route - using add_edge means we automatically route to join_node
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    print(f"[{end_time.strftime('%H:%M:%S.%f')[:-3]}] 🏨 HOTEL AGENT COMPLETED (Duration: {duration:.3f}s)")
                    return updated_state
                
                # Handle booking tool separately - no enrichment needed
                if tool_name == "book_hotel_room":
                    # Store booking result directly
                    updated_state["hotel_result"] = hotel_result
                    print(f"Hotel agent: Booking completed - Booking ID: {hotel_result.get('booking_id', 'N/A')}, Confirmation: {hotel_result.get('confirmation_code', 'N/A')}")
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    print(f"[{end_time.strftime('%H:%M:%S.%f')[:-3]}] 🏨 HOTEL AGENT COMPLETED (Duration: {duration:.3f}s)")
                    return updated_state
                
                # Ensure error flag is explicitly False if we have hotels
                if hotel_result.get("hotels") and len(hotel_result.get("hotels", [])) > 0:
                    hotel_result["error"] = False
                
                # Fetch hotel details for top hotels and apply filters (same logic as delegated path)
                # Note: get_list_of_hotels already returns enriched data, so skip enrichment for it
                hotels = hotel_result.get("hotels", [])
                if hotels and tool_name not in ["get_hotel_details", "get_list_of_hotels"]:
                    # Convert max_price to float if it's a string
                    if max_price and isinstance(max_price, str):
                        try:
                            max_price = float(max_price.replace("$", "").replace(",", "").strip())
                        except (ValueError, AttributeError):
                            max_price = None
                    
                    # Convert min_stars to int/float if it's a string
                    if min_stars and isinstance(min_stars, str):
                        try:
                            min_stars = float(min_stars.replace("star", "").replace("s", "").strip())
                        except (ValueError, AttributeError):
                            min_stars = None
                    
                    # Fetch details for top hotels (limit to avoid too many API calls)
                    # Wrap enrichment in try-except to ensure we always store the result
                    try:
                        MAX_DETAILS_TO_FETCH = 10
                        enriched_hotels = []
                        
                        for hotel in hotels[:MAX_DETAILS_TO_FETCH]:
                            hotel_id = hotel.get("hotelId")
                            if not hotel_id:
                                # If no hotel_id, still include the hotel with rate info
                                enriched_hotels.append(hotel)
                                continue
                            
                            try:
                                # Fetch hotel details
                                details_result = await HotelAgentClient.invoke(
                                    "get_hotel_details",
                                    hotel_id=hotel_id
                                )
                                
                                if not details_result.get("error") and details_result.get("hotel"):
                                    hotel_details = details_result.get("hotel")
                                    # Merge details with rate info - ensure name is always set
                                    hotel["name"] = hotel_details.get("name") or hotel_details.get("hotelName") or hotel.get("name", "Unknown Hotel")
                                    hotel["address"] = hotel_details.get("address") or hotel_details.get("location") or hotel.get("address")
                                    hotel["rating"] = hotel_details.get("rating") or hotel_details.get("starRating") or hotel_details.get("stars") or hotel.get("rating")
                                    hotel["description"] = hotel_details.get("description") or hotel.get("description")
                                    # Also store hotel_id for reference
                                    hotel["hotel_id"] = hotel_id
                                
                            except Exception as detail_error:
                                # If details fetch fails, continue with rate info only
                                print(f"Warning: Failed to fetch details for hotel {hotel_id}: {detail_error}")
                                pass
                            
                            # Extract price for filtering (find minimum price)
                            price = None
                            min_price_found = float('inf')
                            if "roomTypes" in hotel and isinstance(hotel["roomTypes"], list):
                                for room_type in hotel["roomTypes"]:
                                    if "offerRetailRate" in room_type and "amount" in room_type["offerRetailRate"]:
                                        try:
                                            p = float(room_type["offerRetailRate"]["amount"])
                                            if p < min_price_found:
                                                min_price_found = p
                                                price = p
                                        except (ValueError, TypeError):
                                            pass
                                    if "rates" in room_type and isinstance(room_type["rates"], list):
                                        for rate in room_type["rates"]:
                                            if "retailRate" in rate and "total" in rate["retailRate"]:
                                                if isinstance(rate["retailRate"]["total"], list) and len(rate["retailRate"]["total"]) > 0:
                                                    try:
                                                        p = float(rate["retailRate"]["total"][0].get("amount", 0))
                                                        if p > 0 and p < min_price_found:
                                                            min_price_found = p
                                                            price = p
                                                    except (ValueError, TypeError):
                                                        pass
                            
                            # Apply filters
                            if max_price and price and price > max_price:
                                continue
                            
                            if min_stars:
                                hotel_stars = hotel.get("rating") or hotel.get("starRating") or hotel.get("stars")
                                if hotel_stars:
                                    try:
                                        hotel_stars_float = float(hotel_stars)
                                        if hotel_stars_float < min_stars:
                                            continue
                                    except (ValueError, TypeError):
                                        pass
                            
                            enriched_hotels.append(hotel)
                        
                        # Update hotel_result with enriched hotels
                        # If all hotels were filtered out, keep at least the original hotels list
                        if enriched_hotels:
                            hotel_result["hotels"] = enriched_hotels
                            hotel_result["_filtered"] = len(hotels) - len(enriched_hotels)
                        else:
                            # If all filtered out, keep original hotels (filtering might have been too strict)
                            hotel_result["hotels"] = hotels
                            hotel_result["_filtered"] = len(hotels)
                        
                        # CRITICAL: If booking was detected and we just searched, try to continue with booking
                        if is_booking_request and tool_name in ["get_hotel_rates", "get_hotel_rates_by_price"]:
                            print(f"🚨 BOOKING DETECTED: Just completed search, checking if we can proceed with booking...")
                            # Find the hotel the user wants (second hotel = index 1, first = index 0)
                            target_hotel = None
                            if hotels:
                                # User said "second hotel" or "first hotel" - extract from user message
                                if "second" in user_lower or "2" in user_lower or "two" in user_lower:
                                    if len(hotels) > 1:
                                        target_hotel = hotels[1]  # Second hotel (index 1)
                                        print(f"   Selected second hotel: {target_hotel.get('name', 'Unknown')}")
                                    else:
                                        target_hotel = hotels[0]  # Fallback to first if only one
                                elif "first" in user_lower or "1" in user_lower or "one" in user_lower:
                                    target_hotel = hotels[0]
                                    print(f"   Selected first hotel: {target_hotel.get('name', 'Unknown')}")
                                else:
                                    # Try to match by hotel name from step context or user message
                                    hotel_name_to_find = None
                                    if "hotel napoleon" in user_lower or "napoleon" in user_lower:
                                        hotel_name_to_find = "napoleon"
                                    elif "odan" in user_lower:
                                        hotel_name_to_find = "odan"
                                    
                                    if hotel_name_to_find:
                                        for hotel in hotels:
                                            hotel_name = hotel.get("name", "").lower()
                                            if hotel_name_to_find in hotel_name:
                                                target_hotel = hotel
                                                print(f"   Matched hotel by name: {hotel.get('name', 'Unknown')}")
                                                break
                                    
                                    # If no match, use first hotel
                                    if not target_hotel:
                                        target_hotel = hotels[0]
                                        print(f"   No specific hotel mentioned, using first hotel: {target_hotel.get('name', 'Unknown')}")
                            
                            if target_hotel:
                                hotel_id = target_hotel.get("hotelId") or target_hotel.get("id") or target_hotel.get("hotel_id")
                                # Try to find rate_id
                                rate_id = None
                                option_ref_id = None
                                if "roomTypes" in target_hotel and isinstance(target_hotel["roomTypes"], list):
                                    for room_type in target_hotel["roomTypes"]:
                                        if "rates" in room_type and isinstance(room_type["rates"], list):
                                            for rate in room_type["rates"]:
                                                if "optionRefId" in rate:
                                                    option_ref_id = rate["optionRefId"]
                                                    break
                                                if "rateId" in rate:
                                                    rate_id = rate["rateId"]
                                                    break
                                            if option_ref_id or rate_id:
                                                break
                                
                                if not option_ref_id and not rate_id:
                                    option_ref_id = target_hotel.get("optionRefId")
                                    rate_id = target_hotel.get("rateId")
                                
                                booking_rate_id = option_ref_id or rate_id
                                
                                if hotel_id and booking_rate_id:
                                    print(f"   ✅ Found hotel_id={hotel_id}, rate_id={booking_rate_id}")
                                    
                                    # Check if payment info is in the user message
                                    has_payment_info = False
                                    payment_info = {}
                                    
                                    # Extract payment info from user message if available
                                    user_lower_for_payment = user_message.lower()
                                    # Look for card number (typically 13-19 digits)
                                    import re
                                    card_match = re.search(r'card\s*(?:number|#|num)?\s*(?:is|:)?\s*(\d{13,19})', user_lower_for_payment)
                                    expiry_match = re.search(r'expir(?:y|ation)?\s*(?:is|:)?\s*(\d{1,2}[/-]\d{2,4})', user_lower_for_payment)
                                    cvv_match = re.search(r'cvv\s*(?:is|:)?\s*(\d{3,4})', user_lower_for_payment)
                                    name_match = re.search(r'(?:name|card\s*holder)\s*(?:is|:)?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)', user_message)
                                    email_match = re.search(r'email\s*(?:is|:)?\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', user_message, re.IGNORECASE)
                                    
                                    if card_match and expiry_match and cvv_match:
                                        payment_info["card_number"] = card_match.group(1)
                                        payment_info["card_expiry"] = expiry_match.group(1).replace("-", "/")
                                        payment_info["card_cvv"] = cvv_match.group(1)
                                        if name_match:
                                            payment_info["card_holder_name"] = name_match.group(1)
                                        has_payment_info = True
                                        print(f"   ✅ Payment info found in user message!")
                                    
                                    # Extract guest info
                                    guest_info = {}
                                    if email_match:
                                        guest_info["email"] = email_match.group(1)
                                    if name_match:
                                        full_name = name_match.group(1).split()
                                        if len(full_name) >= 2:
                                            guest_info["first_name"] = full_name[0]
                                            guest_info["last_name"] = " ".join(full_name[1:])
                                    
                                    # Extract dates from step context or tool args
                                    checkin_date = tool_args.get("checkin") or "2025-12-10"
                                    checkout_date = tool_args.get("checkout") or "2025-12-12"
                                    occupancies_list = tool_args.get("occupancies", [{"adults": 1}])
                                    
                                    if has_payment_info and guest_info.get("email") and guest_info.get("first_name"):
                                        print(f"   🚀 Attempting to complete booking automatically...")
                                        try:
                                            booking_result = await HotelAgentClient.invoke(
                                                "book_hotel_room",
                                                hotel_id=hotel_id,
                                                rate_id=booking_rate_id,
                                                checkin=checkin_date,
                                                checkout=checkout_date,
                                                occupancies=occupancies_list,
                                                guest_first_name=guest_info.get("first_name", "Guest"),
                                                guest_last_name=guest_info.get("last_name", "User"),
                                                guest_email=guest_info.get("email"),
                                                card_number=payment_info["card_number"],
                                                card_expiry=payment_info["card_expiry"],
                                                card_cvv=payment_info["card_cvv"],
                                                card_holder_name=payment_info.get("card_holder_name", guest_info.get("first_name", "Guest") + " " + guest_info.get("last_name", "User"))
                                            )
                                            
                                            if not booking_result.get("error"):
                                                print(f"   ✅ Booking completed successfully!")
                                                updated_state["hotel_result"] = booking_result
                                                end_time = datetime.now()
                                                duration = (end_time - start_time).total_seconds()
                                                print(f"[{end_time.strftime('%H:%M:%S.%f')[:-3]}] 🏨 HOTEL AGENT COMPLETED (Duration: {duration:.3f}s)")
                                                return updated_state
                                            else:
                                                print(f"   ⚠️  Booking failed: {booking_result.get('error_message')}")
                                        except Exception as booking_error:
                                            print(f"   ⚠️  Error attempting automatic booking: {booking_error}")
                                    else:
                                        print(f"   ⚠️  Payment info missing - need: card number, expiry, CVV, guest name, email")
                                        print(f"   🔗 Generating secure booking URL for payment collection")
                                        # Store booking intent in hotel_result so conversational agent can show booking link
                                        hotel_result["_booking_intent"] = True
                                        hotel_result["_booking_hotel_id"] = hotel_id
                                        hotel_result["_booking_rate_id"] = booking_rate_id
                                        hotel_result["_booking_hotel_name"] = target_hotel.get("name", "Selected Hotel")
                                        hotel_result["_booking_checkin"] = checkin_date
                                        hotel_result["_booking_checkout"] = checkout_date
                                        hotel_result["_booking_price"] = target_hotel.get("price") or "N/A"
                                else:
                                    print(f"   ⚠️  Cannot proceed with booking: Missing hotel_id or rate_id")
                                    print(f"   hotel_id={hotel_id}, rate_id={booking_rate_id}")
                    except Exception as enrich_error:
                        # If enrichment fails completely, keep the original result
                        print(f"Warning: Hotel enrichment failed: {enrich_error}")
                        # Keep the original hotels result - it's better than nothing
                        hotel_result["hotels"] = hotels
                
                elif hotels and tool_name == "get_list_of_hotels":
                    # get_list_of_hotels already returns complete hotel data, no enrichment needed
                    hotel_result["hotels"] = hotels
                    print(f"Hotel agent: get_list_of_hotels returned {len(hotels)} hotel(s) (no enrichment needed)")
                    # Note: Summarization will happen below in the common code path
                
                # Store the result directly in state for parallel execution
                # Even if enrichment failed or no hotels found, store the result
                # Ensure error flag is set correctly based on whether we have hotels
                hotels_count = len(hotel_result.get("hotels", []))
                if hotels_count > 0:
                    hotel_result["error"] = False
                elif not hotel_result.get("error"):
                    # If no hotels but no explicit error, set error flag
                    hotel_result["error"] = True
                    hotel_result["error_message"] = "No hotels found matching the criteria"
                
                # Debug: Log what we're storing
                print(f"Hotel agent: Storing result with {hotels_count} hotel(s), error: {hotel_result.get('error', False)}")
                if hotels_count > 0:
                    hotel_names = [h.get("name", "Unknown") for h in hotel_result.get("hotels", [])[:3]]
                    print(f"Hotel agent: Hotel names: {hotel_names}")
                
                # ===== INTELLIGENT SUMMARIZATION =====
                # Summarize results before passing to conversational agent
                if hotels_count > 0 and not hotel_result.get("error"):
                    try:
                        from utils.result_summarizer import summarize_hotel_results
                        print(f"🧠 Hotel agent: Summarizing {hotels_count} hotels for conversational agent...")
                        summarized = await summarize_hotel_results(
                            hotel_result.get("hotels", []),
                            user_message,
                            step_context
                        )
                        # Replace hotels with summarized version
                        hotel_result["hotels"] = summarized.get("hotels", [])
                        hotel_result["original_count"] = hotels_count
                        hotel_result["summarized_count"] = len(summarized.get("hotels", []))
                        hotel_result["summary"] = summarized.get("summary", "")
                        print(f"✅ Hotel agent: Summarized from {hotels_count} to {hotel_result['summarized_count']} hotels")
                    except Exception as e:
                        print(f"⚠️ Hotel summarization failed, using original data: {e}")
                
                # Store the result directly in state for parallel execution
                # Make sure we're storing a proper dict, not None
                updated_state["hotel_result"] = hotel_result
                # No need to set route - using add_edge means we automatically route to join_node
                
                # Debug: Verify what we're actually storing
                stored_result = updated_state.get("hotel_result")
                print(f"Hotel agent: Verified stored result - type: {type(stored_result)}, is None: {stored_result is None}, has hotels: {len(stored_result.get('hotels', [])) if isinstance(stored_result, dict) else 0}")
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                print(f"[{end_time.strftime('%H:%M:%S.%f')[:-3]}] 🏨 HOTEL AGENT COMPLETED (Duration: {duration:.3f}s)")
                return updated_state
                
            except Exception as e:
                # Log the exception for debugging
                import traceback
                error_trace = traceback.format_exc()
                print(f"Error in hotel_agent_node: {e}")
                print(f"Traceback: {error_trace}")
                # Store error in result with full error structure
                updated_state["hotel_result"] = {
                    "error": True,
                    "error_code": "AGENT_ERROR",
                    "error_message": str(e),
                    "suggestion": "An unexpected error occurred. Please try again or contact support if the problem persists.",
                    "hotels": []
                }
                # No need to set route - using add_edge means we automatically route to join_node
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                print(f"[{end_time.strftime('%H:%M:%S.%f')[:-3]}] 🏨 HOTEL AGENT COMPLETED (Duration: {duration:.3f}s)")
                return updated_state
    
    # No tool call - store empty result
    updated_state["hotel_result"] = {"error": True, "error_message": "No hotel search parameters provided"}
    # No need to set route - using add_edge means we automatically route to join_node
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"[{end_time.strftime('%H:%M:%S.%f')[:-3]}] 🏨 HOTEL AGENT COMPLETED (Duration: {duration:.3f}s)")
    return updated_state

