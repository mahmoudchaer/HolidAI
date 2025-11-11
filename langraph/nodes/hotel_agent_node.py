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
    task_args = context.get("args", {})
    
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
    updated_state = state.copy()
    
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
                hotel_result = await HotelAgentClient.invoke(tool_name, **args)
                
                # Format the response
                if hotel_result.get("error"):
                    response_text = f"I encountered an error while searching for hotels: {hotel_result.get('error_message', 'Unknown error')}"
                    if hotel_result.get("suggestion"):
                        response_text += f"\n\nSuggestion: {hotel_result.get('suggestion')}"
                else:
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

