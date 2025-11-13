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

# Load environment variables from .env file in main directory
# Get the project root directory (2 levels up from langraph/nodes/)
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_main_agent_prompt(agents_called: list, collected_info: dict) -> str:
    """Get the system prompt for the Main Agent."""
    base_prompt = """You are the Main Agent, an orchestrator that coordinates specialized agents to help users with travel tasks.

Your role:
- Understand user requests and determine which specialized agents are needed
- Each specialized agent will intelligently understand the user's message and extract all necessary parameters using LLM reasoning
- You do NOT need to extract parameters - just determine which agents are needed
- After agents return, review the collected information and decide if more agents are needed
- Once you have all necessary information, route to "conversational_agent" to generate the final response

Available specialized agents:
- flight_agent: For flight searches (one-way, round-trip, flexible dates, etc.)
- hotel_agent: For hotel searches (by location, price, dates, etc.)
- visa_agent: For visa requirement checks
- tripadvisor_agent: For location searches, restaurants, attractions, reviews, etc.

IMPORTANT: 
- You ONLY need to determine which agents are needed based on the user's request
- Each agent will intelligently understand the user's message and extract all parameters using LLM reasoning - you don't need to do any parameter extraction
- Simply respond with a JSON object indicating which agents are needed
- The agents have access to full tool documentation and will extract all necessary parameters from the user's message
"""
    
    if agents_called:
        base_prompt += f"\n\nAgents already called: {', '.join(agents_called)}"
        base_prompt += "\nYou have information from these agents. Review if you need more agents or if you're ready to generate the final response."
    
    if collected_info:
        base_prompt += "\n\nCollected information summary:"
        for key, value in collected_info.items():
            if value:
                base_prompt += f"\n- {key}: Information available"
    
    return base_prompt


async def main_agent_node(state: AgentState) -> AgentState:
    """Main Agent node that determines which agents are needed and returns list for parallel execution.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with list of nodes to execute in parallel
    """
    user_message = state.get("user_message", "")
    
    # Prepare messages for LLM to determine which agents are needed
    messages = [
        {"role": "system", "content": get_main_agent_prompt([], {})},
        {"role": "user", "content": f"""Analyze the user's request and determine which specialized agents are needed.

User's message: {user_message}

Available agents:
- flight_agent: For flight searches
- hotel_agent: For hotel searches
- visa_agent: For visa requirement checks
- tripadvisor_agent: For location/restaurant/attraction searches

Respond with a JSON object indicating which agents are needed. Example:
{{"needs_flights": true, "needs_hotels": true, "needs_visa": false, "needs_tripadvisor": false}}

If no specialized agents are needed, respond with all false values."""}
    ]
    
    # Call LLM to determine needed agents
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )
    
    message = response.choices[0].message
    import json
    
    # Extract JSON from the LLM response
    content = message.content or ""
    needs_analysis = {}
    
    # LLM should return JSON - extract it from the response
    try:
        # Try to find JSON in the response (might be wrapped in text)
        # Find the first { and try to match balanced braces
        start_idx = content.find('{')
        if start_idx != -1:
            brace_count = 0
            end_idx = start_idx
            for i in range(start_idx, len(content)):
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
            if brace_count == 0:
                json_str = content[start_idx:end_idx]
                needs_analysis = json.loads(json_str)
            else:
                # Try parsing the whole content as JSON
                needs_analysis = json.loads(content)
        else:
            # Try parsing the whole content as JSON
            needs_analysis = json.loads(content)
    except Exception as e:
        # If LLM didn't return valid JSON, default to no agents needed
        # The LLM should always return valid JSON based on the prompt
        print(f"Warning: Could not parse LLM response as JSON: {e}")
        print(f"LLM response content: {content[:500]}")  # Print first 500 chars for debugging
        needs_analysis = {
            "needs_flights": False,
            "needs_hotels": False,
            "needs_visa": False,
            "needs_tripadvisor": False
        }
    
    # Debug: Log what agents are needed
    print(f"Main agent: Determined needs - flights: {needs_analysis.get('needs_flights')}, hotels: {needs_analysis.get('needs_hotels')}, visa: {needs_analysis.get('needs_visa')}, tripadvisor: {needs_analysis.get('needs_tripadvisor')}")
    
    # Build list of nodes to execute in parallel
    nodes_to_execute = []
    updated_state = state.copy()
    
    # Agents will extract all parameters from user_message using LLM
    # No need to pass task contexts - LLM has access to tool documentation
    
    if needs_analysis.get("needs_flights", False):
        nodes_to_execute.append("flight_agent")
        updated_state["needs_flights"] = True
    else:
        updated_state["needs_flights"] = False
        updated_state["flight_result"] = None
    
    if needs_analysis.get("needs_hotels", False):
        nodes_to_execute.append("hotel_agent")
        updated_state["needs_hotels"] = True
    else:
        updated_state["needs_hotels"] = False
        updated_state["hotel_result"] = None
    
    if needs_analysis.get("needs_visa", False):
        nodes_to_execute.append("visa_agent")
        updated_state["needs_visa"] = True
    else:
        updated_state["needs_visa"] = False
        updated_state["visa_result"] = None
    
    if needs_analysis.get("needs_tripadvisor", False):
        nodes_to_execute.append("tripadvisor_agent")
        updated_state["needs_tripadvisor"] = True
    else:
        updated_state["needs_tripadvisor"] = False
        updated_state["tripadvisor_result"] = None
    
    # If no agents needed, route directly to conversational
    if not nodes_to_execute:
        updated_state["route"] = "conversational_agent"
        updated_state["ready_for_response"] = True
        print("Main agent: No agents needed, routing to conversational_agent")
    else:
        # Return list of nodes for parallel execution
        updated_state["route"] = nodes_to_execute
        print(f"Main agent: Routing to parallel nodes: {nodes_to_execute}")
    
    return updated_state

