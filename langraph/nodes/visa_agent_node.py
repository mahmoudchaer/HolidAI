"""Visa Agent node for LangGraph orchestration."""

import sys
import os
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


def get_visa_agent_prompt() -> str:
    """Get the system prompt for the Visa Agent."""
    return """You are the Visa Agent, a specialized agent that helps users check visa requirements for international travel.

Your role:
- Understand user queries about visa requirements
- Extract nationality, origin country, and destination country from user messages
- Use the get_traveldoc_requirement tool to check visa requirements
- Provide clear, helpful responses about visa requirements

Available tool:
- get_traveldoc_requirement: Checks visa requirements using TravelDoc.aero
  - Parameters:
    - nationality: The traveler's nationality/passport country (e.g., "Lebanon", "United States")
    - leaving_from: The origin country (e.g., "Lebanon", "United States")
    - going_to: The destination country (e.g., "Qatar", "France")

When a user asks about visa requirements, extract the nationality, origin, and destination from their message and use the tool.
If any information is missing, ask the user for clarification.

Provide friendly, clear responses about visa requirements based on the tool results."""


async def visa_agent_node(state: AgentState) -> AgentState:
    """Visa Agent node that handles visa requirement queries.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with response
    """
    user_message = state.get("user_message", "")
    context = state.get("context", {})
    
    # Check if we have task context from delegation
    task_args = context.get("args", {})
    
    # Get tools available to visa agent
    tools = await VisaAgentClient.list_tools()
    
    # Prepare messages for LLM
    messages = [
        {"role": "system", "content": get_visa_agent_prompt()},
        {"role": "user", "content": user_message}
    ]
    
    # Build function calling schema for visa tool
    functions = []
    for tool in tools:
        if tool["name"] == "get_traveldoc_requirement":
            functions.append({
                "type": "function",
                "function": {
                    "name": "get_traveldoc_requirement",
                    "description": tool.get("description", "Get visa requirements for travel"),
                    "parameters": tool.get("inputSchema", {})
                }
            })
    
    # Call LLM with function calling
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        tools=functions if functions else None,
        tool_choice="auto"
    )
    
    message = response.choices[0].message
    updated_state = state.copy()
    
    # Check if LLM wants to call a tool
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        if tool_call.function.name == "get_traveldoc_requirement":
            import json
            args = json.loads(tool_call.function.arguments)
            
            # Call the visa tool via MCP
            try:
                visa_result = await VisaAgentClient.invoke(
                    "get_traveldoc_requirement",
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
                
                updated_state["last_response"] = response_text
                updated_state["route"] = "main_agent"  # Return to main agent
                
            except Exception as e:
                updated_state["last_response"] = f"I encountered an error while checking visa requirements: {str(e)}"
                updated_state["route"] = "main_agent"
            
            return updated_state
    
    # No tool call - respond directly
    assistant_message = message.content or "I can help you check visa requirements. Please provide your nationality, origin country, and destination country."
    updated_state["route"] = "main_agent"
    updated_state["last_response"] = assistant_message
    
    return updated_state

