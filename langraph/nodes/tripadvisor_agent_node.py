"""TripAdvisor Agent node for LangGraph orchestration."""

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
from clients.tripadvisor_agent_client import TripAdvisorAgentClient

# Load environment variables from .env file in main directory
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _load_tool_docs() -> dict:
    """Load tool documentation from JSON file."""
    docs_path = project_root / "mcp_system" / "tool_docs" / "tripadvisor_docs.json"
    try:
        with open(docs_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load tripadvisor tool docs: {e}")
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
            for i, example in enumerate(tool_info['examples'][:1], 1):  # Show first example only (many tools)
                formatted += f"  Example {i}: {example.get('title', 'N/A')}\n"
                formatted += f"    {json.dumps(example.get('body', {}), indent=4)}\n"
            formatted += "\n"
        
        formatted += "---\n\n"
    
    return formatted


def get_tripadvisor_agent_prompt() -> str:
    """Get the system prompt for the TripAdvisor Agent."""
    docs = _load_tool_docs()
    docs_text = _format_tool_docs(docs)
    
    base_prompt = """You are the TripAdvisor Agent, a specialized agent that helps users find attractions, restaurants, and reviews.

CRITICAL: You MUST use the available tools to search for locations/attractions. DO NOT respond without calling a tool.

Your role:
- Focus EXCLUSIVELY on RESTAURANTS, ATTRACTIONS, and ACTIVITIES - NEVER hotels
- Hotels are 100% handled by a separate agent - YOU MUST COMPLETELY IGNORE ANY hotel mentions
- Understand the user's message using your LLM reasoning capabilities
- Extract ONLY the restaurant/attraction/activity parts of the query
- Use your understanding to determine what search parameters are needed
- Use the appropriate TripAdvisor tool with parameters you determine from the user's message
- The tool schemas will show you exactly what parameters are needed

CRITICAL - STRICT DOMAIN RULES:
- If query mentions "restaurants" → search ONLY for restaurants (category: "restaurants")
- If query mentions "attractions" or "things to do" → search for attractions
- If query mentions "hotels" + "restaurants" → IGNORE hotels completely, search ONLY restaurants
- NEVER use "hotels" as search_query or category - this is FORBIDDEN
- Your search_query should be like "restaurants in [city]" NOT "hotels in [city]"
- Example: User says "hotels and restaurants in Beirut" → You search: "restaurants in Beirut" with category "restaurants"

Available tools (you will see their full schemas with function calling):
- search_locations: Search for locations/attractions (general search)
- get_location_reviews: Get reviews for a location
- get_location_photos: Get photos for a location
- get_location_details: Get detailed information about a location
- search_nearby: Search for nearby locations
- search_locations_by_rating: Search locations filtered by minimum rating
- search_nearby_by_rating: Search nearby locations filtered by minimum rating
- get_top_rated_locations: Get top k highest-rated locations
- search_locations_by_price: Search locations filtered by maximum price level
- search_nearby_by_price: Search nearby locations filtered by maximum price level
- search_nearby_by_distance: Search nearby locations sorted by distance
- find_closest_location: Find the single closest location
- search_restaurants_by_cuisine: Search restaurants filtered by cuisine type
- get_multiple_location_details: Get details for multiple locations
- compare_locations: Compare 2-3 locations side by side

IMPORTANT:
- Use your LLM understanding to determine parameters from the user's message - NO code-based parsing is used
- Choose the most appropriate tool based on your understanding of the user's query
- Use the tool schemas to understand required vs optional parameters
- ALWAYS call a tool - do not ask for clarification unless absolutely critical information is missing
- You have access to the full tool documentation through function calling - use it to understand parameter requirements

You have access to the full tool documentation through function calling. Use your LLM reasoning to understand the user's message and call the appropriate tool with the correct parameters."""
    
    return base_prompt + docs_text


async def tripadvisor_agent_node(state: AgentState) -> AgentState:
    """TripAdvisor Agent node that handles location and review queries.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with response
    """
    user_message = state.get("user_message", "")
    
    # Always use LLM to extract parameters from user message
    # LLM has access to tool documentation and can intelligently extract parameters
    # Get tools available to tripadvisor agent
    tools = await TripAdvisorAgentClient.list_tools()
    
    # Use the standard prompt - LLM will extract parameters from user message
    prompt = get_tripadvisor_agent_prompt()
    
    # Prepare messages for LLM
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_message}
    ]
    
    # Build function calling schema for tripadvisor tools
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
        input_schema = tool.get("inputSchema", {})
        input_schema = _sanitize_schema(input_schema)
        functions.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", f"TripAdvisor tool: {tool['name']}"),
                "parameters": input_schema
            }
        })
    
    # Call LLM with function calling - require tool use when functions are available
    if functions:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=functions,
            tool_choice="required"  # Force tool call when tools are available
        )
    else:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )
    
    message = response.choices[0].message
    updated_state = state.copy()
    
    # Check if LLM wants to call a tool
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        tool_name = tool_call.function.name
        
        import json
        args = json.loads(tool_call.function.arguments)
        
        # Debug: Log what the LLM chose
        print(f"🔍 TRIPADVISOR DEBUG - Tool: {tool_name}, Args: {args}")
        
        # Validate that we're not searching for hotels
        if "search_query" in args and "hotel" in args.get("search_query", "").lower():
            print(f"⚠️ WARNING: TripAdvisor trying to search for hotels! Overriding to restaurants.")
            # Override to search for restaurants instead
            args["search_query"] = args["search_query"].replace("hotels", "restaurants").replace("hotel", "restaurant")
            args["category"] = "restaurants"
            print(f"✅ Corrected args: {args}")
        
        # LLM has extracted all parameters from user message - use them directly
        # Call the tripadvisor tool via MCP
        try:
            tripadvisor_result = await TripAdvisorAgentClient.invoke(tool_name, **args)
            
            # Format the response
            if tripadvisor_result.get("error"):
                response_text = f"I encountered an error while searching TripAdvisor: {tripadvisor_result.get('error_message', 'Unknown error')}"
                if tripadvisor_result.get("suggestion"):
                    response_text += f"\n\nSuggestion: {tripadvisor_result.get('suggestion')}"
            else:
                # Store the raw result directly in state for parallel execution
                updated_state["tripadvisor_result"] = tripadvisor_result
                # No need to set route - using add_edge means we automatically route to join_node
            
        except Exception as e:
            # Store error in result
            updated_state["tripadvisor_result"] = {"error": True, "error_message": str(e)}
            # No need to set route - using add_edge means we automatically route to join_node
        
        return updated_state
    
    # No tool call - store empty result
    updated_state["tripadvisor_result"] = {"error": True, "error_message": "No TripAdvisor search parameters provided"}
    # No need to set route - using add_edge means we automatically route to join_node
    
    return updated_state

