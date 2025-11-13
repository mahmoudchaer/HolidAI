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


def get_flight_agent_prompt() -> str:
    """Get the system prompt for the Flight Agent."""
    docs = _load_tool_docs()
    docs_text = _format_tool_docs(docs)
    
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

You have access to the full tool documentation through function calling. Use your LLM reasoning to understand the user's message and call the appropriate tool with the correct parameters."""
    
    return base_prompt + docs_text


async def flight_agent_node(state: AgentState) -> AgentState:
    """Flight Agent node that handles flight search queries.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with response
    """
    user_message = state.get("user_message", "")
    
    # Always use LLM to extract parameters from user message
    # LLM has access to tool documentation and can intelligently extract parameters
    # Get tools available to flight agent
    tools = await FlightAgentClient.list_tools()
    
    # Prepare messages for LLM
    messages = [
        {"role": "system", "content": get_flight_agent_prompt()},
        {"role": "user", "content": user_message}
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
            model="gpt-4",
            messages=messages,
            tools=functions,
            tool_choice="required"  # Force tool call when tools are available
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
        
        if tool_name in ["agent_get_flights_tool", "agent_get_flights_flexible_tool"]:
            import json
            args = json.loads(tool_call.function.arguments)
            
            # Call the flight tool via MCP
            try:
                # Convert args to keyword arguments
                flight_result = await FlightAgentClient.invoke(tool_name, **args)
                
                # Format the response
                if flight_result.get("error"):
                    response_text = f"I encountered an error while searching for flights: {flight_result.get('error_message', 'Unknown error')}"
                    if flight_result.get("suggestion"):
                        response_text += f"\n\nSuggestion: {flight_result.get('suggestion')}"
                else:
                    # Format flight results nicely
                    if tool_name == "agent_get_flights_flexible_tool":
                        flights = flight_result.get("flights", [])
                        if flights:
                            response_text = f"Found {len(flights)} flight options across multiple dates:\n\n"
                            # Show top 5 flights
                            for i, flight in enumerate(flights[:5], 1):
                                price = flight.get("price", "N/A")
                                search_date = flight.get("search_date", "N/A")
                                route = f"{flight_result.get('departure', '?')} → {flight_result.get('arrival', '?')}"
                                response_text += f"{i}. {route} on {search_date}: {price} {flight_result.get('currency', 'USD')}\n"
                            if len(flights) > 5:
                                response_text += f"\n... and {len(flights) - 5} more options."
                        else:
                            response_text = "No flights found for the specified criteria. Try adjusting your search parameters or dates."
                    else:
                        # Regular flight search
                        outbound = flight_result.get("outbound", [])
                        return_flights = flight_result.get("return", [])
                        
                        if outbound:
                            response_text = f"Found {len(outbound)} outbound flight option(s):\n\n"
                            # Show top 3 outbound flights
                            for i, flight in enumerate(outbound[:3], 1):
                                price = flight.get("price", "N/A")
                                route = f"{flight_result.get('departure', '?')} → {flight_result.get('arrival', '?')}"
                                response_text += f"{i}. {route}: {price} {flight_result.get('currency', 'USD')}\n"
                            
                            if return_flights:
                                response_text += f"\nFound {len(return_flights)} return flight option(s):\n\n"
                                for i, flight in enumerate(return_flights[:3], 1):
                                    price = flight.get("price", "N/A")
                                    route = f"{flight_result.get('arrival', '?')} → {flight_result.get('departure', '?')}"
                                    response_text += f"{i}. {route}: {price} {flight_result.get('currency', 'USD')}\n"
                        else:
                            response_text = "No flights found for the specified criteria. Try adjusting your search parameters or dates."
                
                # Store result directly in state for parallel execution
                updated_state["flight_result"] = flight_result
                # No need to set route - using add_edge means we automatically route to join_node
                
            except Exception as e:
                # Store error in result
                updated_state["flight_result"] = {"error": True, "error_message": str(e)}
                # No need to set route - using add_edge means we automatically route to join_node
            
            return updated_state
    
    # No tool call - store empty result
    updated_state["flight_result"] = {"error": True, "error_message": "No flight search parameters provided"}
    # No need to set route - using add_edge means we automatically route to join_node
    
    return updated_state

