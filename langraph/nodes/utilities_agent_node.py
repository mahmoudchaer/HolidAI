"""Utilities Agent node for LangGraph orchestration."""

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
from clients.utilities_agent_client import UtilitiesAgentClient

# Load environment variables from .env file in main directory
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _load_tool_docs() -> dict:
    """Load tool documentation from JSON file."""
    docs_path = project_root / "mcp_system" / "tool_docs" / "utilities_docs.json"
    try:
        with open(docs_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load utilities tool docs: {e}")
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


def get_utilities_agent_prompt() -> str:
    """Get the system prompt for the Utilities Agent."""
    docs = _load_tool_docs()
    docs_text = _format_tool_docs(docs)
    
    base_prompt = """You are the Utilities Agent, a specialized agent that helps users with utility functions like weather, currency conversion, and date/time information.

CRITICAL: You MUST use the available tools to provide utility information. Do NOT respond without calling a tool.

Your role:
- Understand the user's message using your LLM reasoning capabilities
- Determine which utility tool is needed based on the user's query
- Use the appropriate tool with parameters you determine from the user's message
- The tool schemas will show you exactly what parameters are needed

Available tools (you will see their full schemas with function calling):
- get_real_time_weather: Get current weather for a city or country
- convert_currencies: Convert between currency codes
- get_real_time_date_time: Get current date and time for a city or country
- get_esim_bundles: Get available eSIM bundles for a country
- get_holidays: Get holidays for a specific country, optionally filtered by date

IMPORTANT:
- Use your LLM understanding to determine parameters from the user's message - NO code-based parsing is used
- For weather: Extract city name or country name from the user's message
- For currency conversion: Extract from_currency, to_currency, and amount (if specified) from the user's message
- For date/time: Extract city name or country name from the user's message. If user asks for "today's date" or "current date" without specifying a location, use "UTC" as the location parameter. The location parameter is optional and defaults to UTC.
- For eSIM bundles: Extract country name from the user's message (e.g., "Qatar", "USA", "Japan")
- For holidays: Extract country name, and optionally year, month, and day from the user's message (e.g., "holidays in Qatar", "holidays in USA in December", "holidays in Lebanon on January 1st")
- Use the tool schemas to understand required vs optional parameters
- ALWAYS call a tool - do not ask for clarification unless absolutely critical information is missing
- You have access to the full tool documentation through function calling - use it to understand parameter requirements

You have access to the full tool documentation through function calling. Use your LLM reasoning to understand the user's message and call the appropriate tool with the correct parameters."""
    
    return base_prompt + docs_text


async def utilities_agent_node(state: AgentState) -> AgentState:
    """Utilities Agent node that handles utility queries (weather, currency, date/time).
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with response
    """
    user_message = state.get("user_message", "")
    updated_state = state.copy()
    
    # Always use LLM to extract parameters from user message
    # LLM has access to tool documentation and can intelligently extract parameters
    # Get tools available to utilities agent
    tools = await UtilitiesAgentClient.list_tools()
    
    # Prepare messages for LLM
    messages = [
        {"role": "system", "content": get_utilities_agent_prompt()},
        {"role": "user", "content": user_message}
    ]
    
    # Build function calling schema for utilities tools
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
        if tool["name"] in ["get_real_time_weather", "convert_currencies", "get_real_time_date_time", "get_esim_bundles"]:
            input_schema = tool.get("inputSchema", {})
            input_schema = _sanitize_schema(input_schema)
            functions.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", f"Utility tool: {tool['name']}"),
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
        
        if tool_name in ["get_real_time_weather", "convert_currencies", "get_real_time_date_time", "get_esim_bundles", "get_holidays"]:
            import json
            args = json.loads(tool_call.function.arguments)
            
            # LLM has extracted all parameters from user message - use them directly
            # Call the utilities tool via MCP
            try:
                utilities_result = await UtilitiesAgentClient.invoke(tool_name, **args)
                
                # Store result in both legacy field and new results structure
                updated_state["utilities_result"] = utilities_result
                # Initialize results dict if not present
                if "results" not in updated_state:
                    updated_state["results"] = {}
                updated_state["results"]["utilities_agent"] = utilities_result
                updated_state["results"]["utilities"] = utilities_result
                updated_state["results"]["utilities_result"] = utilities_result
                # Also store with semantic keys based on tool used
                if tool_name == "get_real_time_weather":
                    updated_state["results"]["weather_data"] = utilities_result
                elif tool_name == "get_esim_bundles":
                    updated_state["results"]["esim_data"] = utilities_result
                # No need to set route - using add_edge means we automatically route to join_node
                
            except Exception as e:
                # Store error in result
                error_result = {"error": True, "error_message": str(e)}
                updated_state["utilities_result"] = error_result
                if "results" not in updated_state:
                    updated_state["results"] = {}
                updated_state["results"]["utilities_agent"] = error_result
                updated_state["results"]["utilities"] = error_result
                updated_state["results"]["utilities_result"] = error_result
                # No need to set route - using add_edge means we automatically route to join_node
            
            return updated_state
    
    # No tool call - store empty result
    error_result = {"error": True, "error_message": "No utility parameters provided"}
    updated_state["utilities_result"] = error_result
    if "results" not in updated_state:
        updated_state["results"] = {}
    updated_state["results"]["utilities_agent"] = error_result
    updated_state["results"]["utilities"] = error_result
    updated_state["results"]["utilities_result"] = error_result
    # No need to set route - using add_edge means we automatically route to join_node
    
    return updated_state

