"""Planner Agent node for LangGraph orchestration - manages travel plan items."""

import sys
import os
import json
import copy
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "mcp_system"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import AgentState
from clients.planner_agent_client import PlannerAgentClient

# Load environment variables
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_planner_agent_prompt() -> str:
    """Get the system prompt for the Planner Agent."""
    return """You are the Planner Agent, a specialized agent that manages travel plan items (saved flights, hotels, activities, etc.).

Your role:
- Analyze user messages to determine if they want to add, update, delete, or view travel plan items
- Extract information about which items the user wants to save (e.g., "I want option 2", "save flight X", "I liked hotel Y")
- Use the available tools to manage travel plan items in the database
- Understand references to previously shown results (e.g., "option 2" refers to the second flight/hotel in a list)

Available tools:
- agent_add_plan_item_tool: Add a new item to the travel plan
- agent_update_plan_item_tool: Update an existing plan item
- agent_delete_plan_item_tool: Delete a plan item
- agent_get_plan_items_tool: Retrieve all plan items for the session

CRITICAL INTENT DISTINCTION - READ CAREFULLY:

You MUST distinguish between:
1. **SEARCH REQUESTS** (NOT your job - do NOT call tools, just pass through):
   - "Let's see hotel options" / "Show me hotel options" / "Find hotels" / "Search for hotels"
   - "Show me flight options" / "Find flights" / "Search for flights"
   - "What hotels are available?" / "What flights are there?"
   - "I want to see hotels" / "I want to see flights"
   - These are SEARCH requests - the user wants to DISCOVER new options, NOT check their saved plan
   - **ACTION: Do NOT call agent_get_plan_items_tool. These requests should be handled by hotel_agent/flight_agent, not you.**

2. **PLAN CHECK REQUESTS** (Your job - call agent_get_plan_items_tool):
   - "Show my plan" / "What's in my plan" / "My travel plan" / "My saved plan"
   - "What have I saved?" / "What's in my itinerary?"
   - "Show me what I've chosen" / "What did I add to my plan?"
   - These explicitly ask about the USER'S SAVED PLAN
   - **ACTION: Call agent_get_plan_items_tool to retrieve saved items**

3. **ADD TO PLAN REQUESTS** (Your job - call agent_add_plan_item_tool):
   - "I want option 2" / "save option 2" / "select option 2" / "add option 2" / "choose option 2"
   - "I liked hotel X" / "save flight Y" / "add hotel X to my plan"
   - "I'll take this one" / "I'll choose option 3"
   - These indicate the user wants to SAVE a specific item to their plan
   - **ACTION: Extract item details and call agent_add_plan_item_tool**

4. **UPDATE/DELETE REQUESTS** (Your job):
   - "remove X" / "delete Y" / "cancel Z" → Delete item
   - "update X" / "change Y" / "modify Z" → Update item
   - "add X instead of Y" / "replace Y with X" → DELETE Y, then ADD X

IMPORTANT WORKFLOW:
1. **FIRST**: Determine if this is a SEARCH request (see examples above)
   - If YES → Do NOT call any tools. Just pass through (the system will route to hotel_agent/flight_agent)
   - If NO → Continue to step 2

2. **SECOND**: If it's a plan management request:
   - Extract the item details from the collected_info (flight_result, hotel_result, etc.) based on the user's selection
   - If user says "option 2", find the 2nd item in the relevant result array
   - Extract all relevant details (price, dates, location, etc.)

3. **THIRD**: Call the appropriate tool(s) to perform the operation

4. **FOURTH**: Provide a summary of what was done

CRITICAL RULES:
- "See options" / "Show options" / "Find options" = SEARCH, NOT plan check
- "Show my plan" / "My plan" = Plan check
- When in doubt about SEARCH vs PLAN CHECK, ask yourself: "Does the user want to DISCOVER new options, or see what they've ALREADY SAVED?"
- If the user wants to discover → Do NOT call tools (this is not your job)
- If the user wants to see saved items → Call agent_get_plan_items_tool
- If the user wants to save an item → Call agent_add_plan_item_tool

CRITICAL: You MUST use the tools to perform operations. Do NOT just respond without calling tools UNLESS it's a search request (in which case you should not be handling it at all)."""


async def planner_agent_node(state: AgentState) -> AgentState:
    """Planner Agent node that manages travel plan items.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with planner operations completed
    """
    from datetime import datetime
    import re
    start_time = datetime.now()
    print(f"[{start_time.strftime('%H:%M:%S.%f')[:-3]}] 📋 PLANNER AGENT STARTED")
    
    user_message = state.get("user_message", "")
    user_email = state.get("user_email")
    session_id = state.get("session_id")
    collected_info = state.get("collected_info", {})
    context = state.get("context", {}) or {}
    travel_plan_items = state.get("travel_plan_items", [])
    
    # Fast path: Check for simple "option X" pattern to optimize processing
    user_msg_lower = user_message.lower()
    simple_option_pattern = r'(?:choose|select|want|take|pick|i\'ll choose|i\'ll take|i will choose|i will take)\s+(?:option\s+)?(?:number\s+)?(?:nb\s+)?(?:#\s+)?(\d+)'
    option_match = re.search(simple_option_pattern, user_msg_lower)
    
    # If it's a simple "option X" request and we have flight/hotel data, we can optimize
    is_simple_option = option_match is not None
    
    # Check state directly for results (they might be in state fields, not just collected_info)
    # This is critical for follow-up messages where results were from previous execution
    if state.get("flight_result") and not collected_info.get("flight_result"):
        collected_info["flight_result"] = state.get("flight_result")
    if state.get("hotel_result") and not collected_info.get("hotel_result"):
        collected_info["hotel_result"] = state.get("hotel_result")
    if state.get("visa_result") and not collected_info.get("visa_result"):
        collected_info["visa_result"] = state.get("visa_result")
    if state.get("tripadvisor_result") and not collected_info.get("tripadvisor_result"):
        collected_info["tripadvisor_result"] = state.get("tripadvisor_result")
    if state.get("utilities_result") and not collected_info.get("utilities_result"):
        collected_info["utilities_result"] = state.get("utilities_result")
    
    # Also check context for results (results might be in context instead of collected_info)
    if context.get("flight_result") and not collected_info.get("flight_result"):
        collected_info["flight_result"] = context.get("flight_result")
    if context.get("hotel_result") and not collected_info.get("hotel_result"):
        collected_info["hotel_result"] = context.get("hotel_result")
    if context.get("visa_result") and not collected_info.get("visa_result"):
        collected_info["visa_result"] = context.get("visa_result")
    if context.get("tripadvisor_result") and not collected_info.get("tripadvisor_result"):
        collected_info["tripadvisor_result"] = context.get("tripadvisor_result")
    if context.get("utilities_result") and not collected_info.get("utilities_result"):
        collected_info["utilities_result"] = context.get("utilities_result")
    
    # If no results in collected_info, try to retrieve from STM (from previous message)
    # Retrieve each type separately - don't require all to be missing
    if session_id:
        try:
            from stm.short_term_memory import get_last_results
            last_results = get_last_results(session_id)
            if last_results:
                print(f"[PLANNER] Retrieved last results from STM: {list(last_results.keys())}")
                # Merge with collected_info (don't overwrite if something exists)
                for key, value in last_results.items():
                    if not collected_info.get(key) and value:
                        collected_info[key] = value
                        if key == "flight_result" and isinstance(value, dict):
                            outbound_count = len(value.get("outbound", []))
                            return_count = len(value.get("return", []))
                            print(f"[PLANNER] Loaded {key} from STM: {outbound_count} outbound, {return_count} return flights")
                        elif key == "hotel_result" and isinstance(value, dict):
                            hotels_count = len(value.get("hotels", []))
                            print(f"[PLANNER] Loaded {key} from STM: {hotels_count} hotels")
                        elif key == "tripadvisor_result" and isinstance(value, dict):
                            locations_count = len(value.get("data", []))
                            print(f"[PLANNER] Loaded {key} from STM: {locations_count} locations")
                        else:
                            print(f"[PLANNER] Loaded {key} from STM")
        except Exception as e:
            print(f"[WARNING] Could not retrieve last results from STM: {e}")
    
    # If no user email or session, skip planner operations
    if not user_email or not session_id:
        print("[PLANNER] No user_email or session_id, skipping planner operations")
        updated_state = state.copy()
        updated_state["route"] = "planner_feedback"
        updated_state["needs_planner"] = False
        return updated_state
    
    # Check if user message indicates planner intent
    user_msg_lower = user_message.lower()
    
    # CRITICAL: Exclude search requests - these should NOT trigger planner
    search_phrases = [
        "see hotel options", "see flight options", "see options",
        "show hotel options", "show flight options", "show options",
        "find hotels", "find flights", "search for hotels", "search for flights",
        "what hotels are available", "what flights are available",
        "hotel options", "flight options", "available hotels", "available flights",
        "let's see", "show me hotels", "show me flights", "i want to see"
    ]
    
    # If it's clearly a search request, skip planner
    is_search_request = any(phrase in user_msg_lower for phrase in search_phrases)
    if is_search_request:
        print(f"[PLANNER] Detected search request ('{user_message}'), skipping planner operations")
        updated_state = state.copy()
        updated_state["route"] = "planner_feedback"
        updated_state["needs_planner"] = False
        return updated_state
    
    # Planner keywords for plan management operations
    planner_keywords = [
        "save", "select", "choose", "want", "like", "add to plan", "add to my plan",
        "remove", "delete", "cancel", "update", "change", "modify",
        "show my plan", "what's in my plan", "my plan", "travel plan", "my saved plan"
    ]
    
    has_planner_intent = any(keyword in user_msg_lower for keyword in planner_keywords)
    
    if not has_planner_intent:
        print("[PLANNER] No planner intent detected, skipping planner operations")
        updated_state = state.copy()
        updated_state["route"] = "planner_feedback"
        updated_state["needs_planner"] = False
        return updated_state
    
    # Debug: Log what results we have
    print(f"[PLANNER] Debug - collected_info keys: {list(collected_info.keys())}")
    print(f"[PLANNER] Debug - state flight_result: {bool(state.get('flight_result'))}")
    print(f"[PLANNER] Debug - state hotel_result: {bool(state.get('hotel_result'))}")
    if collected_info.get("flight_result"):
        flight_result = collected_info["flight_result"]
        outbound_count = len(flight_result.get("outbound", [])) if isinstance(flight_result, dict) else 0
        return_count = len(flight_result.get("return", [])) if isinstance(flight_result, dict) else 0
        print(f"[PLANNER] Debug - Found {outbound_count} outbound and {return_count} return flights")
    
    selected_context: dict = {}

    def _append_selected_result(result_key: str, list_key: str, data: dict):
        """Add a selected item to context for conversational agent display."""
        nonlocal selected_context
        if not data:
            return
        container = selected_context.setdefault(result_key, {})
        items = container.setdefault(list_key, [])
        items.append(copy.deepcopy(data))

    try:
        # Get tools available to planner agent
        tools = await PlannerAgentClient.list_tools()
        
        # Prepare messages for LLM
        prompt = get_planner_agent_prompt()
        
        # Build context about available results - include ONLY essential details for saving
        results_context = ""
        full_flight_data = {}  # Store MINIMAL flight data for extraction (no booking links, no redundant fields)
        
        def _strip_flight_to_essentials(flight):
            """Strip flight data to only essential fields needed for saving."""
            import copy
            stripped = copy.deepcopy(flight)
            # Keep only essential fields (don't send long links to LLM)
            essential_fields = {
                "flights": stripped.get("flights", []),  # Keep flight segments (needed for airports, times)
                "price": stripped.get("price"),
                "total_duration": stripped.get("total_duration"),
                "type": stripped.get("type", "One way"),
                "direction": stripped.get("direction"),
                "airline_logo": stripped.get("airline_logo"),  # Keep for display
            }
            # Remove booking_link, booking_token, google_flights_url, and other large/unnecessary fields
            # Also clean flight segments to remove unnecessary details
            if essential_fields.get("flights"):
                cleaned_segments = []
                for segment in essential_fields["flights"]:
                    cleaned_seg = {
                        "airline": segment.get("airline"),
                        "flight_number": segment.get("flight_number"),
                        "departure_airport": segment.get("departure_airport"),
                        "arrival_airport": segment.get("arrival_airport"),
                        "duration": segment.get("duration"),
                        "travel_class": segment.get("travel_class"),
                        "airplane": segment.get("airplane"),
                        "legroom": segment.get("legroom"),
                    }
                    cleaned_segments.append(cleaned_seg)
                essential_fields["flights"] = cleaned_segments
            return essential_fields
        
        if collected_info.get("flight_result"):
            flight_result = collected_info["flight_result"]
            outbound = flight_result.get("outbound", [])
            return_flights = flight_result.get("return", [])
            results_context += f"\n\nAvailable flight results:\n"
            
            if outbound:
                results_context += f"Outbound flights ({len(outbound)} options, numbered 1 to {len(outbound)}):\n"
                for i, flight in enumerate(outbound[:10], 1):  # Limit to first 10
                    price = flight.get("price", "N/A")
                    airline = flight.get("flights", [{}])[0].get("airline", "Unknown") if flight.get("flights") else "Unknown"
                    departure = flight.get("flights", [{}])[0].get("departure_airport", {}).get("name", "Unknown") if flight.get("flights") else "Unknown"
                    arrival = flight.get("flights", [{}])[0].get("arrival_airport", {}).get("name", "Unknown") if flight.get("flights") else "Unknown"
                    # Extract flight numbers for indexing
                    flight_numbers = []
                    if flight.get("flights"):
                        for seg in flight["flights"]:
                            fn = seg.get("flight_number", "")
                            if fn:
                                flight_numbers.append(fn)
                    flight_number_str = " ".join(flight_numbers) if flight_numbers else "N/A"
                    position_label = " (LAST)" if i == len(outbound) else " (FIRST)" if i == 1 else ""
                    results_context += f"  Option {i}{position_label}: {airline} {flight_number_str} - {departure} to {arrival} - ${price}\n"
                    # Store STRIPPED flight data (essential fields only, no booking links)
                    stripped_flight = _strip_flight_to_essentials(flight)
                    full_flight_data[f"outbound_option_{i}"] = stripped_flight
                    if i == 1:
                        full_flight_data["outbound_first"] = stripped_flight
                    if i == len(outbound):
                        full_flight_data["outbound_last"] = stripped_flight
                    # Also index by flight number for easy lookup (e.g., "ME 229", "VF 1628")
                    for fn in flight_numbers:
                        # Normalize flight number (remove spaces, uppercase)
                        fn_key = fn.replace(" ", "").upper()
                        full_flight_data[f"flight_{fn_key}"] = stripped_flight
                        # Also store with airline prefix (e.g., "ME229", "ME 229")
                        if airline:
                            airline_prefix = airline.upper().replace(" ", "")
                            full_flight_data[f"flight_{airline_prefix}_{fn_key}"] = stripped_flight
            
            if return_flights:
                results_context += f"Return flights ({len(return_flights)} options, numbered 1 to {len(return_flights)}):\n"
                for i, flight in enumerate(return_flights[:10], 1):
                    price = flight.get("price", "N/A")
                    airline = flight.get("flights", [{}])[0].get("airline", "Unknown") if flight.get("flights") else "Unknown"
                    departure = flight.get("flights", [{}])[0].get("departure_airport", {}).get("name", "Unknown") if flight.get("flights") else "Unknown"
                    arrival = flight.get("flights", [{}])[0].get("arrival_airport", {}).get("name", "Unknown") if flight.get("flights") else "Unknown"
                    # Extract flight numbers for indexing
                    flight_numbers = []
                    if flight.get("flights"):
                        for seg in flight["flights"]:
                            fn = seg.get("flight_number", "")
                            if fn:
                                flight_numbers.append(fn)
                    flight_number_str = " ".join(flight_numbers) if flight_numbers else "N/A"
                    position_label = " (LAST)" if i == len(return_flights) else " (FIRST)" if i == 1 else ""
                    results_context += f"  Option {i}{position_label}: {airline} {flight_number_str} - {departure} to {arrival} - ${price}\n"
                    # Store STRIPPED flight data (essential fields only, no booking links)
                    stripped_flight = _strip_flight_to_essentials(flight)
                    full_flight_data[f"return_option_{i}"] = stripped_flight
                    if i == 1:
                        full_flight_data["return_first"] = stripped_flight
                    if i == len(return_flights):
                        full_flight_data["return_last"] = stripped_flight
                    # Also index by flight number for easy lookup
                    for fn in flight_numbers:
                        fn_key = fn.replace(" ", "").upper()
                        full_flight_data[f"flight_{fn_key}"] = stripped_flight
                        if airline:
                            airline_prefix = airline.upper().replace(" ", "")
                            full_flight_data[f"flight_{airline_prefix}_{fn_key}"] = stripped_flight
        
        full_hotel_data = {}  # Store full hotel data for extraction
        if collected_info.get("hotel_result"):
            hotel_result = collected_info["hotel_result"]
            hotels = hotel_result.get("hotels", [])
            if hotels:
                results_context += f"\n\nAvailable hotel results ({len(hotels)} options):\n"
                for i, hotel in enumerate(hotels[:10], 1):  # Limit to first 10
                    name = hotel.get("name", "Unknown")
                    price = hotel.get("roomTypes", [{}])[0].get("rates", [{}])[0].get("price", {}).get("total", "N/A") if hotel.get("roomTypes") else "N/A"
                    results_context += f"  Option {i}: {name} - ${price}\n"
                    # Store full hotel data for extraction (by both option number and name)
                    full_hotel_data[f"hotel_option_{i}"] = hotel
                    # Also store by name (normalized) for name-based matching
                    name_key = name.lower().replace(" ", "_").replace("-", "_")
                    full_hotel_data[f"hotel_name_{name_key}"] = hotel
        
        full_restaurant_data = {}  # Store full restaurant/activity data for extraction
        if collected_info.get("tripadvisor_result"):
            tripadvisor_result = collected_info["tripadvisor_result"]
            locations = tripadvisor_result.get("data", [])
            if locations:
                results_context += f"\n\nAvailable location/restaurant results ({len(locations)} options):\n"
                for i, loc in enumerate(locations[:10], 1):
                    name = loc.get("name", "Unknown")
                    rating = loc.get("rating", "N/A")
                    location_str = loc.get("address") or loc.get("location", "N/A")
                    results_context += f"  Option {i}: {name} - Rating: {rating} - {location_str}\n"
                    # Store full restaurant/activity data for extraction (by option number and name)
                    full_restaurant_data[f"restaurant_option_{i}"] = loc
                    full_restaurant_data[f"activity_option_{i}"] = loc  # Same data for activities
                    # Also store by name (normalized) for name-based matching
                    name_key = name.lower().replace(" ", "_").replace("-", "_")
                    full_restaurant_data[f"restaurant_name_{name_key}"] = loc
                    full_restaurant_data[f"activity_name_{name_key}"] = loc
        
        # Include optimized data context (avoid sending huge JSON dumps)
        full_data_context = ""
        if full_flight_data:
            # Instead of sending entire JSON, provide lookup instructions and key mapping
            available_keys = list(full_flight_data.keys())[:20]  # Limit to first 20 keys for context
            full_data_context += f"\n\nFULL FLIGHT DATA AVAILABLE (indexed by option number and flight number):\n"
            full_data_context += f"Available lookup keys: {', '.join(available_keys[:10])}{'...' if len(available_keys) > 10 else ''}\n"
            full_data_context += "\n**SEMANTIC MAPPING FOR OPTION REFERENCES:**\n"
            full_data_context += "- 'last option' / 'last one' → Use 'outbound_last' or 'return_last' key\n"
            full_data_context += "- 'first option' / 'first one' → Use 'outbound_first' or 'return_first' key\n"
            full_data_context += "- 'option X' (e.g., 'option 3') → Use 'outbound_option_X' or 'return_option_X' key\n"
            full_data_context += "- 'cheapest' → Find the flight with lowest price from all options\n"
            full_data_context += "- 'most expensive' → Find the flight with highest price from all options\n"
            full_data_context += "- **FLIGHT NUMBER REFERENCES** (e.g., 'ME 229', 'VF 1628'):\n"
            full_data_context += "  * Search for keys like 'flight_ME229', 'flight_ME_229', or 'flight_VF1628'\n"
            full_data_context += "\n**IMPORTANT**: The complete flight data is stored in the state. When you call agent_add_plan_item_tool, the system will automatically extract the full flight object from the indexed data using the key you specify. Just reference the key (e.g., 'outbound_option_2') and the system will handle extraction."
        else:
            # No flight data available - make this clear
            full_data_context += "\n\n NO FLIGHT DATA AVAILABLE: The user is asking to save an option, but no flight search results are available. You MUST inform the user that they need to search for flights first before they can save an option."
        
        if full_hotel_data:
            # Optimize hotel data context similarly
            available_hotel_keys = list(full_hotel_data.keys())[:20]
            full_data_context += f"\n\nFULL HOTEL DATA AVAILABLE (indexed by option number and name):\n"
            full_data_context += f"Available lookup keys: {', '.join(available_hotel_keys[:10])}{'...' if len(available_hotel_keys) > 10 else ''}\n"
            full_data_context += "\nWhen user says 'option X' or mentions a hotel name:\n"
            full_data_context += "- If they say 'option X', use 'hotel_option_X' key\n"
            full_data_context += "- If they mention a hotel name, search for a matching key like 'hotel_name_*' (names are normalized: lowercase, spaces/hyphens become underscores)\n"
            full_data_context += "\n**IMPORTANT**: The complete hotel data is stored in the state. When you call agent_add_plan_item_tool, the system will automatically extract the full hotel object from the indexed data using the key you specify."
        elif collected_info.get("hotel_result") and not collected_info.get("hotel_result", {}).get("hotels"):
            full_data_context += "\n\n NO HOTEL DATA AVAILABLE: The user is asking to save a hotel, but no hotel search results are available. You MUST inform the user that they need to search for hotels first before they can save one."
        
        if full_restaurant_data:
            # Optimize restaurant/activity data context similarly
            available_restaurant_keys = list(full_restaurant_data.keys())[:20]
            full_data_context += f"\n\nFULL RESTAURANT/ACTIVITY DATA AVAILABLE (indexed by option number and name):\n"
            full_data_context += f"Available lookup keys: {', '.join(available_restaurant_keys[:10])}{'...' if len(available_restaurant_keys) > 10 else ''}\n"
            full_data_context += "\nWhen user says 'option X' or mentions a restaurant/activity name:\n"
            full_data_context += "- If they say 'option X', use 'restaurant_option_X' or 'activity_option_X' key\n"
            full_data_context += "- If they mention a name, search for a matching key like 'restaurant_name_*' or 'activity_name_*' (names are normalized: lowercase, spaces/hyphens become underscores)\n"
            full_data_context += "\n**IMPORTANT**: The complete restaurant/activity data is stored in the state. When you call agent_add_plan_item_tool, the system will automatically extract the full object from the indexed data using the key you specify."
        elif collected_info.get("tripadvisor_result") and not collected_info.get("tripadvisor_result", {}).get("data"):
            full_data_context += "\n\n NO RESTAURANT/ACTIVITY DATA AVAILABLE: The user is asking to save a restaurant/activity, but no search results are available. You MUST inform the user that they need to search for restaurants/activities first before they can save one."
        
        # Extract string with backslashes to avoid f-string syntax error
        no_results_msg = "\n\n⚠️ No results available yet. If the user wants to save an item, they need to search first (e.g., 'find flights to Paris') to see options."
        
        agent_message = f"""User message: {user_message}

Current travel plan items ({len(travel_plan_items)} items):
{json.dumps(travel_plan_items, indent=2, default=str) if travel_plan_items else "No items in plan yet"}

Available results from agents:{results_context if results_context else no_results_msg}
{full_data_context}

User email: {user_email}
Session ID: {session_id}

CRITICAL INSTRUCTIONS:
1. Analyze the user's intent (add, update, delete, or view plan items) - understand the SEMANTIC meaning, not just keywords
2. **CHECKING FOR DUPLICATES BEFORE ADDING** (CRITICAL):
   - Before adding any restaurant/activity/hotel/flight, ALWAYS check the "Current travel plan items" section above
   - If an item with the same name already exists in the plan, DO NOT add it again - skip it or update it instead
   - For restaurants: Check if a restaurant with the same name already exists (case-insensitive matching)
   - For flights: Check if a flight with the same flight number and date already exists
   - For hotels: Check if a hotel with the same name and location already exists
   - If user asks to add multiple items (e.g., "add 2 restaurants"), only add items that don't already exist
3. **HANDLING "INSTEAD OF" / "REPLACE" SCENARIOS** (CRITICAL):
   - If user says "add X instead of Y" or "replace Y with X" or "change Y to X":
     * FIRST: Find Y in the current travel plan items (check the "Current travel plan items" section above)
     * SECOND: Call agent_delete_plan_item_tool to remove Y (you'll need the item's ID from travel_plan_items)
     * THIRD: Find X in the available results (FULL HOTEL DATA or FULL FLIGHT DATA)
     * FOURTH: Call agent_add_plan_item_tool to add X
     * This requires TWO tool calls: delete then add
4. **SEMANTIC UNDERSTANDING OF OPTION REFERENCES** (CRITICAL):
   - **CRITICAL: DISTINGUISH OUTBOUND vs RETURN FLIGHTS**:
     * "returning flight" / "return flight" / "flight back" / "return trip" → Use 'return_option_X' keys
     * "outbound flight" / "departure flight" / "going flight" → Use 'outbound_option_X' keys
     * If user says "the 1st option" for a "returning flight" → Use 'return_option_1', NOT 'outbound_option_1'
     * If user says "the 1st option" for an "outbound flight" → Use 'outbound_option_1'
     * If context is unclear, check the user message for words like "return", "back", "returning" → these indicate RETURN flights
   - "last option" / "last one" / "the last flight" → Find the LAST item in the list (highest index number, use 'outbound_last' or 'return_last' key)
   - "first option" / "first one" / "the first flight" → Find the FIRST item in the list (index 1, use 'outbound_first' or 'return_first' key)
   - "second option" / "second one" → Find the SECOND item (index 2)
   - "third option" / "third one" → Find the THIRD item (index 3)
   - "option X" (e.g., "option 3") → Find the Xth item (index X) - but determine if it's outbound or return based on context
   - "cheapest" / "cheapest one" → Find the item with the LOWEST price
   - "most expensive" / "expensive one" → Find the item with the HIGHEST price
   - Use your understanding of the context - if user says "last option" after seeing 9 flights, they mean the 9th flight (the one at the end of the list)
5. If user mentions a hotel name (e.g., "add Le Meridien Fairway", "add meridien fairway"), search the FULL HOTEL DATA for a matching hotel name (case-insensitive, partial matches OK - e.g., "meridien fairway" matches "Le Meridien Fairway")
5b. **FINDING FLIGHTS BY FLIGHT NUMBER** (CRITICAL):
   - If user mentions a flight number (e.g., "ME 229", "VF 1628", "flight ME 229", "add ME 229"):
     * Search FULL FLIGHT DATA for keys like 'flight_ME229', 'flight_ME_229', 'flight_VF1628' (normalized: spaces removed, uppercase)
     * Also try 'flight_<AIRLINE>_<NUMBER>' format (e.g., 'flight_ME_229')
     * Extract the COMPLETE flight object with ALL details - do NOT create a minimal flight object with just the flight number
     * If flight is not found in FULL FLIGHT DATA, you MUST inform the user that the flight details are not available and they need to search for flights first
6. **OPTIMIZED EXTRACTION**: When calling agent_add_plan_item_tool, you can pass minimal details - the system will automatically extract the complete object from indexed data:
   - For flights: You can pass just the key reference (e.g., "outbound_option_2") or minimal details - the system will auto-complete from full_flight_data
   - For hotels: You can pass just the key reference (e.g., "hotel_option_1") or minimal details - the system will auto-complete from full_hotel_data
   - For restaurants/activities: You can pass just the key reference (e.g., "restaurant_option_1") or minimal details - the system will auto-complete from full_restaurant_data
   - The system will automatically extract: flights (price, duration, airports, times), hotels (name, location, rating, roomTypes), restaurants/activities (name, location, rating, photos, cuisine, etc.)
   - IMPORTANT: Do NOT include booking_link or booking_token (system will exclude these automatically)
7. When calling agent_add_plan_item_tool:
   - For flights: title like "Flight: Beirut to Dubai on Dec 1, 2025 - Emirates EK 958", type: "flight"
   - For hotels: title like "Hotel: Le Meridien Fairway, Dubai", type: "hotel"
   - details: Pass minimal details or key reference - the system will extract the complete object automatically
   - status: "not_booked"
8. When calling agent_delete_plan_item_tool:
   - You need the item's ID from the "Current travel plan items" section
   - Match by title or details to find the correct item ID
9. If no results are available, inform them they need to search first

**IMPORTANT**: Use semantic understanding, not rule-based logic. Understand what the user means by "last", "first", "cheapest", "instead of", etc. based on the context and the list of available options.

Remember: You MUST extract and save the COMPLETE flight/hotel object with ALL details, not just a summary."""

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": agent_message}
        ]
        
        # Build function calling schema for planner tools
        functions = []
        def _sanitize_schema(schema: dict) -> dict:
            """Ensure arrays have 'items' and sanitize nested schemas."""
            if not isinstance(schema, dict):
                return schema
            sanitized = dict(schema)
            schema_type = sanitized.get("type")
            if schema_type == "array" and "items" not in sanitized:
                sanitized["items"] = {"type": "object"}
            if schema_type == "object":
                props = sanitized.get("properties", {})
                for key, val in list(props.items()):
                    props[key] = _sanitize_schema(val)
                sanitized["properties"] = props
            if "items" in sanitized and isinstance(sanitized["items"], dict):
                sanitized["items"] = _sanitize_schema(sanitized["items"])
            return sanitized

        for tool in tools:
            if tool["name"] in [
                "agent_add_plan_item_tool",
                "agent_update_plan_item_tool",
                "agent_delete_plan_item_tool",
                "agent_get_plan_items_tool"
            ]:
                input_schema = tool.get("inputSchema", {})
                input_schema = _sanitize_schema(input_schema)
                functions.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", f"Planner operation tool"),
                        "parameters": input_schema
                    }
                })
        
        # Call LLM with function calling - use faster model for simple operations
        # For "choose option X" type requests, we can use a faster response
        user_msg_lower = user_message.lower()
        is_simple_option_selection = any(phrase in user_msg_lower for phrase in [
            "choose option", "select option", "want option", "option number", 
            "option nb", "option #", "i'll take option", "i'll choose option"
        ])
        
        # Use faster temperature and potentially shorter max_tokens for simple selections
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            tools=functions if functions else None,
            tool_choice="auto" if functions else None,
            temperature=0.1 if is_simple_option_selection else 0.3,  # Lower temperature for faster, more deterministic responses
            max_tokens=2000 if is_simple_option_selection else None  # Limit tokens for simple operations
        )
        
        message = response.choices[0].message
        tool_calls = message.tool_calls or []
        
        # CRITICAL: Double-check for search requests - if LLM tries to check plan for a search request, skip it
        if tool_calls:
            for tool_call in tool_calls:
                if tool_call.function.name == "agent_get_plan_items_tool":
                    # Check if this is actually a search request disguised as a plan check
                    search_indicators = [
                        "see", "show", "find", "search", "options", "available",
                        "let's see", "show me", "what are", "what hotels", "what flights"
                    ]
                    user_lower = user_message.lower()
                    if any(indicator in user_lower for indicator in search_indicators):
                        # This is a search request, not a plan check
                        if "my plan" not in user_lower and "saved" not in user_lower and "travel plan" not in user_lower:
                            print(f"[PLANNER] ⚠️ Detected search request ('{user_message}') but LLM tried to check plan - skipping tool call")
                            tool_calls = []  # Remove the tool call
                            break
        
        planner_summary = []
        
        # Execute tool calls
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)
            
            print(f"[PLANNER] Calling tool: {tool_name} with args: {tool_args}")
            
            try:
                # Check for duplicates and extract full details for restaurants/activities
                original_restaurant_details = None  # Initialize for UI display
                if tool_name == "agent_add_plan_item_tool" and tool_args.get("type") in ("restaurant", "activity"):
                    details = tool_args.get("details", {})
                    details_updated = False
                    
                    # CRITICAL: Handle case where details is a string key reference (e.g., "restaurant_option_2")
                    # This happens when the LLM follows the optimization instruction to pass just a key
                    if isinstance(details, str):
                        print(f"[PLANNER] Restaurant/activity details is a string key reference: '{details}', extracting from full_restaurant_data...")
                        # Try to extract from full_restaurant_data using the key
                        if details in full_restaurant_data:
                            print(f"[PLANNER] ✓ Found key '{details}' in full_restaurant_data")
                            details = copy.deepcopy(full_restaurant_data[details])
                            tool_args["details"] = details
                            details_updated = True
                        else:
                            print(f"[PLANNER] Key '{details}' not found in full_restaurant_data, trying to parse option number...")
                            # Try to find by option number pattern
                            import re
                            option_match = re.search(r'option[_\s]*(\d+)', details, re.IGNORECASE)
                            if option_match:
                                option_num = int(option_match.group(1))
                                # Try both restaurant and activity keys
                                for key_type in ["restaurant", "activity"]:
                                    key = f"{key_type}_option_{option_num}"
                                    if key in full_restaurant_data:
                                        print(f"[PLANNER] ✓ Found {key_type} by option number: {key}")
                                        details = copy.deepcopy(full_restaurant_data[key])
                                        tool_args["details"] = details
                                        details_updated = True
                                        break
                            
                            # If still not found, try to extract from tripadvisor_result directly
                            if not details_updated:
                                print(f"[PLANNER] Trying to extract from tripadvisor_result directly...")
                                tripadvisor_result = collected_info.get("tripadvisor_result", {})
                                locations = tripadvisor_result.get("data", [])
                                
                                # Try to parse option number from the string
                                import re
                                option_match = re.search(r'(\d+)', details)
                                if option_match:
                                    option_num = int(option_match.group(1))
                                    
                                    if locations and 1 <= option_num <= len(locations):
                                        # Option numbers are 1-indexed, list is 0-indexed
                                        location = locations[option_num - 1]
                                        print(f"[PLANNER] ✓ Extracted restaurant/activity from locations list at index {option_num - 1}")
                                        details = copy.deepcopy(location)
                                        tool_args["details"] = details
                                        details_updated = True
                                    else:
                                        print(f"[PLANNER] ⚠ Option {option_num} out of range for locations list (has {len(locations)} items)")
                    
                    # If details are missing or incomplete, try to extract from full_restaurant_data
                    if not details_updated and (not details or not isinstance(details, dict) or not details.get("name")):
                        # Try to extract based on title or option number
                        title = tool_args.get("title", "").lower()
                        user_msg_lower = user_message.lower()
                        import re
                        
                        # Try option number
                        option_pattern = r'option\s+(\d+)'
                        option_match = re.search(option_pattern, title) or re.search(option_pattern, user_msg_lower)
                        
                        if option_match:
                            option_num = int(option_match.group(1))
                            # Try both restaurant and activity keys
                            for key_type in ["restaurant", "activity"]:
                                key = f"{key_type}_option_{option_num}"
                                if key in full_restaurant_data:
                                    print(f"[PLANNER] Extracting complete {key_type} data for {key}")
                                    location = full_restaurant_data[key]
                                    tool_args["details"] = copy.deepcopy(location)
                                    details = tool_args["details"]
                                    details_updated = True
                                    break
                    
                    # Validate that we have complete restaurant/activity details
                    details = tool_args.get("details", {}) if not details_updated else details
                    
                    # Ensure details is a dict (not a string key reference)
                    if isinstance(details, str):
                        print(f"[PLANNER] Error: restaurant/activity details is still a string '{details}' after extraction attempt")
                        error_msg = f"Cannot add {tool_args.get('type')}: Could not extract data from key '{details}'. Please search for restaurants/activities first."
                        planner_summary.append(error_msg)
                        print(f"[PLANNER] ✗ {error_msg}")
                        continue  # Skip this tool call
                    
                    if not details or not isinstance(details, dict) or not details.get("name"):
                        error_msg = f"Cannot add {tool_args.get('type')}: Details are incomplete. Please search for restaurants/activities first to get complete information."
                        planner_summary.append(error_msg)
                        print(f"[PLANNER] ✗ {error_msg}")
                        continue  # Skip this tool call
                    
                    # Store original restaurant details for UI display
                    original_restaurant_details = copy.deepcopy(details) if details else None
                    
                    # Ensure location field exists for frontend display
                    if details and not details.get("location"):
                        # Construct location from available fields
                        location_parts = []
                        if details.get("address"):
                            location_parts.append(details["address"])
                        if details.get("city"):
                            location_parts.append(details["city"])
                        if details.get("country"):
                            location_parts.append(details["country"])
                        if location_parts:
                            details["location"] = ", ".join(location_parts)
                    
                    # Prepare restaurant/activity details - keep all essential fields
                    if details:
                        cleaned_restaurant_details = {}
                        # Keep essential fields
                        if "name" in details:
                            cleaned_restaurant_details["name"] = details["name"]
                        if "address" in details:
                            cleaned_restaurant_details["address"] = details["address"]
                        if "location" in details:
                            cleaned_restaurant_details["location"] = details["location"]
                        if "rating" in details:
                            cleaned_restaurant_details["rating"] = details["rating"]
                        if "reviews" in details:
                            cleaned_restaurant_details["reviews"] = details["reviews"]
                        if "description" in details:
                            cleaned_restaurant_details["description"] = details["description"]
                        if "photos" in details:
                            cleaned_restaurant_details["photos"] = details["photos"]
                        if "cuisine" in details:
                            cleaned_restaurant_details["cuisine"] = details["cuisine"]
                        if "price_level" in details:
                            cleaned_restaurant_details["price_level"] = details["price_level"]
                        if "latitude" in details:
                            cleaned_restaurant_details["latitude"] = details["latitude"]
                        if "longitude" in details:
                            cleaned_restaurant_details["longitude"] = details["longitude"]
                        if "location_id" in details:
                            cleaned_restaurant_details["location_id"] = details["location_id"]
                        if "type" in details:
                            cleaned_restaurant_details["type"] = details["type"]
                        
                        tool_args["details"] = cleaned_restaurant_details
                        print(f"[PLANNER] Prepared {tool_args.get('type')} details with {len(cleaned_restaurant_details)} fields (name: {cleaned_restaurant_details.get('name', 'N/A')}, location: {cleaned_restaurant_details.get('location', 'N/A')})")
                    
                    # Check for duplicates after extraction
                    item_name = details.get("name") or tool_args.get("title", "")
                    # Normalize name for comparison (lowercase, remove extra spaces)
                    if item_name:
                        normalized_name = " ".join(item_name.lower().split())
                        # Check if a restaurant/activity with the same name already exists
                        for existing_item in travel_plan_items:
                            if existing_item.get("type") in ("restaurant", "activity"):
                                existing_title = existing_item.get("title", "")
                                existing_name = existing_item.get("details", {}).get("name", "")
                                # Check both title and name fields
                                existing_normalized = " ".join((existing_name or existing_title).lower().split())
                                if normalized_name in existing_normalized or existing_normalized in normalized_name:
                                    print(f"[PLANNER] ⚠️ Restaurant/activity '{item_name}' already exists in plan, skipping duplicate")
                                    planner_summary.append(f"Skipped: {item_name} already exists in plan")
                                    continue  # Skip adding this duplicate
                
                # If adding a plan item, ensure we have complete details
                if tool_name == "agent_add_plan_item_tool" and tool_args.get("type") == "flight":
                    # Check if details are incomplete or if we need to extract from full_flight_data
                    details = tool_args.get("details", {})
                    details_updated = False
                    
                    # CRITICAL: Detect if user wants return flight vs outbound flight
                    user_msg_lower = user_message.lower()
                    user_wants_return = any(word in user_msg_lower for word in ["return", "returning", "back", "return flight", "returning flight"])
                    user_wants_outbound = any(word in user_msg_lower for word in ["outbound", "departure", "going", "outbound flight"])
                    
                    # CRITICAL: Handle case where details is a string key reference (e.g., "outbound_option_2")
                    # This happens when the LLM follows the optimization instruction to pass just a key
                    if isinstance(details, str):
                        print(f"[PLANNER] Details is a string key reference: '{details}', extracting from full_flight_data...")
                        
                        # CRITICAL: Check if LLM chose wrong flight type (outbound when user wants return, or vice versa)
                        if user_wants_return and "outbound" in details.lower():
                            print(f"[PLANNER] ⚠️ User wants RETURN flight but LLM chose OUTBOUND key '{details}' - correcting...")
                            # Try to find return option instead
                            import re
                            option_match = re.search(r'option[_\s]*(\d+)', details, re.IGNORECASE)
                            if option_match:
                                option_num = int(option_match.group(1))
                                return_key = f"return_option_{option_num}"
                                if return_key in full_flight_data:
                                    print(f"[PLANNER] ✓ Corrected to return flight: {return_key}")
                                    details = copy.deepcopy(full_flight_data[return_key])
                                    tool_args["details"] = details
                                    details_updated = True
                        elif user_wants_outbound and "return" in details.lower():
                            print(f"[PLANNER] ⚠️ User wants OUTBOUND flight but LLM chose RETURN key '{details}' - correcting...")
                            # Try to find outbound option instead
                            import re
                            option_match = re.search(r'option[_\s]*(\d+)', details, re.IGNORECASE)
                            if option_match:
                                option_num = int(option_match.group(1))
                                outbound_key = f"outbound_option_{option_num}"
                                if outbound_key in full_flight_data:
                                    print(f"[PLANNER] ✓ Corrected to outbound flight: {outbound_key}")
                                    details = copy.deepcopy(full_flight_data[outbound_key])
                                    tool_args["details"] = details
                                    details_updated = True
                        
                        # If not corrected above, proceed with normal extraction
                        if not details_updated:
                            # Try to extract from full_flight_data using the key
                            if details in full_flight_data:
                                print(f"[PLANNER] ✓ Found key '{details}' in full_flight_data")
                                details = copy.deepcopy(full_flight_data[details])
                                tool_args["details"] = details
                                details_updated = True
                            else:
                                print(f"[PLANNER] Key '{details}' not found in full_flight_data, trying to parse option number...")
                                # Try to find by option number pattern
                                import re
                                option_match = re.search(r'option[_\s]*(\d+)', details, re.IGNORECASE)
                                if option_match:
                                    option_num = int(option_match.group(1))
                                    # Determine flight type based on user intent if available, otherwise from key
                                    if user_wants_return:
                                        flight_type = "return"
                                    elif user_wants_outbound:
                                        flight_type = "outbound"
                                    else:
                                        flight_type = "outbound" if "outbound" in details.lower() else "return"
                                    key = f"{flight_type}_option_{option_num}"
                                    print(f"[PLANNER] Trying key: '{key}' (user wants {flight_type if user_wants_return or user_wants_outbound else 'unknown'})")
                                    if key in full_flight_data:
                                        print(f"[PLANNER] ✓ Found flight by option number: {key}")
                                        details = copy.deepcopy(full_flight_data[key])
                                        tool_args["details"] = details
                                        details_updated = True
                                    else:
                                        print(f"[PLANNER] ⚠ Key '{key}' not found. Available keys: {list(full_flight_data.keys())[:10]}")
                                else:
                                    print(f"[PLANNER] ⚠ Could not parse option number from '{details}'")
                                
                                # If still not found, try to extract from flight_result directly
                                if not details_updated:
                                    print(f"[PLANNER] Trying to extract from flight_result directly...")
                                    flight_result = collected_info.get("flight_result", {})
                                    outbound = flight_result.get("outbound", [])
                                    return_flights = flight_result.get("return", [])
                                    
                                    # Try to parse option number from the string
                                    import re
                                    option_match = re.search(r'(\d+)', details)
                                    if option_match:
                                        option_num = int(option_match.group(1))
                                        # Determine flight type based on user intent
                                        if user_wants_return:
                                            flight_type = "return"
                                            flight_list = return_flights
                                        elif user_wants_outbound:
                                            flight_type = "outbound"
                                            flight_list = outbound
                                        else:
                                            flight_type = "outbound" if "outbound" in details.lower() else "return"
                                            flight_list = outbound if flight_type == "outbound" else return_flights
                                        
                                        if flight_list and 1 <= option_num <= len(flight_list):
                                            # Option numbers are 1-indexed, list is 0-indexed
                                            flight = flight_list[option_num - 1]
                                            print(f"[PLANNER] ✓ Extracted flight from {flight_type} list at index {option_num - 1}")
                                            details = copy.deepcopy(flight)
                                            tool_args["details"] = details
                                            details_updated = True
                                        else:
                                            print(f"[PLANNER] ⚠ Option {option_num} out of range for {flight_type} list (has {len(flight_list)} items)")
                                            if user_wants_return and len(return_flights) == 0:
                                                print(f"[PLANNER] ⚠️ User wants return flight but no return flights available in data")
                                            elif user_wants_outbound and len(outbound) == 0:
                                                print(f"[PLANNER] ⚠️ User wants outbound flight but no outbound flights available in data")
                    
                    # If details are missing or incomplete, try to extract from full_flight_data
                    # Also search through all flights if indexed lookup fails
                    if not details_updated and (not details or not isinstance(details, dict) or not details.get("flights") or not details.get("price") or not details.get("total_duration")):
                        # Try to extract based on title, option number, or flight number
                        title = tool_args.get("title", "").lower()
                        user_msg_lower = user_message.lower()
                        import re
                        
                        # First, try to find by flight number (e.g., "ME 229", "VF 1628", "AF 565")
                        flight_number_match = None
                        # Pattern: flight number like "ME 229", "ME229", "VF 1628", "AF 565", etc.
                        flight_patterns = [
                            r'([A-Z]{1,3})\s*(\d{1,4})',  # "ME 229", "VF 1628", "AF 565"
                            r'flight\s+([A-Z]{1,3})\s*(\d{1,4})',  # "flight ME 229"
                        ]
                        for pattern in flight_patterns:
                            match = re.search(pattern, title, re.IGNORECASE) or re.search(pattern, user_msg_lower, re.IGNORECASE)
                            if match:
                                airline_code = match.group(1).upper()
                                flight_num = match.group(2)
                                # Try different key formats
                                flight_keys = [
                                    f"flight_{airline_code}{flight_num}",
                                    f"flight_{airline_code}_{flight_num}",
                                    f"flight_{flight_num}",
                                ]
                                for key in flight_keys:
                                    if key in full_flight_data:
                                        print(f"[PLANNER] Found flight by flight number: {key}")
                                        flight = full_flight_data[key]
                                        tool_args["details"] = copy.deepcopy(flight)
                                        details = tool_args["details"]  # Update details variable
                                        details_updated = True
                                        # Update title with proper flight details
                                        if flight.get("flights"):
                                            first_flight = flight["flights"][0]
                                            airline = first_flight.get("airline", airline_code)
                                            dep_airport = first_flight.get("departure_airport", {})
                                            arr_airport = first_flight.get("arrival_airport", {})
                                            dep_name = dep_airport.get("name", "Unknown")
                                            arr_name = arr_airport.get("name", "Unknown")
                                            dep_time = dep_airport.get("time", "").split()[0] if dep_airport.get("time") else ""
                                            tool_args["title"] = f"Flight: {dep_name} to {arr_name} on {dep_time} - {airline} {airline_code} {flight_num}"
                                        flight_number_match = True
                                        break
                                
                                # If not found in indexed keys, search through all flights
                                if not flight_number_match:
                                    flight_result = collected_info.get("flight_result", {})
                                    all_flights = flight_result.get("outbound", []) + flight_result.get("return", [])
                                    for flight in all_flights:
                                        flight_segments = flight.get("flights", [])
                                        for segment in flight_segments:
                                            seg_flight_num = segment.get("flight_number", "").replace(" ", "").upper()
                                            target_flight_num = f"{airline_code}{flight_num}".replace(" ", "").upper()
                                            if seg_flight_num == target_flight_num or seg_flight_num.endswith(flight_num):
                                                print(f"[PLANNER] Found flight by searching all flights: {airline_code} {flight_num}")
                                                tool_args["details"] = copy.deepcopy(flight)
                                                details = tool_args["details"]  # Update details variable
                                                details_updated = True
                                                flight_number_match = True
                                                break
                                        if flight_number_match:
                                            break
                                
                                if flight_number_match:
                                    break
                        
                        # If not found by flight number, try option number
                        if not flight_number_match:
                            option_pattern = r'option\s+(\d+)'
                            option_match = re.search(option_pattern, title) or re.search(option_pattern, user_msg_lower)
                            
                            if option_match:
                                option_num = int(option_match.group(1))
                                # Determine if outbound or return based on context
                                flight_type = "outbound"  # Default
                                if "return" in title or "return" in user_msg_lower:
                                    flight_type = "return"
                                
                                key = f"{flight_type}_option_{option_num}"
                                if key in full_flight_data:
                                    print(f"[PLANNER] Extracting complete flight data for {key}")
                                    # Extract flight data (will be cleaned below)
                                    flight = full_flight_data[key]
                                    tool_args["details"] = copy.deepcopy(flight)  # Store original with booking_link
                                    details = tool_args["details"]  # Update details variable
                                    details_updated = True
                                    # Update title if needed
                                    if flight.get("flights"):
                                        first_flight = flight["flights"][0]
                                        airline = first_flight.get("airline", "Unknown")
                                        dep_airport = first_flight.get("departure_airport", {})
                                        arr_airport = first_flight.get("arrival_airport", {})
                                        dep_name = dep_airport.get("name", "Unknown")
                                        arr_name = arr_airport.get("name", "Unknown")
                                        dep_time = dep_airport.get("time", "").split()[0] if dep_airport.get("time") else ""
                                        if not tool_args.get("title") or "option" in tool_args.get("title", "").lower():
                                            tool_args["title"] = f"Flight: {dep_name} to {arr_name} - {airline} ({dep_time})"
                    
                    # Validate that we have complete flight details before proceeding
                    # Re-check details after potential updates
                    details = tool_args.get("details", {}) if not details_updated else details
                    
                    # Ensure details is a dict (not a string key reference)
                    if isinstance(details, str):
                        # This shouldn't happen if extraction worked, but handle it gracefully
                        print(f"[PLANNER] Error: details is still a string '{details}' after extraction attempt")
                        error_msg = f"Cannot add flight: Could not extract flight data from key '{details}'. Please search for flights first."
                        planner_summary.append(error_msg)
                        print(f"[PLANNER] ✗ {error_msg}")
                        continue  # Skip this tool call
                    
                    if not details or not isinstance(details, dict) or not details.get("flights") or len(details.get("flights", [])) == 0:
                        error_msg = "Cannot add flight: Flight details are incomplete. Please search for flights first to get complete flight information."
                        planner_summary.append(error_msg)
                        print(f"[PLANNER] ✗ {error_msg}")
                        continue  # Skip this tool call
                    
                    # Check if essential fields are missing (price, airports, times, duration)
                    first_flight = details.get("flights", [{}])[0] if details.get("flights") else {}
                    dep_airport = first_flight.get("departure_airport", {})
                    arr_airport = first_flight.get("arrival_airport", {})
                    
                    missing_fields = []
                    if not dep_airport or not dep_airport.get("name") or not dep_airport.get("id"):
                        missing_fields.append("departure airport")
                    if not arr_airport or not arr_airport.get("name") or not arr_airport.get("id"):
                        missing_fields.append("arrival airport")
                    if not dep_airport.get("time") or "T00:00:00" in str(dep_airport.get("time", "")):
                        missing_fields.append("departure time")
                    if not arr_airport.get("time") or "T00:00:00" in str(arr_airport.get("time", "")):
                        missing_fields.append("arrival time")
                    if not details.get("price"):
                        missing_fields.append("price")
                    if not details.get("total_duration"):
                        missing_fields.append("duration")
                    if not first_flight.get("duration"):
                        missing_fields.append("flight segment duration")
                    
                    if missing_fields:
                        error_msg = f"Cannot add flight: Missing essential information ({', '.join(missing_fields)}). Please search for flights first to get complete flight details."
                        planner_summary.append(error_msg)
                        print(f"[PLANNER] ✗ {error_msg}")
                        continue  # Skip this tool call
                    
                    # CRITICAL: Store original details (with booking_link) before cleaning
                    # We need the original for UI display, but cleaned version for DB storage
                    original_details = copy.deepcopy(details) if details else None
                    
                    # CRITICAL: Clean flight details before passing to tool
                    # Keep booking links for UI display, but they won't be sent to LLM (already stripped from context)
                    if details:
                        cleaned_details = {}
                        # Keep essential fields
                        if "flights" in details:
                            cleaned_details["flights"] = details["flights"]
                        if "layovers" in details:
                            cleaned_details["layovers"] = details["layovers"]
                        if "total_duration" in details:
                            cleaned_details["total_duration"] = details["total_duration"]
                        if "price" in details:
                            cleaned_details["price"] = details["price"]
                        if "type" in details:
                            cleaned_details["type"] = details["type"]
                        if "carbon_emissions" in details:
                            cleaned_details["carbon_emissions"] = details["carbon_emissions"]
                        if "airline_logo" in details:
                            cleaned_details["airline_logo"] = details["airline_logo"]
                        if "direction" in details:
                            cleaned_details["direction"] = details["direction"]
                        # Keep booking links for UI display (stored in DB but not sent to LLM)
                        if "google_flights_url" in details:
                            cleaned_details["google_flights_url"] = details["google_flights_url"]
                        if "booking_link" in details:
                            cleaned_details["booking_link"] = details["booking_link"]
                        if "book_with" in details:
                            cleaned_details["book_with"] = details["book_with"]
                        if "booking_price" in details:
                            cleaned_details["booking_price"] = details["booking_price"]
                        # booking_token is not needed
                        
                        tool_args["details"] = cleaned_details
                        print(f"[PLANNER] Prepared flight details: kept booking links for UI, {len(cleaned_details)} fields total")
                
                # If adding a hotel, ensure we have complete details
                original_hotel_details = None  # Initialize for UI display
                if tool_name == "agent_add_plan_item_tool" and tool_args.get("type") == "hotel":
                    # Check if details are incomplete or if we need to extract from full_hotel_data
                    details = tool_args.get("details", {})
                    details_updated = False
                    
                    # CRITICAL: Handle case where details is a string key reference (e.g., "hotel_option_2")
                    # This happens when the LLM follows the optimization instruction to pass just a key
                    if isinstance(details, str):
                        print(f"[PLANNER] Hotel details is a string key reference: '{details}', extracting from full_hotel_data...")
                        # Try to extract from full_hotel_data using the key
                        if details in full_hotel_data:
                            print(f"[PLANNER] ✓ Found key '{details}' in full_hotel_data")
                            details = copy.deepcopy(full_hotel_data[details])
                            tool_args["details"] = details
                            details_updated = True
                        else:
                            print(f"[PLANNER] Key '{details}' not found in full_hotel_data, trying to parse option number...")
                            # Try to find by option number pattern
                            import re
                            option_match = re.search(r'option[_\s]*(\d+)', details, re.IGNORECASE)
                            if option_match:
                                option_num = int(option_match.group(1))
                                key = f"hotel_option_{option_num}"
                                print(f"[PLANNER] Trying key: '{key}'")
                                if key in full_hotel_data:
                                    print(f"[PLANNER] ✓ Found hotel by option number: {key}")
                                    details = copy.deepcopy(full_hotel_data[key])
                                    tool_args["details"] = details
                                    details_updated = True
                                else:
                                    print(f"[PLANNER] ⚠ Key '{key}' not found. Available keys: {list(full_hotel_data.keys())[:10]}")
                            else:
                                print(f"[PLANNER] ⚠ Could not parse option number from '{details}'")
                            
                            # If still not found, try to extract from hotel_result directly
                            if not details_updated:
                                print(f"[PLANNER] Trying to extract from hotel_result directly...")
                                hotel_result = collected_info.get("hotel_result", {})
                                hotels = hotel_result.get("hotels", [])
                                
                                # Try to parse option number from the string
                                import re
                                option_match = re.search(r'(\d+)', details)
                                if option_match:
                                    option_num = int(option_match.group(1))
                                    
                                    if hotels and 1 <= option_num <= len(hotels):
                                        # Option numbers are 1-indexed, list is 0-indexed
                                        hotel = hotels[option_num - 1]
                                        print(f"[PLANNER] ✓ Extracted hotel from hotels list at index {option_num - 1}")
                                        details = copy.deepcopy(hotel)
                                        tool_args["details"] = details
                                        details_updated = True
                                    else:
                                        print(f"[PLANNER] ⚠ Option {option_num} out of range for hotels list (has {len(hotels)} items)")
                    
                    # If details are missing or incomplete, try to extract from full_hotel_data
                    if not details_updated and (not details or not isinstance(details, dict) or not details.get("name")):
                        # Try to extract based on title or option number
                        title = tool_args.get("title", "").lower()
                        user_msg_lower = user_message.lower()
                        import re
                        
                        # Try option number
                        option_pattern = r'option\s+(\d+)'
                        option_match = re.search(option_pattern, title) or re.search(option_pattern, user_msg_lower)
                        
                        if option_match:
                            option_num = int(option_match.group(1))
                            key = f"hotel_option_{option_num}"
                            if key in full_hotel_data:
                                print(f"[PLANNER] Extracting complete hotel data for {key}")
                                hotel = full_hotel_data[key]
                                tool_args["details"] = copy.deepcopy(hotel)
                                details = tool_args["details"]
                                details_updated = True
                    
                    # Validate that we have complete hotel details before proceeding
                    details = tool_args.get("details", {}) if not details_updated else details
                    
                    # Ensure details is a dict (not a string key reference)
                    if isinstance(details, str):
                        print(f"[PLANNER] Error: hotel details is still a string '{details}' after extraction attempt")
                        error_msg = f"Cannot add hotel: Could not extract hotel data from key '{details}'. Please search for hotels first."
                        planner_summary.append(error_msg)
                        print(f"[PLANNER] ✗ {error_msg}")
                        continue  # Skip this tool call
                    
                    if not details or not isinstance(details, dict) or not details.get("name"):
                        error_msg = "Cannot add hotel: Hotel details are incomplete. Please search for hotels first to get complete hotel information."
                        planner_summary.append(error_msg)
                        print(f"[PLANNER] ✗ {error_msg}")
                        continue  # Skip this tool call
                    
                    # Store original hotel details for UI display
                    original_hotel_details = copy.deepcopy(details) if details else None
                    
                    # Ensure location field exists for frontend display
                    if details and not details.get("location"):
                        # Construct location from available fields
                        location_parts = []
                        if details.get("address"):
                            location_parts.append(details["address"])
                        if details.get("city"):
                            location_parts.append(details["city"])
                        if details.get("country"):
                            location_parts.append(details["country"])
                        if location_parts:
                            details["location"] = ", ".join(location_parts)
                    
                    # Clean hotel details if needed (remove very long fields, keep essential ones)
                    if details:
                        # Keep all essential hotel fields - hotels don't have booking_link issues like flights
                        # But we can still clean up if there are any problematic fields
                        cleaned_hotel_details = {}
                        # Keep essential fields
                        if "name" in details:
                            cleaned_hotel_details["name"] = details["name"]
                        if "address" in details:
                            cleaned_hotel_details["address"] = details["address"]
                        if "location" in details:
                            cleaned_hotel_details["location"] = details["location"]
                        if "city" in details:
                            cleaned_hotel_details["city"] = details["city"]
                        if "country" in details:
                            cleaned_hotel_details["country"] = details["country"]
                        if "rating" in details:
                            cleaned_hotel_details["rating"] = details["rating"]
                        if "description" in details:
                            cleaned_hotel_details["description"] = details["description"]
                        if "roomTypes" in details:
                            cleaned_hotel_details["roomTypes"] = details["roomTypes"]
                        if "hotel_id" in details:
                            cleaned_hotel_details["hotel_id"] = details["hotel_id"]
                        if "latitude" in details:
                            cleaned_hotel_details["latitude"] = details["latitude"]
                        if "longitude" in details:
                            cleaned_hotel_details["longitude"] = details["longitude"]
                        if "images" in details:
                            cleaned_hotel_details["images"] = details["images"]
                        if "amenities" in details:
                            cleaned_hotel_details["amenities"] = details["amenities"]
                        
                        tool_args["details"] = cleaned_hotel_details
                        print(f"[PLANNER] Prepared hotel details with {len(cleaned_hotel_details)} fields (name: {cleaned_hotel_details.get('name', 'N/A')}, location: {cleaned_hotel_details.get('location', 'N/A')})")
                
                # Add user_email and session_id to all tool calls
                tool_args["user_email"] = user_email
                tool_args["session_id"] = session_id
                
                result = await PlannerAgentClient.invoke(tool_name, **tool_args)
                
                if result.get("success"):
                    action = result.get("action", "performed")
                    msg = result.get("message", "Operation completed")
                    planner_summary.append(f"{action.capitalize()}: {msg}")
                    print(f"[PLANNER] ✓ {msg}")

                    # Capture selected items so the UI only shows confirmed options
                    # IMPORTANT: Use original_details (with booking_link) for UI display, not cleaned_details
                    if tool_name == "agent_add_plan_item_tool":
                        selection_type = tool_args.get("type")
                        if selection_type == "flight":
                            # Try to get original flight with booking_link for UI display
                            display_details = original_details if original_details else tool_args.get("details")
                            
                            # If display_details doesn't have booking_link, try to find it from full_flight_data
                            if display_details and not display_details.get("booking_link"):
                                # Try to match by flight number to get original with booking_link
                                if display_details.get("flights") and len(display_details["flights"]) > 0:
                                    flight_number = display_details["flights"][0].get("flight_number", "")
                                    # Search in full_flight_data for matching flight
                                    for key, original_flight in full_flight_data.items():
                                        if original_flight.get("flights") and len(original_flight["flights"]) > 0:
                                            if original_flight["flights"][0].get("flight_number") == flight_number:
                                                if original_flight.get("booking_link"):
                                                    # Merge booking_link from original
                                                    display_details["booking_link"] = original_flight["booking_link"]
                                                    print(f"[PLANNER] Restored booking_link from full_flight_data for flight {flight_number}")
                                                    break
                            
                            if display_details:
                                _append_selected_result(
                                    "flight_result",
                                    "outbound",
                                    display_details
                                )
                        elif selection_type == "hotel":
                            # Use original hotel details for UI display (if available)
                            hotel_details = original_hotel_details if original_hotel_details else tool_args.get("details")
                            if hotel_details:
                                _append_selected_result(
                                    "hotel_result",
                                    "hotels",
                                    hotel_details
                                )
                        elif selection_type in ("restaurant", "activity"):
                            # Use original restaurant/activity details for UI display (if available)
                            restaurant_details = original_restaurant_details if original_restaurant_details else tool_args.get("details")
                            if restaurant_details:
                                _append_selected_result(
                                    "tripadvisor_result",
                                    "data",
                                    restaurant_details
                                )
                else:
                    error_msg = result.get("message", "Unknown error")
                    planner_summary.append(f"Error: {error_msg}")
                    print(f"[PLANNER] ✗ {error_msg}")
            except Exception as e:
                error_msg = f"Error calling {tool_name}: {str(e)}"
                planner_summary.append(error_msg)
                print(f"[PLANNER] ✗ {error_msg}")
        
        # If no tool calls were made, check if user just wants to view plan
        if not tool_calls:
            if "show" in user_msg_lower or "view" in user_msg_lower or "what" in user_msg_lower or "list" in user_msg_lower:
                # Get current plan items
                try:
                    result = await PlannerAgentClient.invoke(
                        "agent_get_plan_items_tool",
                        user_email=user_email,
                        session_id=session_id
                    )
                    if result.get("success"):
                        items = result.get("items", [])
                        travel_plan_items = items
                        planner_summary.append(f"Retrieved {len(items)} plan items")
                except Exception as e:
                    print(f"[PLANNER] Error retrieving plan items: {e}")
            else:
                # User wants to save/select but no results available
                if not collected_info.get("flight_result") and not collected_info.get("hotel_result") and not collected_info.get("tripadvisor_result"):
                    planner_summary.append("No search results available. Please search for flights, hotels, or other options first, then I can help you save your selection.")
                    print("[PLANNER] No results available for selection")
        
        # CRITICAL: Refresh travel_plan_items from database AFTER all tool calls complete
        # This ensures we have the latest data including any items that were just added/updated/deleted
        if tool_calls and any(tool_call.function.name in ["agent_add_plan_item_tool", "agent_update_plan_item_tool", "agent_delete_plan_item_tool"] for tool_call in tool_calls):
            try:
                refresh_result = await PlannerAgentClient.invoke(
                    "agent_get_plan_items_tool",
                    user_email=user_email,
                    session_id=session_id
                )
                if refresh_result.get("success"):
                    travel_plan_items = refresh_result.get("items", [])
                    print(f"[PLANNER] ✓ Refreshed travel plan items from database after operations: {len(travel_plan_items)} items")
            except Exception as e:
                print(f"[PLANNER] Warning: Could not refresh travel plan items after operations: {e}")
        
        # Update state
        updated_state = state.copy()
        updated_state["travel_plan_items"] = travel_plan_items
        updated_state["needs_planner"] = len(tool_calls) > 0
        updated_state["route"] = "planner_feedback"
        updated_state["context"] = selected_context
        
        # CRITICAL: Preserve original full flight/hotel lists when storing selected items
        # This ensures that when user says "add flight ME 229", we still have the full list
        # to search through, not just the previously selected flight
        updated_collected_info = {}
        
        # Check if restaurants/activities were added - if so, clear tripadvisor_result
        restaurants_added = any(
            tool_call.function.name == "agent_add_plan_item_tool" 
            and json.loads(tool_call.function.arguments).get("type") in ("restaurant", "activity")
            for tool_call in tool_calls
        )
        
        if selected_context:
            # If we have selected items, merge with original full results
            # This preserves the full flight list for future lookups
            original_flight_result = collected_info.get("flight_result")
            selected_flight_result = selected_context.get("flight_result")
            
            if original_flight_result and selected_flight_result:
                # Preserve the original full list, but also include selected items in context
                # The original full list should remain in STM for future lookups
                updated_collected_info["flight_result"] = original_flight_result
                # Store selected items separately in context for UI display
                updated_state["context"] = selected_context
            elif selected_flight_result:
                # Only selected items, no original - use selected
                updated_collected_info["flight_result"] = selected_flight_result
            else:
                # No flight results in selected context - preserve original if exists
                if original_flight_result:
                    updated_collected_info["flight_result"] = original_flight_result
            
            # Same logic for hotels
            original_hotel_result = collected_info.get("hotel_result")
            selected_hotel_result = selected_context.get("hotel_result")
            if original_hotel_result and selected_hotel_result:
                updated_collected_info["hotel_result"] = original_hotel_result
            elif selected_hotel_result:
                updated_collected_info["hotel_result"] = selected_hotel_result
            elif original_hotel_result:
                updated_collected_info["hotel_result"] = original_hotel_result
            
            # Preserve other result types (but exclude tripadvisor_result if restaurants were added)
            for key in ["visa_result", "utilities_result"]:
                if collected_info.get(key):
                    updated_collected_info[key] = collected_info[key]
            
            # Only preserve tripadvisor_result if restaurants were NOT added
            if not restaurants_added and collected_info.get("tripadvisor_result"):
                updated_collected_info["tripadvisor_result"] = collected_info["tripadvisor_result"]
        else:
            # No selected items - preserve original collected_info (but exclude tripadvisor_result if restaurants were added)
            if restaurants_added:
                updated_collected_info = copy.deepcopy(collected_info) if collected_info else {}
                updated_collected_info.pop("tripadvisor_result", None)
            else:
                updated_collected_info = copy.deepcopy(collected_info) if collected_info else {}
        
        updated_state["collected_info"] = updated_collected_info

        # Clear stale search results so the conversational agent doesn't
        # re-display entire lists after a specific selection.
        updated_state["flight_result"] = None
        updated_state["hotel_result"] = None
        updated_state["tripadvisor_result"] = None
        updated_state["utilities_result"] = None
        updated_state["visa_result"] = None
        
        # Store planner summary for feedback node
        if planner_summary:
            updated_state["last_response"] = "\n".join(planner_summary)
        elif not tool_calls and not collected_info.get("flight_result") and not collected_info.get("hotel_result"):
            # No tool calls and no results - set a helpful message
            updated_state["last_response"] = "I don't see any search results available right now. Could you please search for flights or hotels first? Once you see the options, I can help you save your selection (e.g., 'I want option 3')."
        
    except Exception as e:
        print(f"[PLANNER] Error in planner agent: {e}")
        import traceback
        traceback.print_exc()
        updated_state = state.copy()
        updated_state["needs_planner"] = False
        updated_state["route"] = "planner_feedback"
        updated_state["last_response"] = f"Error processing planner request: {str(e)}"
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"[{end_time.strftime('%H:%M:%S.%f')[:-3]}] 📋 PLANNER AGENT COMPLETED ({duration:.2f}s)")
    print(f"[PLANNER] Routing to: planner_feedback")
    
    return updated_state

