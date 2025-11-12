"""Hotel Agent node for LangGraph orchestration."""

import sys
import os
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


def get_hotel_agent_prompt() -> str:
    """Get the system prompt for the Hotel Agent."""
    return """You are the Hotel Agent, a specialized agent that helps users search for hotels.

Your role:
- Understand user queries about hotel searches
- Extract hotel search parameters from user messages or context
- Use the appropriate hotel search tool
- Provide clear, helpful responses about hotel options

Available tools:
- get_hotel_rates: Search for hotel rates
- get_hotel_rates_by_price: Search for hotels by price range
- get_hotel_details: Get detailed information about specific hotels

When a user asks about hotels, extract the parameters from their message or use the provided context, and use the appropriate tool.
If any information is missing, ask the user for clarification.

Provide friendly, clear responses about hotel options based on the tool results."""


async def hotel_agent_node(state: AgentState) -> AgentState:
    """Hotel Agent node that handles hotel search queries.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with response
    """
    user_message = state.get("user_message", "")
    context = state.get("context", {})
    
    # Check if we have task context from delegation
    task_name = context.get("task", "")
    task_args = context.get("args", {})
    
    updated_state = state.copy()
    
    # If we have delegated task args, use them directly
    if task_args and task_name:
        # Map task names to tool names
        task_to_tool = {
            "get_hotel_rates": "get_hotel_rates",
            "get_hotel_rates_by_price": "get_hotel_rates_by_price",
            "get_hotel_details": "get_hotel_details"
        }
        
        tool_name = task_to_tool.get(task_name)
        
        if tool_name and tool_name != "get_hotel_details":
            try:
                # Make a copy of task_args to avoid modifying the original
                tool_args = task_args.copy()
                
                # Extract filter parameters (don't pass them to the tool)
                max_price = tool_args.pop("max_price", None) or tool_args.pop("budget", None)
                min_stars = tool_args.pop("min_stars", None) or tool_args.pop("star_rating", None) or tool_args.pop("stars", None)
                
                # Call the hotel tool without filter parameters
                hotel_result = await HotelAgentClient.invoke(
                    tool_name,
                    **tool_args
                )
                
                # Format the response
                if hotel_result.get("error"):
                    response_text = f"I encountered an error while searching for hotels: {hotel_result.get('error_message', 'Unknown error')}"
                    if hotel_result.get("suggestion"):
                        response_text += f"\n\nSuggestion: {hotel_result.get('suggestion')}"
                else:
                    # Fetch hotel details for top hotels and apply filters
                    hotels = hotel_result.get("hotels", [])
                    if hotels:
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
                        MAX_DETAILS_TO_FETCH = 10
                        enriched_hotels = []
                        
                        for hotel in hotels[:MAX_DETAILS_TO_FETCH]:
                            hotel_id = hotel.get("hotelId")
                            if not hotel_id:
                                continue
                            
                            try:
                                # Fetch hotel details
                                details_result = await HotelAgentClient.invoke(
                                    "get_hotel_details",
                                    hotel_id=hotel_id
                                )
                                
                                if not details_result.get("error") and details_result.get("hotel"):
                                    hotel_details = details_result.get("hotel")
                                    # Merge details with rate info
                                    hotel["name"] = hotel_details.get("name") or hotel_details.get("hotelName")
                                    hotel["address"] = hotel_details.get("address") or hotel_details.get("location")
                                    hotel["rating"] = hotel_details.get("rating") or hotel_details.get("starRating") or hotel_details.get("stars")
                                    hotel["description"] = hotel_details.get("description")
                                
                            except Exception as e:
                                # If details fetch fails, continue with rate info only
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
                        hotel_result["hotels"] = enriched_hotels
                        hotel_result["_filtered"] = len(hotels) - len(enriched_hotels)
                    
                    # Store the raw result in context for orchestrator
                    response_text = f"Hotel search completed. Found hotel information."
                    if "context" not in updated_state:
                        updated_state["context"] = {}
                    updated_state["context"]["hotel_result"] = hotel_result
                
                updated_state["last_response"] = response_text
                updated_state["route"] = "main_agent"  # Return to main agent
                
                return updated_state
            except Exception as e:
                updated_state["last_response"] = f"I encountered an error while searching for hotels: {str(e)}"
                updated_state["route"] = "main_agent"
                return updated_state
    
    # Fall back to LLM-based extraction if no delegated args
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
                    "description": tool.get("description", f"Search for hotels"),
                    "parameters": input_schema
                }
            })
    
    # Call LLM with function calling
    if functions:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            tools=functions,
            tool_choice="auto"
        )
    else:
        response = client.chat.completions.create(
            model="gpt-4",
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
            
            # Merge task_args if available
            if task_args:
                args = {**args, **task_args}
            
            # Call the hotel tool via MCP
            try:
                # Make a copy of args to avoid modifying the original
                tool_args = args.copy()
                
                # Extract filter parameters (don't pass them to the tool)
                max_price = tool_args.pop("max_price", None) or tool_args.pop("budget", None)
                min_stars = tool_args.pop("min_stars", None) or tool_args.pop("star_rating", None) or tool_args.pop("stars", None)
                
                # Call the hotel tool without filter parameters
                hotel_result = await HotelAgentClient.invoke(tool_name, **tool_args)
                
                # Format the response
                if hotel_result.get("error"):
                    response_text = f"I encountered an error while searching for hotels: {hotel_result.get('error_message', 'Unknown error')}"
                    if hotel_result.get("suggestion"):
                        response_text += f"\n\nSuggestion: {hotel_result.get('suggestion')}"
                else:
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
                        MAX_DETAILS_TO_FETCH = 10
                        enriched_hotels = []
                        
                        for hotel in hotels[:MAX_DETAILS_TO_FETCH]:
                            hotel_id = hotel.get("hotelId")
                            if not hotel_id:
                                continue
                            
                            try:
                                # Fetch hotel details
                                details_result = await HotelAgentClient.invoke(
                                    "get_hotel_details",
                                    hotel_id=hotel_id
                                )
                                
                                if not details_result.get("error") and details_result.get("hotel"):
                                    hotel_details = details_result.get("hotel")
                                    # Merge details with rate info
                                    hotel["name"] = hotel_details.get("name") or hotel_details.get("hotelName")
                                    hotel["address"] = hotel_details.get("address") or hotel_details.get("location")
                                    hotel["rating"] = hotel_details.get("rating") or hotel_details.get("starRating") or hotel_details.get("stars")
                                    hotel["description"] = hotel_details.get("description")
                                
                            except Exception as e:
                                # If details fetch fails, continue with rate info only
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
                        hotel_result["hotels"] = enriched_hotels
                        hotel_result["_filtered"] = len(hotels) - len(enriched_hotels)
                    
                    # Store the raw result in context for orchestrator
                    response_text = f"Hotel search completed. Found hotel information."
                    if "context" not in updated_state:
                        updated_state["context"] = {}
                    updated_state["context"]["hotel_result"] = hotel_result
                
                updated_state["last_response"] = response_text
                updated_state["route"] = "main_agent"  # Return to main agent
                
            except Exception as e:
                updated_state["last_response"] = f"I encountered an error while searching for hotels: {str(e)}"
                updated_state["route"] = "main_agent"
            
            return updated_state
    
    # No tool call - respond directly
    assistant_message = message.content or "I can help you search for hotels. Please provide check-in/check-out dates, location, and occupancy details."
    updated_state["route"] = "main_agent"
    updated_state["last_response"] = assistant_message
    
    return updated_state

