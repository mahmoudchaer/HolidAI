"""TripAdvisor Agent node for LangGraph orchestration."""

import sys
import os
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


def get_tripadvisor_agent_prompt() -> str:
    """Get the system prompt for the TripAdvisor Agent."""
    return """You are the TripAdvisor Agent, a specialized agent that helps users find attractions, restaurants, and reviews.

Your role:
- Understand user queries about attractions, restaurants, reviews, and location information
- Extract search parameters from user messages or context
- Use the appropriate TripAdvisor tool
- Provide clear, helpful responses about locations and reviews

Available tools:
- search_locations: Search for locations/attractions
- get_location_reviews: Get reviews for a location
- get_location_photos: Get photos for a location
- get_location_details: Get detailed information about a location
- search_nearby: Search for nearby locations
- search_locations_by_rating: Search locations by rating
- search_nearby_by_rating: Search nearby locations by rating
- get_top_rated_locations: Get top rated locations
- search_locations_by_price: Search locations by price range
- search_nearby_by_price: Search nearby locations by price
- search_nearby_by_distance: Search nearby locations by distance
- find_closest_location: Find closest location
- search_restaurants_by_cuisine: Search restaurants by cuisine type
- get_multiple_location_details: Get details for multiple locations
- compare_locations: Compare multiple locations

When a user asks about attractions, restaurants, or reviews, extract the parameters from their message or use the provided context, and use the appropriate tool.
If any information is missing, ask the user for clarification.

Provide friendly, clear responses about locations and reviews based on the tool results."""


async def tripadvisor_agent_node(state: AgentState) -> AgentState:
    """TripAdvisor Agent node that handles location and review queries.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with response
    """
    user_message = state.get("user_message", "")
    context = state.get("context", {})
    
    # Check if we have task context from delegation
    task_args = context.get("args", {})
    
    # Get tools available to tripadvisor agent
    tools = await TripAdvisorAgentClient.list_tools()
    
    # Prepare messages for LLM
    messages = [
        {"role": "system", "content": get_tripadvisor_agent_prompt()},
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
    updated_state = state.copy()
    
    # Check if LLM wants to call a tool
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        tool_name = tool_call.function.name
        
        import json
        args = json.loads(tool_call.function.arguments)
        
        # Merge task_args if available
        if task_args:
            args = {**args, **task_args}
        
        # Call the tripadvisor tool via MCP
        try:
            tripadvisor_result = await TripAdvisorAgentClient.invoke(tool_name, **args)
            
            # Format the response
            if tripadvisor_result.get("error"):
                response_text = f"I encountered an error while searching TripAdvisor: {tripadvisor_result.get('error_message', 'Unknown error')}"
                if tripadvisor_result.get("suggestion"):
                    response_text += f"\n\nSuggestion: {tripadvisor_result.get('suggestion')}"
            else:
                # Store the raw result in context for orchestrator
                response_text = f"TripAdvisor search completed. Found location information."
                if "context" not in updated_state:
                    updated_state["context"] = {}
                updated_state["context"]["tripadvisor_result"] = tripadvisor_result
            
            updated_state["last_response"] = response_text
            updated_state["route"] = "main_agent"  # Return to main agent
            
        except Exception as e:
            updated_state["last_response"] = f"I encountered an error while searching TripAdvisor: {str(e)}"
            updated_state["route"] = "main_agent"
        
        return updated_state
    
    # No tool call - respond directly
    assistant_message = message.content or "I can help you find attractions, restaurants, and reviews. Please provide a location or search criteria."
    updated_state["route"] = "main_agent"
    updated_state["last_response"] = assistant_message
    
    return updated_state

