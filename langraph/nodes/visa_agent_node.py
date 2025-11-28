"""Visa Agent node for LangGraph orchestration."""

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
from clients.visa_agent_client import VisaAgentClient
# Import memory_filter from the same directory
_nodes_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _nodes_dir)
from memory_filter import filter_memories_for_agent

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


def get_visa_agent_prompt(memories: list = None) -> str:
    """Get the system prompt for the Visa Agent."""
    docs = _load_tool_docs()
    docs_text = _format_tool_docs(docs)
    
    memory_section = ""
    if memories and len(memories) > 0:
        memory_section = "\n\n⚠️ CRITICAL - USER PREFERENCES (MUST USE WHEN CALLING TOOLS):\n" + "\n".join([f"- {mem}" for mem in memories]) + "\n\nWhen calling tools, you MUST:\n- Use these preferences to determine nationality, origin, or destination if mentioned in memories\n- These preferences are about THIS USER - always apply them to tool parameters\n"
    
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

You have access to the full tool documentation through function calling. Use your LLM reasoning to understand the user's message and call the appropriate tool with the correct parameters.

NOTE: If you find placeholders like <NAME_1>, <EMAIL_1>, etc. in the user's message, this is due to the PII redaction node and is expected behavior."""
    
    return base_prompt + memory_section + docs_text


async def visa_agent_node(state: AgentState) -> AgentState:
    """Visa Agent node that handles visa requirement queries.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with response
    """
    user_message = state.get("user_message", "")
    all_memories = state.get("relevant_memories", [])
    
    # Filter memories to only include visa-related ones
    relevant_memories = filter_memories_for_agent(all_memories, "visa")
    if all_memories and not relevant_memories:
        print(f"[MEMORY] Visa agent: {len(all_memories)} total memories, 0 visa-related (filtered out non-visa memories)")
    elif relevant_memories:
        print(f"[MEMORY] Visa agent: {len(all_memories)} total memories, {len(relevant_memories)} visa-related")
    
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
    prompt = get_visa_agent_prompt(memories=relevant_memories)
    
    # Enhance user message with visa-related memories if available
    if relevant_memories:
        print(f"[MEMORY] Visa agent using {len(relevant_memories)} visa-related memories: {relevant_memories}")
        # Add memories to user message to ensure they're considered in tool calls
        memory_context = "\n\nIMPORTANT USER PREFERENCES (MUST APPLY TO TOOL CALLS):\n" + "\n".join([f"- {mem}" for mem in relevant_memories])
        agent_message = agent_message + memory_context
    
    messages = [
        {"role": "system", "content": prompt},
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
    session_id = state.get("session_id", "unknown")
    user_email = state.get("user_email")
    llm_start_time = time.time()
    
    if functions:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            tools=functions,
            tool_choice="required"  # Force tool call when tools are available
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
        agent_name="visa_agent",
        model="gpt-4.1",
        prompt_preview=prompt_preview,
        response_preview=response_preview,
        token_usage=token_usage,
        latency_ms=llm_latency_ms
    )
    
    message = response.choices[0].message
    
    # Check if LLM wants to call a tool
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        if tool_call.function.name == "get_traveldoc_requirement_tool":
            import json
            args = json.loads(tool_call.function.arguments)
            
            # Extract parameters for comparison
            requested_nationality = args.get("nationality", "").strip()
            requested_leaving_from = args.get("leaving_from", "").strip()
            requested_going_to = args.get("going_to", "").strip()
            
            # Check if we already have a valid result for the same parameters
            existing_visa_result = state.get("visa_result")
            if existing_visa_result and not existing_visa_result.get("error"):
                existing_nationality = existing_visa_result.get("nationality", "").strip()
                existing_leaving_from = existing_visa_result.get("leaving_from", "").strip()
                existing_going_to = existing_visa_result.get("going_to", "").strip()
                
                # Normalize for comparison (case-insensitive)
                if (requested_nationality.lower() == existing_nationality.lower() and
                    requested_leaving_from.lower() == existing_leaving_from.lower() and
                    requested_going_to.lower() == existing_going_to.lower()):
                    print(f"✅ VISA DEDUP: Already have valid result for {requested_nationality} -> {requested_going_to}, skipping tool call")
                    # Return existing result without calling tool again
                    return updated_state
            
            # Call the visa tool via MCP
            try:
                visa_result = await VisaAgentClient.invoke(
                    "get_traveldoc_requirement_tool",
                    nationality=requested_nationality,
                    leaving_from=requested_leaving_from,
                    going_to=requested_going_to
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

