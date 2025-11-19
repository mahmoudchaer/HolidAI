"""Visa Agent node for LangGraph orchestration."""

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
from clients.visa_agent_client import VisaAgentClient

# Load environment variables from .env file in main directory
# Get the project root directory (2 levels up from langraph/nodes/)
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _load_tool_docs() -> dict:
    """Load tool documentation from JSON file."""
    docs_path = project_root / "mcp_system" / "tool_docs" / "visa_docs.json"
    try:
        with open(docs_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load visa tool docs: {e}")
        return {}


def _format_tool_docs(docs: dict) -> str:
    """Format tool documentation for inclusion in prompt."""
    if not docs:
        return ""
    
    formatted = "\n\n=== TOOL DOCUMENTATION ===\n\n"
    
    for tool_name, tool_info in docs.items():
        # Map tool name to actual tool name used in the system
        actual_tool_name = tool_name.replace("get_traveldoc_requirement", "get_traveldoc_requirement_tool")
        
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


def get_visa_agent_prompt() -> str:
    """Get the system prompt for the Visa Agent."""
    docs = _load_tool_docs()
    docs_text = _format_tool_docs(docs)
    
    base_prompt = """You are the Visa Agent, a specialized agent that helps users check visa requirements for international travel.

CRITICAL: You MUST use the available tools to check visa requirements. Do NOT respond without calling a tool.

Your role:
- Understand the user's message using your LLM reasoning capabilities
- Use your understanding to determine what visa requirement parameters are needed
- Use the get_traveldoc_requirement_tool tool to check visa requirements
- The tool schemas will show you exactly what parameters are needed

Available tool (you will see its full schema with function calling):
- get_traveldoc_requirement_tool: Checks visa requirements using TravelDoc.aero

IMPORTANT:
- Use your LLM understanding to determine parameters from the user's message - NO code-based parsing is used:
  - nationality: The traveler's nationality/passport country (determine from user's message)
  - leaving_from: The origin country (determine from user's message)
  - going_to: The destination country (determine from user's message)
- Use the tool schemas to understand required vs optional parameters
- ALWAYS call a tool - do not ask for clarification unless absolutely critical information is missing
- You have access to the full tool documentation through function calling - use it to understand parameter requirements

You have access to the full tool documentation through function calling. Use your LLM reasoning to understand the user's message and call the appropriate tool with the correct parameters."""
    
    return base_prompt + docs_text


async def visa_agent_node(state: AgentState) -> AgentState:
    """Visa Agent node that handles visa requirement queries.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with response
    """
    user_message = state.get("user_message", "")
    
    # Get current step context from execution plan
    execution_plan = state.get("execution_plan", [])
    current_step_index = state.get("current_step", 1) - 1  # current_step is 1-indexed
    
    # If we have an execution plan, use the step description as context
    step_context = ""
    if execution_plan and 0 <= current_step_index < len(execution_plan):
        current_step = execution_plan[current_step_index]
        step_context = current_step.get("description", "")
        print(f"🔍 VISA DEBUG - Step context: {step_context}")
    
    # Build the message to send to LLM
    if step_context:
        # Use step description as primary instruction, with user message as background
        agent_message = f"""Current task: {step_context}

Background context from user: {user_message}

Focus on the visa requirement check described above."""
    else:
        # Fallback to user message if no step context
        agent_message = user_message
    
    updated_state = state.copy()
    
    # Always use LLM to extract parameters from user message
    # LLM has access to tool documentation and can intelligently extract parameters
    # Get tools available to visa agent
    tools = await VisaAgentClient.list_tools()
    
    # Prepare messages for LLM
    messages = [
        {"role": "system", "content": get_visa_agent_prompt()},
        {"role": "user", "content": agent_message}
    ]
    
    # Build function calling schema for visa tool
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
        if tool["name"] == "get_traveldoc_requirement_tool":
            input_schema = tool.get("inputSchema", {})
            input_schema = _sanitize_schema(input_schema)
            functions.append({
                "type": "function",
                "function": {
                    "name": "get_traveldoc_requirement_tool",
                    "description": tool.get("description", "Get visa requirements for travel"),
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
    
    # Check if LLM wants to call a tool
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        if tool_call.function.name == "get_traveldoc_requirement_tool":
            import json
            args = json.loads(tool_call.function.arguments)
            
            # Call the visa tool via MCP
            try:
                visa_result = await VisaAgentClient.invoke(
                    "get_traveldoc_requirement_tool",
                    nationality=args.get("nationality", ""),
                    leaving_from=args.get("leaving_from", ""),
                    going_to=args.get("going_to", "")
                )
                
                # Format the response
                if visa_result.get("error"):
                    response_text = f"I encountered an error while checking visa requirements: {visa_result.get('error_message', 'Unknown error')}"
                    if visa_result.get("suggestion"):
                        response_text += f"\n\nSuggestion: {visa_result.get('suggestion')}"
                else:
                    visa_info = visa_result.get("result", "No visa information available.")
                    response_text = f"Here are the visa requirements:\n\n{visa_info}"
                
                # Store result directly in state for parallel execution
                updated_state["visa_result"] = visa_result
                # No need to set route - using add_edge means we automatically route to join_node
                
            except Exception as e:
                # Store error in result
                updated_state["visa_result"] = {"error": True, "error_message": str(e)}
                # No need to set route - using add_edge means we automatically route to join_node
            
            return updated_state
    
    # No tool call - store empty result
    updated_state["visa_result"] = {"error": True, "error_message": "No visa requirement parameters provided"}
    # No need to set route - using add_edge means we automatically route to join_node
    
    return updated_state

