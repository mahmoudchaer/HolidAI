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


def get_hotel_agent_prompt() -> str:
    """Get the system prompt for the Hotel Agent."""
    docs = _load_tool_docs()
    docs_text = _format_tool_docs(docs)
    
    base_prompt = """You are the Hotel Agent, a specialized agent that helps users search for hotels.

CRITICAL: You MUST use the available tools to search for hotels. Do NOT respond without calling a tool.

Your role:
- Understand the user's message using your LLM reasoning capabilities
- Use your understanding to determine what hotel search parameters are needed
- Use the appropriate hotel search tool with parameters you determine from the user's message
- The tool schemas will show you exactly what parameters are needed

Available tools (you will see their full schemas with function calling):
- get_hotel_rates: Search for hotel rates
- get_hotel_rates_by_price: Search for hotels by price range
- get_hotel_details: Get detailed information about specific hotels

IMPORTANT DATE HANDLING:
- If user specifies dates, use them exactly as provided
- If NO dates are mentioned, use these smart defaults:
  * checkin: 7 days from today (YYYY-MM-DD format)
  * checkout: 3 nights after checkin (typical short stay)
- Keep stays reasonable: 2-7 nights is typical unless user specifies longer
- NEVER use date ranges longer than 14 days unless explicitly requested
- Current date context: November 2024, so near-future dates should be in December 2024 or early 2025

LOCATION HANDLING:
- Determine location information - you MUST provide one of these combinations:
  * city_name AND country_code (BOTH required together) - e.g., "Beirut" requires country_code "LB" for Lebanon
  * OR iata_code (airport code)
  * OR hotel_ids (array of hotel IDs)
  * When a city name is mentioned, use your knowledge to infer the country code (e.g., "Beirut" -> "LB", "Dubai" -> "AE", "Paris" -> "FR", "Rome" -> "IT")

OTHER PARAMETERS:
- Infer occupancies from user message using your understanding (adults, children)
- Default to 2 adults if not specified
- Use the tool schemas to understand required vs optional parameters
- ALWAYS call a tool - do not ask for clarification unless absolutely critical information is missing
- You have access to the full tool documentation through function calling - use it to understand parameter requirements

You have access to the full tool documentation through function calling. Use your LLM reasoning to understand the user's message and call the appropriate tool with the correct parameters."""
    
    return base_prompt + docs_text


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
    updated_state = state.copy()
    
    # Always use LLM to extract parameters from user message
    # LLM has access to tool documentation and can intelligently extract parameters
    # Get tools available to hotel agent
    tools = await HotelAgentClient.list_tools()
    
    # Prepare messages for LLM
    messages = [
        {"role": "system", "content": get_hotel_agent_prompt()},
        {"role": "user", "content": user_message}
    ]
    
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

    for tool in tools:
        if tool["name"] in ["get_hotel_rates", "get_hotel_rates_by_price", "get_hotel_details"]:
            input_schema = tool.get("inputSchema", {})
            input_schema = _sanitize_schema(input_schema)
            functions.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", "Search for hotels"),
                    "parameters": input_schema
                }
            })
    
    # Call LLM with function calling - require tool use when functions are available
    if functions:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=functions,
            tool_choice="required"  # Force tool call when tools are available
        )
    else:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
    
    message = response.choices[0].message
    
    # Check if LLM wants to call a tool
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        tool_name = tool_call.function.name
        
        if tool_name in ["get_hotel_rates", "get_hotel_rates_by_price", "get_hotel_details"]:
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
                
                # Call the hotel tool without filter parameters
                hotel_result = await HotelAgentClient.invoke(tool_name, **tool_args)
                
                # Check if the tool call itself had an error
                if hotel_result.get("error"):
                    # Store error result and return
                    updated_state["hotel_result"] = hotel_result
                    # No need to set route - using add_edge means we automatically route to join_node
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    print(f"[{end_time.strftime('%H:%M:%S.%f')[:-3]}] 🏨 HOTEL AGENT COMPLETED (Duration: {duration:.3f}s)")
                    return updated_state
                
                # Ensure error flag is explicitly False if we have hotels
                if hotel_result.get("hotels") and len(hotel_result.get("hotels", [])) > 0:
                    hotel_result["error"] = False
                
                # Fetch hotel details for top hotels and apply filters (same logic as delegated path)
                hotels = hotel_result.get("hotels", [])
                if hotels and tool_name != "get_hotel_details":
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
                    except Exception as enrich_error:
                        # If enrichment fails completely, keep the original result
                        print(f"Warning: Hotel enrichment failed: {enrich_error}")
                        # Keep the original hotels result - it's better than nothing
                        hotel_result["hotels"] = hotels
                
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
                print(f"Error in hotel_agent_node: {e}")
                print(f"Traceback: {traceback.format_exc()}")
                # Store error in result
                updated_state["hotel_result"] = {"error": True, "error_message": str(e)}
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

