"""Utilities Agent node for LangGraph orchestration."""

import sys
import os
import json
import time
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from agent_logger import log_llm_call

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "mcp_system"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import AgentState
from clients.utilities_agent_client import UtilitiesAgentClient
# Import memory_filter from the same directory
import sys
import os
_nodes_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _nodes_dir)
from memory_filter import filter_memories_for_agent

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


def get_utilities_agent_prompt(memories: list = None) -> str:
    """Get the system prompt for the Utilities Agent."""
    docs = _load_tool_docs()
    docs_text = _format_tool_docs(docs)
    
    memory_section = ""
    if memories and len(memories) > 0:
        memory_section = "\n\n⚠️ CRITICAL - USER PREFERENCES (MUST USE WHEN CALLING TOOLS):\n" + "\n".join([f"- {mem}" for mem in memories]) + "\n\nWhen calling tools, you MUST:\n- Use these preferences to inform your tool calls (e.g., preferred currency, location preferences)\n- These preferences are about THIS USER - always apply them to tool parameters\n"
    
    base_prompt = """You are the Utilities Agent, a specialized agent that helps users with utility functions like weather, currency conversion, and date/time information.

CRITICAL: You MUST use the available tools to provide utility information. DO NOT respond without calling a tool.

Your role:
- Understand the user's message using your LLM reasoning capabilities
- Determine which utility tool(s) are needed based on EXPLICITLY REQUESTED utilities
- ONLY call tools that are directly requested by the user - don't add extra information
- Use the appropriate tool with parameters you determine from the user's message
- The tool schemas will show you exactly what parameters are needed
- You CAN make MULTIPLE parallel tool calls if user requests multiple operations (e.g., "weather in Paris and weather in Beirut" = 2 tool calls)

CRITICAL - STRICT REQUEST MATCHING:
- If user asks to "convert prices" or "convert to EUR/AED/etc" → use convert_currencies ONLY
- If user asks for "weather" or "temperature" or "conditions" → use get_real_time_weather
- If user asks for "eSIM" or "mobile data" → use get_esim_bundles
- If user asks for "holidays" → use get_holidays
- If user asks for "current time" or "what time is it" → use get_real_time_date_time

FORBIDDEN BEHAVIORS:
- DO NOT call weather just because a city is mentioned - ONLY if weather is explicitly requested
- DO NOT add extra information - if user asks for currency conversion, ONLY do currency conversion
- DO NOT call multiple tools unless the user explicitly requests multiple operations
- Focus ONLY on the EXACT utility operations mentioned in the user's message

EXAMPLES:
- "Convert prices to EUR" → ONLY call convert_currencies (1 tool call)
- "Get weather in Beirut" → ONLY call get_real_time_weather for Beirut (1 tool call)
- "Weather in Paris and weather in Beirut" → Call get_real_time_weather TWICE (2 parallel tool calls: one for Paris, one for Beirut)
- "Convert to EUR and get weather" → Call BOTH convert_currencies AND get_real_time_weather (2 different tool calls)
- "Get hotels in Beirut. Convert prices to EUR" → ONLY call convert_currencies (weather NOT requested)

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
- For date/time: Extract city name or country name from the user's message
- For eSIM bundles: Extract country name from the user's message (e.g., "Qatar", "USA", "Japan")
- For holidays: Extract country name, and optionally year, month, and day from the user's message (e.g., "holidays in Qatar", "holidays in USA in December", "holidays in Lebanon on January 1st")
- Use the tool schemas to understand required vs optional parameters
- ALWAYS call a tool - do not ask for clarification unless absolutely critical information is missing
- You have access to the full tool documentation through function calling - use it to understand parameter requirements

You have access to the full tool documentation through function calling. Use your LLM reasoning to understand the user's message and call the appropriate tool with the correct parameters."""
    
    return base_prompt + memory_section + docs_text


async def utilities_agent_node(state: AgentState) -> AgentState:
    """Utilities Agent node that handles utility queries (weather, currency, date/time).
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with response
    """
    from datetime import datetime
    start_time = datetime.now()
    print(f"[{start_time.strftime('%H:%M:%S.%f')[:-3]}] 🛠️ UTILITIES AGENT STARTED")
    
    user_message = state.get("user_message", "")
    all_memories = state.get("relevant_memories", [])
    
    # Filter memories to only include utilities-related ones
    relevant_memories = filter_memories_for_agent(all_memories, "utilities")
    if all_memories and not relevant_memories:
        print(f"[MEMORY] Utilities agent: {len(all_memories)} total memories, 0 utilities-related (filtered out non-utilities memories)")
    elif relevant_memories:
        print(f"[MEMORY] Utilities agent: {len(all_memories)} total memories, {len(relevant_memories)} utilities-related")
    
    # Get current step context from execution plan
    execution_plan = state.get("execution_plan", [])
    current_step_index = state.get("current_step", 1) - 1  # current_step is 1-indexed
    
    # If we have an execution plan, use the step description as context
    step_context = ""
    if execution_plan and 0 <= current_step_index < len(execution_plan):
        current_step = execution_plan[current_step_index]
        step_context = current_step.get("description", "")
        print(f"🔍 UTILITIES DEBUG - Step context: {step_context}")
    
    # Build the message to send to LLM
    if step_context:
        # Use step description as primary instruction, with user message as background
        agent_message = f"""Current task: {step_context}

Background context from user: {user_message}

Focus ONLY on the current task described above. Do NOT add extra operations not mentioned in the current task."""
    else:
        # Fallback to user message if no step context
        agent_message = user_message
    
    updated_state = state.copy()
    
    # Always use LLM to extract parameters from user message
    # LLM has access to tool documentation and can intelligently extract parameters
    # Get tools available to utilities agent
    tools = await UtilitiesAgentClient.list_tools()
    
    # Prepare messages for LLM
    prompt = get_utilities_agent_prompt(memories=relevant_memories)
    
    # Enhance user message with utilities-related memories if available
    if relevant_memories:
        print(f"[MEMORY] Utilities agent using {len(relevant_memories)} utilities-related memories: {relevant_memories}")
        # Add memories to user message to ensure they're considered in tool calls
        memory_context = "\n\nIMPORTANT USER PREFERENCES (MUST APPLY TO TOOL CALLS):\n" + "\n".join([f"- {mem}" for mem in relevant_memories])
        agent_message = agent_message + memory_context
    
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": agent_message}
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
    
    # Call LLM with function calling - require tool use when functions are available
    session_id = state.get("session_id", "unknown")
    user_email = state.get("user_email")
    llm_start_time = time.time()
    
    if functions:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            tools=functions,
            tool_choice="required",  # Force tool call when tools are available
            parallel_tool_calls=True  # Enable multiple parallel tool calls (e.g., weather for 2 cities)
        )
    else:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages
        )
    
    llm_latency_ms = (time.time() - llm_start_time) * 1000
    
    # Log LLM call
    prompt_preview = str(messages[-1].get("content", "")) if messages else ""
    response_preview = response.choices[0].message.content if response.choices[0].message.content else ""
    token_usage = {
        "prompt_tokens": response.usage.prompt_tokens if hasattr(response, 'usage') and response.usage else None,
        "completion_tokens": response.usage.completion_tokens if hasattr(response, 'usage') and response.usage else None,
        "total_tokens": response.usage.total_tokens if hasattr(response, 'usage') and response.usage else None
    } if hasattr(response, 'usage') and response.usage else None
    
    log_llm_call(
        session_id=session_id,
        user_email=user_email,
        agent_name="utilities_agent",
        model="gpt-4.1",
        prompt_preview=prompt_preview,
        response_preview=response_preview,
        token_usage=token_usage,
        latency_ms=llm_latency_ms
    )
    
    message = response.choices[0].message
    
    # Check if LLM wants to call tools (can be multiple parallel calls)
    if message.tool_calls:
        import json
        
        # Debug: Log how many tool calls the LLM made
        print(f"🔍 UTILITIES DEBUG - User message: {user_message}")
        print(f"🔍 UTILITIES DEBUG - Number of tool calls: {len(message.tool_calls)}")
        
        # Process ALL tool calls (for multiple weather requests, currency conversions, etc.)
        all_results = []
        
        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            
            if tool_name in ["get_real_time_weather", "convert_currencies", "get_real_time_date_time", "get_esim_bundles", "get_holidays"]:
                args = json.loads(tool_call.function.arguments)
                
                # Debug: Log each tool call
                print(f"🔍 UTILITIES DEBUG - Tool {len(all_results)+1}: {tool_name}, Args: {args}")
                
                # Validate that weather wasn't called unnecessarily
                if tool_name == "get_real_time_weather":
                    if "weather" not in user_message.lower() and "temperature" not in user_message.lower() and "conditions" not in user_message.lower():
                        print(f"⚠️ WARNING: Weather called but not requested in message!")
                        print(f"⚠️ User message was: {user_message}")
                        print(f"⚠️ Skipping weather call - not explicitly requested")
                        continue  # Skip this tool call, process next one
                
                # Call the utilities tool via MCP
                try:
                    utilities_result = await UtilitiesAgentClient.invoke(tool_name, **args)
                    all_results.append({
                        "tool": tool_name,
                        "args": args,
                        "result": utilities_result
                    })
                    
                except Exception as e:
                    all_results.append({
                        "tool": tool_name,
                        "args": args,
                        "result": {"error": True, "error_message": str(e)}
                    })
        
        # Combine all results
        if len(all_results) == 0:
            # No valid tool calls
            updated_state["utilities_result"] = {"error": True, "error_message": "No valid utility operations performed"}
        elif len(all_results) == 1:
            # Single tool call - check if it's eSIM and summarize
            single_result = all_results[0]["result"]
            
            # ===== INTELLIGENT SUMMARIZATION FOR ESIM =====
            if all_results[0]["tool"] == "get_esim_bundles" and not single_result.get("error"):
                bundles = single_result.get("bundles", [])
                if bundles and len(bundles) > 15:
                    try:
                        from utils.result_summarizer import summarize_esim_results
                        print(f"🧠 Utilities agent: Summarizing {len(bundles)} eSIM bundles for conversational agent...")
                        summarized = await summarize_esim_results(
                            bundles,
                            user_message,
                            step_context
                        )
                        single_result["bundles"] = summarized.get("bundles", [])
                        single_result["original_count"] = len(bundles)
                        single_result["summarized_count"] = len(summarized.get("bundles", []))
                        single_result["summary"] = summarized.get("summary", "")
                        print(f"✅ Utilities agent: Summarized from {len(bundles)} to {single_result['summarized_count']} bundles")
                    except Exception as e:
                        print(f"⚠️ eSIM summarization failed, using original data: {e}")
            
            updated_state["utilities_result"] = single_result
        else:
            # Multiple tool calls - summarize eSIM if present
            for result_obj in all_results:
                if result_obj["tool"] == "get_esim_bundles" and not result_obj["result"].get("error"):
                    bundles = result_obj["result"].get("bundles", [])
                    if bundles and len(bundles) > 15:
                        try:
                            from utils.result_summarizer import summarize_esim_results
                            print(f"🧠 Utilities agent: Summarizing {len(bundles)} eSIM bundles (multi-result)...")
                            summarized = await summarize_esim_results(
                                bundles,
                                user_message,
                                step_context
                            )
                            result_obj["result"]["bundles"] = summarized.get("bundles", [])
                            result_obj["result"]["original_count"] = len(bundles)
                            result_obj["result"]["summarized_count"] = len(summarized.get("bundles", []))
                            result_obj["result"]["summary"] = summarized.get("summary", "")
                            print(f"✅ Utilities agent: Summarized from {len(bundles)} to {result_obj['result']['summarized_count']} bundles")
                        except Exception as e:
                            print(f"⚠️ eSIM summarization failed, using original data: {e}")
            
            # Multiple tool calls - return combined results
            updated_state["utilities_result"] = {
                "error": False,
                "multiple_results": True,
                "results": all_results
            }
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"[{end_time.strftime('%H:%M:%S.%f')[:-3]}] 🛠️ UTILITIES AGENT COMPLETED (Duration: {duration:.3f}s)")
        return updated_state
    
    # No tool call - store empty result
    updated_state["utilities_result"] = {"error": True, "error_message": "No utility parameters provided"}
    # No need to set route - using add_edge means we automatically route to join_node
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"[{end_time.strftime('%H:%M:%S.%f')[:-3]}] 🛠️ UTILITIES AGENT COMPLETED (Duration: {duration:.3f}s)")
    return updated_state

