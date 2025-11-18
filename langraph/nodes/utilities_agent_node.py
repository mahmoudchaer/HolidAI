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

IMPORTANT - TOOL SELECTION PRIORITY:
- If user asks about flights/travel/hotels with dates → Use get_real_time_weather (weather affects travel planning)
- If user explicitly asks for holidays → Use get_holidays
- If user explicitly asks about weather → Use get_real_time_weather
- If user asks about currency → Use convert_currencies
- If user asks about date/time → Use get_real_time_date_time
- If user asks about eSIM → Use get_esim_bundles

CRITICAL: When user mentions travel/flights/hotels with dates, they need WEATHER information, NOT holidays. Only use get_holidays when the user explicitly asks about holidays.

PARAMETER EXTRACTION:
- Use your LLM understanding to determine parameters from the user's message - NO code-based parsing is used
- For weather: Extract city name or country name from the user's message (destination city for travel queries)
- For currency conversion: Extract from_currency, to_currency, and amount (if specified) from the user's message
- For date/time: Extract city name or country name from the user's message. If user asks for "today's date" or "current date" without specifying a location, use "UTC" as the location parameter. The location parameter is optional and defaults to UTC.
- For eSIM bundles: Extract country name from the user's message (e.g., "Qatar", "USA", "Japan")
- For holidays: Extract country name, and optionally year, month, and day from the user's message (e.g., "holidays in Qatar", "holidays in USA in December", "holidays in Lebanon on January 1st")
- Use the tool schemas to understand required vs optional parameters
- ALWAYS call a tool - do not ask for clarification unless absolutely critical information is missing
- You have access to the full tool documentation through function calling - use it to understand parameter requirements

You have access to the full tool documentation through function calling. Use your LLM reasoning to understand the user's message and call the appropriate tool with the correct parameters."""
    
    return base_prompt + docs_text


def _plan_utility_tasks(user_message: str) -> dict:
    """Use the LLM to determine which utility tools are required and their parameters."""
    planning_prompt = """You convert user travel/utility requests into structured tool plans.
Return strict JSON with this shape (do not add text outside JSON):
{
  "weather": {"needed": bool, "location": "<city or country or ''>"},
  "date_time": {"needed": bool, "location": "<city or country or ''>"},
  "esim": {"needed": bool, "country": "<country or ''>"},
  "currency": {"needed": bool, "from_currency": "<code>", "to_currency": "<code>", "amount": <number or null>},
  "holidays": {"needed": bool, "country": "<country or ''>", "year": <int or null>, "month": <int or null>, "day": <int or null>}
}
Rules:
- Only mark a tool as needed if the user explicitly or implicitly requests it.
- Reuse the same location for weather and date/time when appropriate.
- If information is missing, keep needed=false (do NOT invent data).
- Ensure amount is a number if provided, otherwise null.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": planning_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"Utilities planner error: {e}")
        return {}


async def utilities_agent_node(state: AgentState) -> AgentState:
    """Utilities Agent node that handles utility queries (weather, currency, date/time)."""
    import time
    from datetime import datetime
    
    start_time = time.time()
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    # Check if this node should execute (for parallel execution mode)
    pending_nodes = state.get("pending_nodes", [])
    if isinstance(pending_nodes, list) and len(pending_nodes) > 0:
        # If we're in parallel mode and this node is not in pending_nodes, skip execution
        if "utilities_agent" not in pending_nodes:
            # Not supposed to execute, just pass through to join_node
            updated_state = state.copy()
            updated_state["route"] = "join_node"
            print(f"[{timestamp}] Utilities agent: SKIPPED (not in pending_nodes: {pending_nodes})")
            return updated_state
    
    print(f"[{timestamp}] Utilities agent: STARTING execution (pending_nodes: {pending_nodes})")
    
    user_message = state.get("user_message", "")
    updated_state = state.copy()
    
    # First, try to determine if multiple utility tools are required
    plan = _plan_utility_tasks(user_message)
    requested_tools = {
        "weather": plan.get("weather", {}),
        "date_time": plan.get("date_time", {}),
        "esim": plan.get("esim", {}),
        "currency": plan.get("currency", {}),
        "holidays": plan.get("holidays", {})
    }
    
    def _tool_needed(entry: dict, required_fields: list) -> bool:
        if not entry or not entry.get("needed"):
            return False
        return all(entry.get(field) not in [None, "", []] for field in required_fields)
    
    multi_tool_plan = any([
        _tool_needed(requested_tools["weather"], ["location"]),
        _tool_needed(requested_tools["date_time"], ["location"]),
        _tool_needed(requested_tools["esim"], ["country"]),
        _tool_needed(requested_tools["currency"], ["from_currency", "to_currency"]),
        _tool_needed(requested_tools["holidays"], ["country"])
    ])
    
    if multi_tool_plan:
        combined_result = {
            "error": False,
            "tasks": {},
            "errors": []
        }
        if "results" not in updated_state:
            updated_state["results"] = {}
        results_ref = updated_state["results"]
        executed_any = False
        
        async def _execute_tool(tool_name: str, params: dict, result_key: str = None):
            nonlocal executed_any
            try:
                result = await UtilitiesAgentClient.invoke(tool_name, **params)
            except Exception as exc:
                result = {"error": True, "error_message": str(exc)}
            combined_result["tasks"][tool_name] = result
            if result.get("error"):
                combined_result["error"] = True
                combined_result["errors"].append({
                    "tool": tool_name,
                    "message": result.get("error_message", "Unknown error")
                })
            executed_any = True
            if result_key:
                results_ref[result_key] = result
        
        if _tool_needed(requested_tools["weather"], ["location"]):
            await _execute_tool(
                "get_real_time_weather",
                {"location": requested_tools["weather"]["location"]},
                "weather_data"
            )
        
        if _tool_needed(requested_tools["date_time"], ["location"]):
            await _execute_tool(
                "get_real_time_date_time",
                {"location": requested_tools["date_time"]["location"]},
                "date_time_data"
            )
        
        if _tool_needed(requested_tools["esim"], ["country"]):
            await _execute_tool(
                "get_esim_bundles",
                {"country": requested_tools["esim"]["country"]},
                "esim_data"
            )
        
        if _tool_needed(requested_tools["currency"], ["from_currency", "to_currency"]):
            currency_params = {
                "from_currency": requested_tools["currency"]["from_currency"],
                "to_currency": requested_tools["currency"]["to_currency"]
            }
            amount = requested_tools["currency"].get("amount")
            if isinstance(amount, (int, float)):
                currency_params["amount"] = amount
            await _execute_tool(
                "convert_currencies",
                currency_params,
                "currency_data"
            )
        
        if _tool_needed(requested_tools["holidays"], ["country"]):
            holiday_params = {"country": requested_tools["holidays"]["country"]}
            for key in ["year", "month", "day"]:
                value = requested_tools["holidays"].get(key)
                if value not in [None, ""]:
                    holiday_params[key] = value
            await _execute_tool(
                "get_holidays",
                holiday_params,
                "holidays_data"
            )
        
        if executed_any:
            updated_state["utilities_result"] = combined_result
            results_ref["utilities_agent"] = combined_result
            results_ref["utilities"] = combined_result
            results_ref["utilities_result"] = combined_result
            elapsed = time.time() - start_time
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{timestamp}] Utilities agent: COMPLETED in {elapsed:.2f}s")
            return updated_state
    
    # Fallback to single-tool function-calling path
    tools = await UtilitiesAgentClient.list_tools()
    messages = [
        {"role": "system", "content": get_utilities_agent_prompt()},
        {"role": "user", "content": user_message}
    ]
    
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
        if tool["name"] in ["get_real_time_weather", "convert_currencies", "get_real_time_date_time", "get_esim_bundles", "get_holidays"]:
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
    
    if functions:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=functions,
            tool_choice="required"
        )
    else:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
    
    message = response.choices[0].message
    
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        tool_name = tool_call.function.name
        
        if tool_name in ["get_real_time_weather", "convert_currencies", "get_real_time_date_time", "get_esim_bundles", "get_holidays"]:
            args = json.loads(tool_call.function.arguments)
            try:
                utilities_result = await UtilitiesAgentClient.invoke(tool_name, **args)
                
                updated_state["utilities_result"] = utilities_result
                if "results" not in updated_state:
                    updated_state["results"] = {}
                updated_state["results"]["utilities_agent"] = utilities_result
                updated_state["results"]["utilities"] = utilities_result
                updated_state["results"]["utilities_result"] = utilities_result
                elapsed = time.time() - start_time
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"[{timestamp}] Utilities agent: COMPLETED in {elapsed:.2f}s")
                if tool_name == "get_real_time_weather":
                    updated_state["results"]["weather_data"] = utilities_result
                elif tool_name == "get_esim_bundles":
                    updated_state["results"]["esim_data"] = utilities_result
                elif tool_name == "get_holidays":
                    updated_state["results"]["holidays_data"] = utilities_result
                elif tool_name == "get_real_time_date_time":
                    updated_state["results"]["date_time_data"] = utilities_result
                elif tool_name == "convert_currencies":
                    updated_state["results"]["currency_data"] = utilities_result
                
            except Exception as e:
                error_result = {"error": True, "error_message": str(e)}
                updated_state["utilities_result"] = error_result
                if "results" not in updated_state:
                    updated_state["results"] = {}
                updated_state["results"]["utilities_agent"] = error_result
                updated_state["results"]["utilities"] = error_result
                updated_state["results"]["utilities_result"] = error_result
                elapsed = time.time() - start_time
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"[{timestamp}] Utilities agent: COMPLETED with ERROR in {elapsed:.2f}s")
            
            return updated_state
    
    error_result = {"error": True, "error_message": "No utility parameters provided"}
    updated_state["utilities_result"] = error_result
    if "results" not in updated_state:
        updated_state["results"] = {}
    updated_state["results"]["utilities_agent"] = error_result
    updated_state["results"]["utilities"] = error_result
    updated_state["results"]["utilities_result"] = error_result
    elapsed = time.time() - start_time
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] Utilities agent: COMPLETED (no tool call) in {elapsed:.2f}s")
    
    return updated_state

