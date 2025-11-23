"""Flight Agent node for LangGraph orchestration."""

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
from clients.flight_agent_client import FlightAgentClient
# Import memory_filter from the same directory
import sys
import os
_nodes_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _nodes_dir)
from memory_filter import filter_memories_for_agent

# Load environment variables from .env file in main directory
# Get the project root directory (2 levels up from langraph/nodes/)
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _load_tool_docs() -> dict:
    """Load tool documentation from JSON file."""
    docs_path = project_root / "mcp_system" / "tool_docs" / "flight_docs.json"
    try:
        with open(docs_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load flight tool docs: {e}")
        return {}


def _format_tool_docs(docs: dict) -> str:
    """Format tool documentation for inclusion in prompt."""
    if not docs:
        return ""
    
    formatted = "\n\n=== TOOL DOCUMENTATION ===\n\n"
    
    for tool_name, tool_info in docs.items():
        # Map tool names to actual tool names used in the system
        actual_tool_name = tool_name.replace("agent_get_flights", "agent_get_flights_tool").replace("agent_get_flights_flexible", "agent_get_flights_flexible_tool")
        
        formatted += f"Tool: {actual_tool_name}\n"
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


def get_flight_agent_prompt(memories: list = None) -> str:
    """Get the system prompt for the Flight Agent."""
    docs = _load_tool_docs()
    docs_text = _format_tool_docs(docs)
    
    memory_section = ""
    if memories and len(memories) > 0:
        memory_section = "\n\n⚠️ CRITICAL - USER PREFERENCES (MUST USE WHEN CALLING TOOLS):\n" + "\n".join([f"- {mem}" for mem in memories]) + "\n\nWhen calling flight search tools, you MUST:\n- If user prefers morning flights: Filter or prioritize flights with departure times in the morning (before 12:00 PM)\n- If user prefers specific airlines: Include airline preferences in search parameters\n- If user has budget constraints: Apply price filters in tool calls\n- If user prefers direct flights: Filter out flights with layovers/stopovers\n- ALWAYS apply these preferences to your tool call parameters - do NOT just mention them in the response\n- These preferences are about THIS USER - they override generic defaults\n- Example: If memory says 'User prefers morning flights', your tool call should prioritize/filter for morning departure times\n"
    
    base_prompt = """You are the Flight Agent, a specialized agent that helps users search for flights.

CRITICAL: You MUST use the available tools to search for flights. Do NOT respond without calling a tool.

Your role:
- Understand the user's message using your LLM reasoning capabilities
- Use your understanding to determine what flight search parameters are needed
- Use the appropriate flight search tool with parameters you determine from the user's message
- The tool schemas will show you exactly what parameters are needed

Available tools (you will see their full schemas with function calling):
- agent_get_flights_tool: Search for flights with specific dates
- agent_get_flights_flexible_tool: Search for flights with flexible dates

IMPORTANT:
- Use your LLM understanding to determine parameters from the user's message - NO code-based parsing is used
- Convert dates to YYYY-MM-DD format based on your understanding
- Use your knowledge to convert city names to airport codes when possible (e.g., "Dubai" -> "DXB", "Beirut" -> "BEY")
- Infer trip_type from context using your understanding (one-way vs round-trip)
- Use the tool schemas to understand required vs optional parameters
- ALWAYS call a tool - do not ask for clarification unless absolutely critical information is missing
- You have access to the full tool documentation through function calling - use it to understand parameter requirements

⚠️ CRITICAL - days_flex LIMITATION:
- The days_flex parameter in agent_get_flights_flexible_tool is LIMITED to 0-7 (maximum 7 days)
- If user asks for "during the month" or "in December", you MUST:
  1. Pick a date in the middle of the month (e.g., December 15 for December, or the 15th of any month)
  2. Set days_flex to 7 (the maximum allowed) to cover as much of the month as possible
  3. DO NOT set days_flex to 10, 15, 20, or any value greater than 7 - it will cause an error
- Example: User says "flights in December 2025" → Use departure_date="2025-12-15" with days_flex=7
- Example: User says "flights during January" → Use departure_date="2025-01-15" with days_flex=7
- If user provides a specific date, use that date with an appropriate days_flex (0-7) based on their flexibility

You have access to the full tool documentation through function calling. Use your LLM reasoning to understand the user's message and call the appropriate tool with the correct parameters."""
    
    return base_prompt + memory_section + docs_text


async def flight_agent_node(state: AgentState) -> AgentState:
    """Flight Agent node that handles flight search queries.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with response
    """
    from datetime import datetime
    start_time = datetime.now()
    print(f"[{start_time.strftime('%H:%M:%S.%f')[:-3]}] 🛫 FLIGHT AGENT STARTED")
    
    user_message = state.get("user_message", "")
    all_memories = state.get("relevant_memories", [])
    
    # Filter memories to only include flight-related ones
    relevant_memories = filter_memories_for_agent(all_memories, "flight")
    if all_memories and not relevant_memories:
        print(f"[MEMORY] Flight agent: {len(all_memories)} total memories, 0 flight-related (filtered out non-flight memories)")
    elif relevant_memories:
        print(f"[MEMORY] Flight agent: {len(all_memories)} total memories, {len(relevant_memories)} flight-related")
    
    # Get current step context from execution plan
    execution_plan = state.get("execution_plan", [])
    current_step_index = state.get("current_step", 1) - 1  # current_step is 1-indexed
    
    # If we have an execution plan, use the step description as context
    step_context = ""
    if execution_plan and 0 <= current_step_index < len(execution_plan):
        current_step = execution_plan[current_step_index]
        step_context = current_step.get("description", "")
        print(f"🔍 FLIGHT DEBUG - Step context: {step_context}")
    
    # Build the message to send to LLM
    if step_context:
        # Use step description as primary instruction, with user message as background
        agent_message = f"""Current task: {step_context}

Background context from user: {user_message}

Focus on the flight search task described above."""
    else:
        # Fallback to user message if no step context
        agent_message = user_message
    
    # Always use LLM to extract parameters from user message
    # LLM has access to tool documentation and can intelligently extract parameters
    # Get tools available to flight agent
    tools = await FlightAgentClient.list_tools()
    
    # Prepare messages for LLM
    prompt = get_flight_agent_prompt(memories=relevant_memories)
    
    # Enhance user message with flight-related memories if available
    if relevant_memories:
        print(f"[MEMORY] Flight agent using {len(relevant_memories)} flight-related memories: {relevant_memories}")
        # Add memories to user message to ensure they're considered in tool calls
        memory_context = "\n\nIMPORTANT USER PREFERENCES (MUST APPLY TO TOOL CALLS):\n" + "\n".join([f"- {mem}" for mem in relevant_memories])
        agent_message = agent_message + memory_context
    
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": agent_message}
    ]
    
    # Build function calling schema for flight tools
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
        if tool["name"] in ["agent_get_flights_tool", "agent_get_flights_flexible_tool"]:
            input_schema = tool.get("inputSchema", {})
            input_schema = _sanitize_schema(input_schema)
            functions.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", f"Search for flights"),
                    "parameters": input_schema
                }
            })
    
    # Call LLM with function calling - require tool use when functions are available
    if functions:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            tools=functions,
            tool_choice="required"  # Force tool call when tools are available
        )
    else:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages
        )
    
    message = response.choices[0].message
    updated_state = state.copy()
    
    # Check if LLM wants to call a tool
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        tool_name = tool_call.function.name
        
        if tool_name in ["agent_get_flights_tool", "agent_get_flights_flexible_tool"]:
            import json
            args = json.loads(tool_call.function.arguments)
            
            # Validate and cap days_flex at 7 (tool limitation)
            # IMPORTANT: agent_get_flights_tool (non-flexible) does NOT accept days_flex parameter
            if tool_name == "agent_get_flights_tool" and "days_flex" in args:
                print(f"[FLIGHT AGENT] WARNING: Removing days_flex parameter from agent_get_flights_tool (not supported)")
                args.pop("days_flex", None)
            elif tool_name == "agent_get_flights_flexible_tool" and "days_flex" in args and args["days_flex"] is not None:
                try:
                    days_flex_value = int(args["days_flex"])
                    if days_flex_value > 7:
                        print(f"[FLIGHT AGENT] WARNING: days_flex={days_flex_value} exceeds maximum of 7, capping to 7")
                        args["days_flex"] = 7
                    elif days_flex_value < 0:
                        print(f"[FLIGHT AGENT] WARNING: days_flex={days_flex_value} is negative, setting to 0")
                        args["days_flex"] = 0
                except (ValueError, TypeError):
                    print(f"[FLIGHT AGENT] WARNING: Invalid days_flex value '{args['days_flex']}', using default 3")
                    args["days_flex"] = 3
            
            # Debug: Log all args
            print(f"[FLIGHT AGENT] Tool call args: {json.dumps(args, indent=2)}")
            
            # Check if this is a round-trip request
            trip_type = args.get("trip_type", "").lower() if args.get("trip_type") else ""
            
            # Also check user message for round-trip keywords if trip_type is not clear
            if not trip_type or trip_type not in ["round-trip", "roundtrip", "round trip"]:
                user_msg_lower = user_message.lower()
                if any(keyword in user_msg_lower for keyword in ["round-trip", "roundtrip", "round trip", "return flight", "return ticket"]):
                    if args.get("arrival_date") or args.get("arr_date"):
                        trip_type = "round-trip"
                        args["trip_type"] = "round-trip"
                        print(f"[FLIGHT AGENT] Inferred round-trip from user message and arrival_date")
            
            is_round_trip = trip_type in ["round-trip", "roundtrip", "round trip"]
            print(f"[FLIGHT AGENT] trip_type='{trip_type}', is_round_trip={is_round_trip}")
            
            # Call the flight tool via MCP
            try:
                if is_round_trip:
                    # For round-trip, make TWO independent one-way calls
                    print(f"[FLIGHT AGENT] Round-trip detected - making 2 independent one-way calls")
                    
                    # Extract dates - check both parameter name variations
                    departure_date = args.get("departure_date", "") or args.get("dep_date", "")
                    arrival_date = args.get("arrival_date", "") or args.get("arr_date", "")
                    departure = args.get("departure", "") or args.get("dep", "")
                    arrival = args.get("arrival", "") or args.get("arr", "")
                    
                    print(f"[FLIGHT AGENT] Extracted: dep={departure}, arr={arrival}, dep_date={departure_date}, arr_date={arrival_date}")
                    
                    # Make first call: Outbound (departure → arrival)
                    print(f"[FLIGHT AGENT] Call 1: Outbound {departure} → {arrival} on {departure_date}")
                    outbound_args = args.copy()
                    outbound_args["trip_type"] = "one-way"
                    outbound_args.pop("arrival_date", None)  # Remove arrival_date for one-way
                    outbound_args.pop("arr_date", None)
                    outbound_result = await FlightAgentClient.invoke(tool_name, **outbound_args)
                    
                    # Make second call: Return (arrival → departure)
                    # For flexible flights, calculate return date from outbound results + trip duration
                    if arrival and departure:
                        # Calculate return date: if we have days_flex or trip duration, use that
                        # Otherwise use provided arrival_date
                        return_date = arrival_date
                        days_flex = args.get("days_flex") or args.get("trip_duration") or args.get("duration")
                        
                        # If using flexible tool and we got outbound results, calculate return date from first outbound flight
                        if tool_name == "agent_get_flights_flexible_tool" and not outbound_result.get("error"):
                            outbound_flights_temp = outbound_result.get("outbound", []) or outbound_result.get("flights", [])
                            if outbound_flights_temp and len(outbound_flights_temp) > 0:
                                # Get the search_date from first flight (flexible tool returns this)
                                first_flight = outbound_flights_temp[0]
                                outbound_search_date = first_flight.get("search_date") or first_flight.get("flights", [{}])[0].get("departure_airport", {}).get("time", "")
                                
                                if outbound_search_date and days_flex:
                                    # Parse date and add days
                                    from datetime import datetime, timedelta
                                    try:
                                        if isinstance(outbound_search_date, str):
                                            # Extract date part (YYYY-MM-DD)
                                            date_str = outbound_search_date.split()[0] if " " in outbound_search_date else outbound_search_date
                                            outbound_dt = datetime.strptime(date_str, "%Y-%m-%d")
                                            return_dt = outbound_dt + timedelta(days=int(days_flex))
                                            return_date = return_dt.strftime("%Y-%m-%d")
                                            print(f"[FLIGHT AGENT] Calculated return date: {outbound_search_date} + {days_flex} days = {return_date}")
                                    except Exception as e:
                                        print(f"[FLIGHT AGENT] Could not calculate return date from outbound: {e}, using provided arrival_date={arrival_date}")
                                        return_date = arrival_date
                        
                        if return_date:
                            print(f"[FLIGHT AGENT] Call 2: Return {arrival} → {departure} on {return_date}")
                            return_args = args.copy()
                            return_args["trip_type"] = "one-way"
                            return_args["departure"] = arrival  # Reverse: destination becomes origin
                            return_args["arrival"] = departure  # Reverse: origin becomes destination
                            return_args["departure_date"] = return_date  # Use calculated return date
                            
                            # Preserve flexible parameters for return flight if using flexible tool
                            if tool_name == "agent_get_flights_flexible_tool":
                                # Keep flexible parameters but adjust for return
                                if "days_flex" in return_args:
                                    # For return, we want flights around the calculated return date
                                    return_args["days_flex"] = min(return_args.get("days_flex", 3), 3)  # Limit to 3 days for return
                                # Keep time preferences if present
                                # dep_after and dep_before can stay the same
                            else:
                                # Remove flexible parameters for non-flexible tool
                                return_args.pop("days_flex", None)
                                return_args.pop("trip_duration", None)
                                return_args.pop("duration", None)
                                return_args.pop("dep_after", None)
                                return_args.pop("dep_before", None)
                            
                            # Remove all date-related fields that aren't needed
                            return_args.pop("arrival_date", None)
                            return_args.pop("arr_date", None)
                            # Also handle dep/dep_date aliases
                            if "dep" in return_args:
                                return_args["dep"] = arrival
                            if "arr" in return_args:
                                return_args["arr"] = departure
                            if "dep_date" in return_args:
                                return_args["dep_date"] = return_date
                            print(f"[FLIGHT AGENT] Return call args: {json.dumps(return_args, indent=2)}")
                            return_result = await FlightAgentClient.invoke(tool_name, **return_args)
                            print(f"[FLIGHT AGENT] Return call result: error={return_result.get('error')}, flights={len(return_result.get('outbound', []) or return_result.get('flights', []))}")
                        else:
                            print(f"[FLIGHT AGENT] ERROR: No return date available - arrival_date={arrival_date}, days_flex={days_flex}")
                            return_result = {"error": True, "error_message": f"No return date provided. arrival_date={arrival_date}, days_flex={days_flex}"}
                    else:
                        print(f"[FLIGHT AGENT] ERROR: Missing data for return flight - arrival={arrival}, departure={departure}")
                        return_result = {"error": True, "error_message": f"Missing origin/destination for return flight. arrival={arrival}, departure={departure}"}
                    
                    # Combine results - handle both flexible and regular tool response formats
                    if not outbound_result.get("error"):
                        outbound_flights = outbound_result.get("outbound", []) or outbound_result.get("flights", [])
                    else:
                        outbound_flights = []
                    
                    if not return_result.get("error"):
                        return_flights = return_result.get("outbound", []) or return_result.get("flights", [])
                    else:
                        return_flights = []
                    
                    # Log detailed results
                    print(f"[FLIGHT AGENT] Outbound result: error={outbound_result.get('error')}, flights={len(outbound_flights)}")
                    print(f"[FLIGHT AGENT] Return result: error={return_result.get('error')}, error_msg={return_result.get('error_message')}, flights={len(return_flights)}")
                    
                    flight_result = {
                        "error": False,
                        "outbound": outbound_flights,
                        "return": return_flights,
                        "trip_type": "round-trip"
                    }
                    
                    # Mark flights with direction
                    for flight in flight_result["outbound"]:
                        flight["type"] = "Outbound flight"
                        flight["direction"] = "outbound"
                    for flight in flight_result["return"]:
                        flight["type"] = "Return flight"
                        flight["direction"] = "return"
                    
                    print(f"[FLIGHT AGENT] Combined results: {len(flight_result['outbound'])} outbound, {len(flight_result['return'])} return")
                    
                    # Warn if return flights are missing
                    if len(flight_result["return"]) == 0 and arrival_date:
                        print(f"[FLIGHT AGENT] ⚠️ WARNING: No return flights found despite having arrival_date={arrival_date}")
                        print(f"[FLIGHT AGENT] Return result details: {json.dumps(return_result, indent=2, default=str)}")
                else:
                    # Single one-way call
                    flight_result = await FlightAgentClient.invoke(tool_name, **args)
                    
                    # Transform flexible tool response format to standard format
                    # agent_get_flights_flexible_tool returns {"flights": [...]} but we need {"outbound": [...]}
                    if not flight_result.get("error") and "flights" in flight_result and "outbound" not in flight_result:
                        flights = flight_result.get("flights", [])
                        flight_result["outbound"] = flights
                        # Remove the old "flights" key to avoid confusion
                        flight_result.pop("flights", None)
                        print(f"[FLIGHT AGENT] Transformed flexible tool result: {len(flights)} flights moved to 'outbound' array")
                
                # ===== INTELLIGENT SUMMARIZATION =====
                # Summarize flight results before passing to conversational agent
                if not flight_result.get("error"):
                    # Handle both old format (flights array) and new format (outbound/return arrays)
                    if "outbound" in flight_result or "return" in flight_result:
                        # New format: round-trip with separate outbound/return
                        outbound_flights = flight_result.get("outbound", [])
                        return_flights = flight_result.get("return", [])
                        if outbound_flights or return_flights:
                            try:
                                from utils.result_summarizer import summarize_flight_results
                                if outbound_flights:
                                    print(f"🧠 Flight agent: Summarizing {len(outbound_flights)} outbound flights...")
                                    summarized_outbound = await summarize_flight_results(
                                        outbound_flights,
                                        user_message,
                                        step_context
                                    )
                                    flight_result["outbound"] = summarized_outbound.get("flights", [])
                                    flight_result["outbound_original_count"] = len(outbound_flights)
                                    flight_result["outbound_summarized_count"] = len(summarized_outbound.get("flights", []))
                                    print(f"✅ Flight agent: Summarized outbound from {len(outbound_flights)} to {flight_result['outbound_summarized_count']} flights")
                                if return_flights:
                                    print(f"🧠 Flight agent: Summarizing {len(return_flights)} return flights...")
                                    summarized_return = await summarize_flight_results(
                                        return_flights,
                                        user_message,
                                        step_context
                                    )
                                    flight_result["return"] = summarized_return.get("flights", [])
                                    flight_result["return_original_count"] = len(return_flights)
                                    flight_result["return_summarized_count"] = len(summarized_return.get("flights", []))
                                    print(f"✅ Flight agent: Summarized return from {len(return_flights)} to {flight_result['return_summarized_count']} flights")
                            except Exception as e:
                                print(f"⚠️ Flight summarization failed, using original data: {e}")
                    else:
                        # Old format: single flights array - transform to outbound format
                        flights = flight_result.get("flights", [])
                        if flights and len(flights) > 0:
                            try:
                                from utils.result_summarizer import summarize_flight_results
                                print(f"🧠 Flight agent: Summarizing {len(flights)} flights for conversational agent...")
                                summarized = await summarize_flight_results(
                                    flights,
                                    user_message,
                                    step_context
                                )
                                # Transform to new format: move flights to outbound array
                                flight_result["outbound"] = summarized.get("flights", [])
                                flight_result["original_count"] = len(flights)
                                flight_result["summarized_count"] = len(summarized.get("flights", []))
                                flight_result["summary"] = summarized.get("summary", "")
                                # Remove old flights key
                                flight_result.pop("flights", None)
                                print(f"✅ Flight agent: Summarized from {len(flights)} to {flight_result['summarized_count']} flights and transformed to 'outbound' format")
                            except Exception as e:
                                print(f"⚠️ Flight summarization failed, using original data: {e}")
                                # Still transform format even if summarization fails
                                if "flights" in flight_result:
                                    flight_result["outbound"] = flight_result.pop("flights")
                                print(f"✅ Flight agent: Transformed {len(flight_result.get('outbound', []))} flights to 'outbound' format (summarization skipped)")
                
                # Store result directly in state for parallel execution
                updated_state["flight_result"] = flight_result
                # No need to set route - using add_edge means we automatically route to join_node
                
            except Exception as e:
                # Store error in result
                updated_state["flight_result"] = {"error": True, "error_message": str(e)}
                # No need to set route - using add_edge means we automatically route to join_node
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            print(f"[{end_time.strftime('%H:%M:%S.%f')[:-3]}] 🛫 FLIGHT AGENT COMPLETED (Duration: {duration:.3f}s)")
            return updated_state
    
    # No tool call - store empty result
    updated_state["flight_result"] = {"error": True, "error_message": "No flight search parameters provided"}
    # No need to set route - using add_edge means we automatically route to join_node
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"[{end_time.strftime('%H:%M:%S.%f')[:-3]}] 🛫 FLIGHT AGENT COMPLETED (Duration: {duration:.3f}s)")
    return updated_state

