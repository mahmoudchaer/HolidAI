"""Main Agent node for LangGraph orchestration."""

import sys
import os
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "mcp_system"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import AgentState
from clients.main_agent_client import MainAgentClient

# Load environment variables from .env file in main directory
# Get the project root directory (2 levels up from langraph/nodes/)
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_main_agent_prompt() -> str:
    """Get the system prompt for the Main Agent."""
    return """You are the Main Agent, an orchestrator that coordinates specialized agents to help users with travel tasks.

Your role:
- Understand user requests and determine if a specialized agent is needed
- Delegate tasks to specialized agents when appropriate
- Extract structured parameters from user messages for delegated tasks
- Provide direct responses for general queries

Available specialized agents:
- hotel_agent: Handles hotel searches. Use task "get_hotel_rates" for hotel rate searches.

When a user asks about hotels, use the delegate tool to route to the hotel_agent.
Extract the following parameters from the user's message:
- checkin: Check-in date in YYYY-MM-DD format (e.g., "2025-12-10")
- checkout: Check-out date in YYYY-MM-DD format (e.g., "2025-12-17")
- occupancies: Array of occupancy objects, each with "adults" (integer) and optionally "children" (array of integers)
- city_name: City name (optional, must be paired with country_code)
- country_code: Country code in ISO 2-letter format (optional, must be paired with city_name)
- hotel_ids: Array of hotel IDs (optional)
- iata_code: IATA code (optional)

The delegate tool takes:
- agent: "hotel_agent"
- task: "get_hotel_rates"
- args: Dictionary with the extracted parameters above

For general questions, respond directly without delegation."""


async def main_agent_node(state: AgentState) -> AgentState:
    """Main Agent node that reasons and delegates tasks.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with route and context
    """
    user_message = state.get("user_message", "")
    
    # Get tools available to main agent
    tools = await MainAgentClient.list_tools()
    
    # Prepare messages for LLM
    messages = [
        {"role": "system", "content": get_main_agent_prompt()},
        {"role": "user", "content": user_message}
    ]
    
    # Build function calling schema for delegate tool
    functions = []
    for tool in tools:
        if tool["name"] == "delegate":
            functions.append({
                "type": "function",
                "function": {
                    "name": "delegate",
                    "description": tool.get("description", "Delegate a task to a specialized agent"),
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
    
    # Check if LLM wants to call a tool (delegate)
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        if tool_call.function.name == "delegate":
            import json
            args = json.loads(tool_call.function.arguments)
            
            # Call the delegate tool via MCP
            delegation_result = await MainAgentClient.invoke(
                "delegate",
                agent=args["agent"],
                task=args["task"],
                args=args.get("args", {})
            )
            
            # Update state to route to the specified agent
            updated_state["route"] = args["agent"]
            updated_state["context"] = {
                "task": args["task"],
                "args": args.get("args", {}),
                "delegation_result": delegation_result
            }
            
            return updated_state
    
    # No delegation - respond directly
    assistant_message = message.content or "I'm here to help you with your travel needs."
    updated_state["route"] = "main_agent"
    updated_state["last_response"] = assistant_message
    
    return updated_state

