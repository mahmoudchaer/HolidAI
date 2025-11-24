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

IMPORTANT WORKFLOW:
1. Analyze the user message to understand their intent - use SEMANTIC understanding, not just keywords:
   - "I want option 2" / "save option 2" / "select option 2" / "add option 2" → Add item
   - "I liked hotel X" / "save flight Y" / "add hotel X" → Add item
   - "remove X" / "delete Y" / "cancel Z" → Delete item
   - "update X" / "change Y" / "modify Z" → Update item
   - "add X instead of Y" / "replace Y with X" / "change Y to X" → DELETE Y, then ADD X (two operations: delete then add)
   - "show my plan" / "what's in my plan" → Get items

2. Extract the item details from the collected_info (flight_result, hotel_result, etc.) based on the user's selection
   - If user says "option 2", find the 2nd item in the relevant result array
   - Extract all relevant details (price, dates, location, etc.)

3. Call the appropriate tool(s) to perform the operation

4. Provide a summary of what was done

CRITICAL: You MUST use the tools to perform operations. Do NOT just respond without calling tools."""


async def planner_agent_node(state: AgentState) -> AgentState:
    """Planner Agent node that manages travel plan items.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with planner operations completed
    """
    from datetime import datetime
    start_time = datetime.now()
    print(f"[{start_time.strftime('%H:%M:%S.%f')[:-3]}] 📋 PLANNER AGENT STARTED")
    
    user_message = state.get("user_message", "")
    user_email = state.get("user_email")
    session_id = state.get("session_id")
    collected_info = state.get("collected_info", {})
    context = state.get("context", {}) or {}
    travel_plan_items = state.get("travel_plan_items", [])
    
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
    planner_keywords = [
        "save", "select", "choose", "want", "like", "add to plan", "add to my plan",
        "remove", "delete", "cancel", "update", "change", "modify",
        "show my plan", "what's in my plan", "my plan", "travel plan"
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
        
        # Build context about available results - include FULL details for extraction
        results_context = ""
        full_flight_data = {}  # Store full flight data for extraction
        
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
                    position_label = " (LAST)" if i == len(outbound) else " (FIRST)" if i == 1 else ""
                    results_context += f"  Option {i}{position_label}: {airline} - {departure} to {arrival} - ${price}\n"
                    # Store full flight data for extraction (by both number and semantic position)
                    full_flight_data[f"outbound_option_{i}"] = flight
                    if i == 1:
                        full_flight_data["outbound_first"] = flight
                    if i == len(outbound):
                        full_flight_data["outbound_last"] = flight
            
            if return_flights:
                results_context += f"Return flights ({len(return_flights)} options, numbered 1 to {len(return_flights)}):\n"
                for i, flight in enumerate(return_flights[:10], 1):
                    price = flight.get("price", "N/A")
                    airline = flight.get("flights", [{}])[0].get("airline", "Unknown") if flight.get("flights") else "Unknown"
                    departure = flight.get("flights", [{}])[0].get("departure_airport", {}).get("name", "Unknown") if flight.get("flights") else "Unknown"
                    arrival = flight.get("flights", [{}])[0].get("arrival_airport", {}).get("name", "Unknown") if flight.get("flights") else "Unknown"
                    position_label = " (LAST)" if i == len(return_flights) else " (FIRST)" if i == 1 else ""
                    results_context += f"  Option {i}{position_label}: {airline} - {departure} to {arrival} - ${price}\n"
                    # Store full flight data for extraction (by both number and semantic position)
                    full_flight_data[f"return_option_{i}"] = flight
                    if i == 1:
                        full_flight_data["return_first"] = flight
                    if i == len(return_flights):
                        full_flight_data["return_last"] = flight
        
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
        
        if collected_info.get("tripadvisor_result"):
            tripadvisor_result = collected_info["tripadvisor_result"]
            locations = tripadvisor_result.get("data", [])
            if locations:
                results_context += f"\n\nAvailable location/restaurant results ({len(locations)} options):\n"
                for i, loc in enumerate(locations[:10], 1):
                    name = loc.get("name", "Unknown")
                    results_context += f"  Option {i}: {name}\n"
        
        # Include full flight and hotel data in JSON format for extraction
        full_data_context = ""
        if full_flight_data:
            full_data_context += f"\n\nFULL FLIGHT DATA (use this to extract complete details when saving):\n{json.dumps(full_flight_data, indent=2, default=str)}\n\n**SEMANTIC MAPPING FOR OPTION REFERENCES:**\n"
            full_data_context += "- 'last option' / 'last one' → Use 'outbound_last' or 'return_last' key\n"
            full_data_context += "- 'first option' / 'first one' → Use 'outbound_first' or 'return_first' key\n"
            full_data_context += "- 'option X' (e.g., 'option 3') → Use 'outbound_option_X' or 'return_option_X' key\n"
            full_data_context += "- 'cheapest' → Find the flight with lowest price from all options\n"
            full_data_context += "- 'most expensive' → Find the flight with highest price from all options\n"
            full_data_context += "\nExtract the complete flight object from the corresponding key and save ALL details in the 'details' field."
        else:
            # No flight data available - make this clear
            full_data_context += "\n\n NO FLIGHT DATA AVAILABLE: The user is asking to save an option, but no flight search results are available. You MUST inform the user that they need to search for flights first before they can save an option."
        
        if full_hotel_data:
            full_data_context += f"\n\nFULL HOTEL DATA (use this to extract complete details when saving):\n{json.dumps(full_hotel_data, indent=2, default=str)}\n\nWhen user says 'option X' or mentions a hotel name (e.g., 'add Le Meridien Fairway', 'add meridien fairway'), find the matching hotel:\n- If they say 'option X', use 'hotel_option_X' key\n- If they mention a hotel name, search for a matching key like 'hotel_name_*' (names are normalized: lowercase, spaces/hyphens become underscores)\n- Extract the COMPLETE hotel object (all fields: name, address, rating, roomTypes, etc.) and save ALL details in the 'details' field."
        elif collected_info.get("hotel_result") and not collected_info.get("hotel_result", {}).get("hotels"):
            full_data_context += "\n\n NO HOTEL DATA AVAILABLE: The user is asking to save a hotel, but no hotel search results are available. You MUST inform the user that they need to search for hotels first before they can save one."
        
        agent_message = f"""User message: {user_message}

Current travel plan items ({len(travel_plan_items)} items):
{json.dumps(travel_plan_items, indent=2, default=str) if travel_plan_items else "No items in plan yet"}

Available results from agents:{results_context if results_context else "\n\n⚠️ No results available yet. If the user wants to save an item, they need to search first (e.g., 'find flights to Paris') to see options."}
{full_data_context}

User email: {user_email}
Session ID: {session_id}

CRITICAL INSTRUCTIONS:
1. Analyze the user's intent (add, update, delete, or view plan items) - understand the SEMANTIC meaning, not just keywords
2. **HANDLING "INSTEAD OF" / "REPLACE" SCENARIOS** (CRITICAL):
   - If user says "add X instead of Y" or "replace Y with X" or "change Y to X":
     * FIRST: Find Y in the current travel plan items (check the "Current travel plan items" section above)
     * SECOND: Call agent_delete_plan_item_tool to remove Y (you'll need the item's ID from travel_plan_items)
     * THIRD: Find X in the available results (FULL HOTEL DATA or FULL FLIGHT DATA)
     * FOURTH: Call agent_add_plan_item_tool to add X
     * This requires TWO tool calls: delete then add
3. **SEMANTIC UNDERSTANDING OF OPTION REFERENCES** (CRITICAL):
   - "last option" / "last one" / "the last flight" → Find the LAST item in the list (highest index number, use 'outbound_last' or 'return_last' key)
   - "first option" / "first one" / "the first flight" → Find the FIRST item in the list (index 1, use 'outbound_first' or 'return_first' key)
   - "second option" / "second one" → Find the SECOND item (index 2)
   - "third option" / "third one" → Find the THIRD item (index 3)
   - "option X" (e.g., "option 3") → Find the Xth item (index X)
   - "cheapest" / "cheapest one" → Find the item with the LOWEST price
   - "most expensive" / "expensive one" → Find the item with the HIGHEST price
   - Use your understanding of the context - if user says "last option" after seeing 9 flights, they mean the 9th flight (the one at the end of the list)
4. If user mentions a hotel name (e.g., "add Le Meridien Fairway", "add meridien fairway"), search the FULL HOTEL DATA for a matching hotel name (case-insensitive, partial matches OK - e.g., "meridien fairway" matches "Le Meridien Fairway")
5. Extract the COMPLETE flight/hotel object (all fields: flights, price, duration, carbon_emissions, booking_token for flights; name, address, rating, roomTypes, etc. for hotels)
6. When calling agent_add_plan_item_tool:
   - For flights: title like "Flight: Beirut to Dubai on Dec 1, 2025 - Emirates EK 958", type: "flight"
   - For hotels: title like "Hotel: Le Meridien Fairway, Dubai", type: "hotel"
   - details: Pass the COMPLETE flight/hotel object (all fields) - this is critical!
   - status: "not_booked"
7. When calling agent_delete_plan_item_tool:
   - You need the item's ID from the "Current travel plan items" section
   - Match by title or details to find the correct item ID
8. If no results are available, inform them they need to search first

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
        
        # Call LLM with function calling
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            tools=functions if functions else None,
            tool_choice="auto" if functions else None,
            temperature=0.3
        )
        
        message = response.choices[0].message
        tool_calls = message.tool_calls or []
        
        planner_summary = []
        
        # Execute tool calls
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)
            
            print(f"[PLANNER] Calling tool: {tool_name} with args: {tool_args}")
            
            try:
                # If adding a plan item, ensure we have complete details
                if tool_name == "agent_add_plan_item_tool" and tool_args.get("type") == "flight":
                    # Check if details are incomplete or if we need to extract from full_flight_data
                    details = tool_args.get("details", {})
                    
                    # If details are missing or incomplete, try to extract from full_flight_data
                    if not details or not details.get("flights"):
                        # Try to extract based on title or option number
                        title = tool_args.get("title", "").lower()
                        option_match = None
                        
                        # Look for "option X" in title or user message
                        import re
                        option_pattern = r'option\s+(\d+)'
                        option_match = re.search(option_pattern, title) or re.search(option_pattern, user_message.lower())
                        
                        if option_match:
                            option_num = int(option_match.group(1))
                            # Determine if outbound or return based on context
                            flight_type = "outbound"  # Default
                            if "return" in title or "return" in user_message.lower():
                                flight_type = "return"
                            
                            key = f"{flight_type}_option_{option_num}"
                            if key in full_flight_data:
                                print(f"[PLANNER] Extracting complete flight data for {key}")
                                tool_args["details"] = full_flight_data[key]
                                # Update title if needed
                                flight = full_flight_data[key]
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
                    if tool_name == "agent_add_plan_item_tool":
                        selection_type = tool_args.get("type")
                        details = tool_args.get("details")
                        if selection_type == "flight" and details:
                            _append_selected_result(
                                "flight_result",
                                "outbound",
                                details
                            )
                        elif selection_type == "hotel" and details:
                            _append_selected_result(
                                "hotel_result",
                                "hotels",
                                details
                            )
                        elif selection_type in ("restaurant", "activity") and details:
                            # For restaurant/activity selections we prefer a simple
                            # textual confirmation instead of redisplaying cards,
                            # so skip pushing TripAdvisor data into context.
                            pass
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
        
        # Update state
        updated_state = state.copy()
        updated_state["travel_plan_items"] = travel_plan_items
        updated_state["needs_planner"] = len(tool_calls) > 0
        updated_state["route"] = "planner_feedback"
        updated_state["context"] = selected_context
        updated_state["collected_info"] = copy.deepcopy(selected_context) if selected_context else {}

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

