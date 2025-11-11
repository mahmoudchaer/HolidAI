"""Conversational Agent node for LangGraph orchestration - generates final user response."""

import sys
import os
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import AgentState

# Load environment variables from .env file in main directory
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_conversational_agent_prompt() -> str:
    """Get the system prompt for the Conversational Agent."""
    return """You are a helpful travel assistant that provides friendly, clear responses to users about their travel queries.

Your role:
- Take the user's original message and all the information gathered from specialized agents
- Synthesize this information into a natural, conversational response
- Present the information in a clear, organized, and helpful manner
- Be friendly, professional, and concise
- If information is missing or incomplete, acknowledge it gracefully

You have access to:
- The user's original message
- Information collected from flight, hotel, visa, and TripAdvisor agents (if any were called)

Create a comprehensive, well-structured response that addresses the user's query using all available information."""


async def conversational_agent_node(state: AgentState) -> AgentState:
    """Conversational Agent node that generates the final user response.
    
    Args:
        state: Current agent state with all collected information
        
    Returns:
        Updated agent state with final response
    """
    user_message = state.get("user_message", "")
    context = state.get("context", {})
    collected_info = state.get("collected_info", {})
    
    # Build a summary of collected information
    info_summary = []
    if collected_info.get("flight_result"):
        info_summary.append("Flight information has been gathered.")
    if collected_info.get("hotel_result"):
        info_summary.append("Hotel information has been gathered.")
    if collected_info.get("visa_result"):
        info_summary.append("Visa requirement information has been gathered.")
    if collected_info.get("tripadvisor_result"):
        info_summary.append("TripAdvisor location/review information has been gathered.")
    
    # Also check context for results
    if context.get("flight_result"):
        collected_info["flight_result"] = context.get("flight_result")
        info_summary.append("Flight information has been gathered.")
    if context.get("hotel_result"):
        collected_info["hotel_result"] = context.get("hotel_result")
        info_summary.append("Hotel information has been gathered.")
    if context.get("visa_result"):
        collected_info["visa_result"] = context.get("visa_result")
        info_summary.append("Visa requirement information has been gathered.")
    if context.get("tripadvisor_result"):
        collected_info["tripadvisor_result"] = context.get("tripadvisor_result")
        info_summary.append("TripAdvisor location/review information has been gathered.")
    
    # Prepare messages for LLM
    messages = [
        {"role": "system", "content": get_conversational_agent_prompt()},
        {
            "role": "user", 
            "content": f"""User's original message: {user_message}

Collected information from agents:
{chr(10).join(info_summary) if info_summary else "No specialized agent information was collected."}

Please provide a comprehensive, friendly response to the user's query using all available information. 
If you have specific data from agents (like flight prices, hotel rates, visa requirements, or location details), 
include that information in a clear and organized way."""
        }
    ]
    
    # Add collected info details if available
    if collected_info:
        import json
        messages.append({
            "role": "user",
            "content": f"Detailed collected information:\n{json.dumps(collected_info, indent=2)}"
        })
    
    # Call LLM to generate response
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        temperature=0.7
    )
    
    message = response.choices[0].message
    final_response = message.content or "I apologize, but I couldn't generate a response. Please try again."
    
    updated_state = state.copy()
    updated_state["last_response"] = final_response
    updated_state["route"] = "end"  # End the workflow
    
    return updated_state

