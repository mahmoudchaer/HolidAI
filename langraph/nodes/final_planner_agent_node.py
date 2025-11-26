"""Final Planner Agent node - runs AFTER conversational agent to update the plan.

This is a full LLM-guided planner agent, similar to the main planner, but:
- It runs ONLY at the end of the graph (after conversational_agent + feedback)
- It NEVER re-runs searches (no flight/hotel/restaurant tools)
- It ONLY calls planner tools: add/update/delete/get plan items
- It bases decisions on:
  * The latest user message
  * The conversational agent's final response (last_response)
  * Existing results in state/STM (flight_result, hotel_result, etc.)

Examples of what it can do:
- "add the cheapest flight to my plan"
- "add the first and second hotel to my plan"
- "remove the Jazeera flight from my plan"
- "mark my Dubai hotel as booked"
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List

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


def get_final_planner_prompt() -> str:
    """System prompt for the final planner agent."""
    return """You are the FINAL PLANNER AGENT in a multi-agent travel assistant system.

ARCHITECTURE (IMPORTANT):
- Other agents have ALREADY searched for flights/hotels/visas/etc. and shown results to the user.
- The conversational_agent has ALREADY generated a natural-language response with flight/hotel information.
- YOUR JOB now is ONLY to manage the user's TRAVEL PLAN in the database.
- You MUST use the following tools to update the plan:
  - agent_add_plan_item_tool
  - agent_update_plan_item_tool
  - agent_delete_plan_item_tool
  - agent_get_plan_items_tool

ABSOLUTE RULES:
- NEVER re-run any searches (no flight/hotel/restaurant tools).
- NEVER generate user-facing text. The user will NOT see your output.
- ONLY decide which planner tools to call and with what arguments.
- You can add/update/delete MULTIPLE items in one turn if the user asked for it.

INPUT YOU SEE:
- user_message: the latest user message in this turn.
- last_response: the conversational agent's final response text for this turn.
- flight_result / hotel_result / other results in collected state: full data of what was shown.
- travel_plan_items: current contents of the user's plan.
- user_email: The actual user's email address (MUST be used in all tool calls).
- session_id: The actual session ID (MUST be used in all tool calls).

CRITICAL REASONING PROCESS:
1. **ANALYZE USER INTENT**: Read the user_message carefully and understand what the user wants.
   - Does the user want to SAVE/ADD something to their travel plan?
   - Does the user want to REMOVE/DELETE something from their plan?
   - Does the user want to UPDATE/MODIFY something in their plan?
   - Is the user just asking a question or viewing information (NOT a plan operation)?

2. **ANALYZE CONVERSATIONAL AGENT RESPONSE**: Read the last_response to understand what was shown to the user.
   - What items were displayed (flights, hotels, etc.)?
   - Did the conversational agent confirm something was saved?
   - What context does the response provide about what the user might want to save?

3. **ANALYZE AVAILABLE DATA**: Check what data is available in flight_result, hotel_result, etc.
   - What specific items are available to save?
   - Can you identify which item the user is referring to (e.g., "this one", "the cheapest", "option 2")?

4. **DECIDE WHETHER TO CALL TOOLS**:
   - If the user explicitly wants to save/add/remove/update items → CALL the appropriate planner tools
   - If the user is just asking questions or viewing information → DO NOT call any tools
   - Use semantic understanding, not keyword matching

EXAMPLES OF REASONING:

Example 1:
- user_message: "can u save this one to my plan: MEA Flight ME 431..."
- last_response: "I've found several flights. Here are your options..."
- Reasoning: User explicitly says "save this one" and provides flight details. This is a clear save request.
- Action: Call agent_add_plan_item_tool with the MEA flight details.

Example 2:
- user_message: "what's the cheapest flight?"
- last_response: "The cheapest flight is Emirates at $450..."
- Reasoning: User is asking a question, not requesting to save anything.
- Action: Do NOT call any tools.

Example 3:
- user_message: "add the cheapest flight to my plan"
- last_response: "Here are your flight options..."
- flight_result: Has outbound flights with prices
- Reasoning: User wants to add the cheapest flight. I need to find the cheapest from flight_result and save it.
- Action: Call agent_add_plan_item_tool with the cheapest flight.

Example 4:
- user_message: "remove the MEA flight"
- travel_plan_items: Contains a flight with "MEA" in the title
- Reasoning: User wants to delete an existing plan item.
- Action: Call agent_delete_plan_item_tool for the MEA flight.

CRITICAL: When calling planner tools, you MUST use the user_email and session_id provided in the context. NEVER use placeholder values like "user@email.com" or "session_123". Always use the exact values provided.

Your output is ONLY function/tool calls. Do NOT return any normal text. If no plan operations are needed, do NOT call any tools.
"""


async def final_planner_agent_node(state: AgentState) -> AgentState:
    """Final Planner Agent node that runs AFTER conversational agent to update plan."""
    from datetime import datetime
    import json

    start_time = datetime.now()
    print(f"[{start_time.strftime('%H:%M:%S.%f')[:-3]}] 📋 FINAL PLANNER AGENT STARTED")

    user_message = state.get("user_message", "") or ""
    last_response = state.get("last_response", "") or ""
    user_email = state.get("user_email")
    session_id = state.get("session_id")
    collected_info = state.get("collected_info", {}) or {}
    travel_plan_items = state.get("travel_plan_items", []) or []

    # Default: no changes, route to end
    updated_state: Dict[str, Any] = {"route": "end"}

    # Safety checks
    if not user_email or not session_id:
        print("[FINAL PLANNER] Missing user_email or session_id - skipping plan update")
        return updated_state

    print("[FINAL PLANNER] Analyzing user intent with LLM reasoning (no keyword filtering)")

    # Get tools available to planner agent
    tools = await PlannerAgentClient.list_tools()

    # Build function calling schema
    functions: List[Dict[str, Any]] = []

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
            "agent_get_plan_items_tool",
        ]:
            input_schema = tool.get("inputSchema", {})
            input_schema = _sanitize_schema(input_schema)
            functions.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", "Planner operation tool"),
                        "parameters": input_schema,
                    },
                }
            )

    if not functions:
        print("[FINAL PLANNER] No planner tools available - skipping")
        return updated_state

    # Prepare MINIMAL context for LLM reasoning (only essential data, no booking links)
    flight_result_data = collected_info.get("flight_result")
    hotel_result_data = collected_info.get("hotel_result")
    
    # Strip flight data to essentials only (remove booking links, large fields)
    def _strip_flight_data(flight_result):
        """Strip flight result to only essential fields needed for saving."""
        if not flight_result or not isinstance(flight_result, dict):
            return flight_result
        import copy
        stripped = copy.deepcopy(flight_result)
        # Keep only essential structure
        if "outbound" in stripped and isinstance(stripped["outbound"], list):
            stripped["outbound"] = [_strip_single_flight(f) for f in stripped["outbound"][:10]]
        if "return" in stripped and isinstance(stripped["return"], list):
            stripped["return"] = [_strip_single_flight(f) for f in stripped["return"][:10]]
        return stripped
    
    def _strip_single_flight(flight):
        """Strip a single flight to essentials."""
        import copy
        stripped = copy.deepcopy(flight)
        # Remove large/unnecessary fields
        stripped.pop("booking_link", None)
        stripped.pop("booking_token", None)
        stripped.pop("book_with", None)
        stripped.pop("booking_price", None)
        # Keep only essential fields
        essential = {
            "flights": stripped.get("flights", []),
            "price": stripped.get("price"),
            "total_duration": stripped.get("total_duration"),
            "type": stripped.get("type", "One way"),
            "google_flights_url": stripped.get("google_flights_url"),  # Keep for reference
            "direction": stripped.get("direction"),
            "airline_logo": stripped.get("airline_logo"),
        }
        # Clean flight segments
        if essential.get("flights"):
            cleaned_segments = []
            for seg in essential["flights"]:
                cleaned_seg = {
                    "airline": seg.get("airline"),
                    "flight_number": seg.get("flight_number"),
                    "departure_airport": seg.get("departure_airport"),
                    "arrival_airport": seg.get("arrival_airport"),
                    "duration": seg.get("duration"),
                    "travel_class": seg.get("travel_class"),
                    "airplane": seg.get("airplane"),
                    "legroom": seg.get("legroom"),
                }
                cleaned_segments.append(cleaned_seg)
            essential["flights"] = cleaned_segments
        return essential
    
    if flight_result_data:
        flight_result_data = _strip_flight_data(flight_result_data)
    
    # Build comprehensive context for LLM
    llm_context = {
        "user_message": user_message,
        "conversational_agent_response": last_response,
        "user_email": user_email,  # CRITICAL: Pass actual user_email
        "session_id": session_id,  # CRITICAL: Pass actual session_id
        "current_plan_items_count": len(travel_plan_items),
    }
    
    # Include MINIMAL flight data if available (for LLM to identify which flight to save)
    if flight_result_data and isinstance(flight_result_data, dict) and not flight_result_data.get("error"):
        outbound = flight_result_data.get("outbound", [])
        returns = flight_result_data.get("return", [])
        llm_context["available_flights"] = {
            "outbound_count": len(outbound),
            "return_count": len(returns),
            "outbound_sample": outbound[:3] if outbound else [],  # First 3 for context
            "return_sample": returns[:3] if returns else [],  # First 3 for context
        }
        # If user mentions a specific flight, include full data
        if len(outbound) <= 5 and len(returns) <= 5:
            llm_context["available_flights"]["all_outbound"] = outbound
            llm_context["available_flights"]["all_return"] = returns
    
    # Include hotel data if available
    if hotel_result_data and isinstance(hotel_result_data, dict) and not hotel_result_data.get("error"):
        hotels = hotel_result_data.get("hotels", [])
        llm_context["available_hotels"] = {
            "count": len(hotels),
            "sample": hotels[:3] if hotels else [],  # First 3 for context
        }
        if len(hotels) <= 5:
            llm_context["available_hotels"]["all"] = hotels
    
    # Include current plan items (for delete/update operations)
    if travel_plan_items:
        llm_context["current_plan_items"] = [
            {"title": item.get("title"), "type": item.get("type"), "status": item.get("status")}
            for item in travel_plan_items[:10]  # First 10 for context
        ]

    # Prepare messages for LLM
    prompt = get_final_planner_prompt()

    llm_user_content = {
        **llm_context,
        "instruction": "Analyze the user's intent using the information above. Decide whether plan operations (add/update/delete) are needed. Use semantic reasoning, not keyword matching. If the user wants to save/add/remove/update items, call the appropriate planner tools. If the user is just asking questions or viewing information, do NOT call any tools. ALWAYS use the provided user_email and session_id in all tool calls - NEVER use placeholder values.",
    }

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(llm_user_content, ensure_ascii=False)},
    ]

    print("[FINAL PLANNER] Calling LLM for planner tool decisions")

    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            tools=functions,
            tool_choice="auto",
            temperature=0,
        )

        message = response.choices[0].message

        if not message.tool_calls:
            print("[FINAL PLANNER] LLM did not request any planner tool calls - no plan changes")
            return updated_state

        import json as _json

        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            raw_args = tool_call.function.arguments or "{}"
            try:
                args = _json.loads(raw_args)
            except Exception as e:
                print(f"[FINAL PLANNER] ERROR parsing tool args for {tool_name}: {e}")
                continue

            print(f"[FINAL PLANNER] Executing planner tool: {tool_name} with args={args}")

            # ALWAYS override with actual values (LLM might provide placeholders)
            args["user_email"] = user_email
            args["session_id"] = session_id
            print(f"[FINAL PLANNER] Using user_email={user_email}, session_id={session_id}")

            # Fix hotel data structure for frontend compatibility
            if tool_name == "agent_add_plan_item_tool" and args.get("type") == "hotel":
                details = args.get("details", {})
                # Frontend expects details.name and details.location, but planner might save hotel_name and address
                if details:
                    if "hotel_name" in details and "name" not in details:
                        details["name"] = details.pop("hotel_name")
                    if "address" in details and "location" not in details:
                        details["location"] = details.pop("address")
                    # Also ensure date is set if trip_month_year exists
                    if "trip_month_year" in details and "date" not in details:
                        details["date"] = details.get("trip_month_year", "")
                    args["details"] = details
                    print(f"[FINAL PLANNER] Fixed hotel data structure: mapped hotel_name->name, address->location")
            
            # Fix flight data structure for frontend compatibility
            if tool_name == "agent_add_plan_item_tool" and args.get("type") == "flight":
                details = args.get("details", {})
                
                # CRITICAL: Frontend expects details.flights[0].departure_airport and arrival_airport as OBJECTS with name/id/time
                # If airports are strings at top level, convert them to proper structure
                if "flights" not in details or not details.get("flights") or len(details.get("flights", [])) == 0:
                    # Need to create flights array from top-level data
                    flight_data = {}
                    
                    # Convert string airports to objects if needed
                    dep_airport_str = details.get("departure_airport")
                    arr_airport_str = details.get("arrival_airport")
                    
                    if isinstance(dep_airport_str, str):
                        # Parse "Beirut-Rafic Hariri International Airport (BEY)" -> {name: "...", id: "BEY"}
                        import re
                        match = re.search(r'\(([A-Z]{3})\)', dep_airport_str)
                        airport_id = match.group(1) if match else dep_airport_str.split()[-1] if dep_airport_str.split() else "UNK"
                        airport_name = dep_airport_str.split("(")[0].strip()
                        dep_airport = {
                            "name": airport_name,
                            "id": airport_id,
                            "time": details.get("departure_time", "")
                        }
                    elif isinstance(dep_airport_str, dict):
                        dep_airport = dep_airport_str
                    else:
                        dep_airport = {"name": "Unknown", "id": "UNK", "time": details.get("departure_time", "")}
                    
                    if isinstance(arr_airport_str, str):
                        # Parse "Dubai International Airport (DXB)" -> {name: "...", id: "DXB"}
                        import re
                        match = re.search(r'\(([A-Z]{3})\)', arr_airport_str)
                        airport_id = match.group(1) if match else arr_airport_str.split()[-1] if arr_airport_str.split() else "UNK"
                        airport_name = arr_airport_str.split("(")[0].strip()
                        arr_airport = {
                            "name": airport_name,
                            "id": airport_id,
                            "time": details.get("arrival_time", "")
                        }
                    elif isinstance(arr_airport_str, dict):
                        arr_airport = arr_airport_str
                    else:
                        arr_airport = {"name": "Unknown", "id": "UNK", "time": details.get("arrival_time", "")}
                    
                    # Build flight segment with proper structure
                    flight_data = {
                        "airline": details.get("airline", "Unknown"),
                        "flight_number": details.get("flight_number", ""),
                        "departure_airport": dep_airport,
                        "arrival_airport": arr_airport,
                        "duration": details.get("duration", ""),
                        "travel_class": details.get("travel_class", "Economy"),
                        "airplane": details.get("airplane", ""),
                        "legroom": details.get("legroom", "")
                    }
                    
                    # Create proper structure: details.flights = [flight_data], details.price at top level
                    args["details"] = {
                        "flights": [flight_data],
                        "price": details.get("price"),
                        "total_duration": details.get("duration") or details.get("total_duration"),
                        "type": details.get("type", "One way"),
                        "google_flights_url": details.get("google_flights_url"),
                        "book_with": details.get("book_with"),
                        "booking_price": details.get("booking_price")
                    }
                    print(f"[FINAL PLANNER] Fixed flight data structure: converted string airports to objects")
                else:
                    # Flights array exists, but check if airports are strings inside segments
                    flights = details.get("flights", [])
                    fixed = False
                    for flight_segment in flights:
                        if isinstance(flight_segment.get("departure_airport"), str):
                            dep_str = flight_segment["departure_airport"]
                            import re
                            match = re.search(r'\(([A-Z]{3})\)', dep_str)
                            airport_id = match.group(1) if match else "UNK"
                            airport_name = dep_str.split("(")[0].strip()
                            flight_segment["departure_airport"] = {
                                "name": airport_name,
                                "id": airport_id,
                                "time": flight_segment.get("departure_time", "")
                            }
                            fixed = True
                        if isinstance(flight_segment.get("arrival_airport"), str):
                            arr_str = flight_segment["arrival_airport"]
                            import re
                            match = re.search(r'\(([A-Z]{3})\)', arr_str)
                            airport_id = match.group(1) if match else "UNK"
                            airport_name = arr_str.split("(")[0].strip()
                            flight_segment["arrival_airport"] = {
                                "name": airport_name,
                                "id": airport_id,
                                "time": flight_segment.get("arrival_time", "")
                            }
                            fixed = True
                    if fixed:
                        print(f"[FINAL PLANNER] Fixed flight segments: converted string airports to objects")
                    # Ensure price is at top level
                    if "price" not in details and details.get("flights"):
                        # Try to extract from first flight if available
                        first_flight = details["flights"][0] if details["flights"] else {}
                        if "price" in first_flight:
                            details["price"] = first_flight["price"]
                            print(f"[FINAL PLANNER] Moved price to top level")

            try:
                result = await PlannerAgentClient.invoke(tool_name, **args)
                print(f"[FINAL PLANNER] Tool {tool_name} result: {result}")
            except Exception as e:
                print(f"[FINAL PLANNER] ERROR invoking {tool_name}: {e}")

    except Exception as e:
        print(f"[FINAL PLANNER] ERROR in LLM planner call: {e}")

    # Always end after running final planner
    return updated_state



