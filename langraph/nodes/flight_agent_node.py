"""Flight Agent node for LangGraph orchestration."""

import sys
import os
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


def get_flight_agent_prompt() -> str:
    """Get the system prompt for the Flight Agent."""
    return """You are the Flight Agent, a specialized agent that helps users search for flights.

Your role:
- Understand user queries about flight searches
- Extract flight search parameters from user messages:
  - trip_type: "one-way" or "round-trip"
  - departure: Departure airport/city code (e.g., "JFK", "NYC", "LAX")
  - arrival: Arrival airport/city code (e.g., "LAX", "LHR", "CDG")
  - departure_date: Departure date in YYYY-MM-DD format
  - arrival_date: Return date for round-trip (if applicable)
  - Optional filters: airline, max_price, direct_only, travel_class, etc.
- Use the appropriate flight search tool
- Provide clear, helpful responses about flight options

Available tools:
- agent_get_flights: Search for flights with specific dates
  - Use for exact date searches
  - Supports one-way and round-trip
  - Extensive filtering options available
  
- agent_get_flights_flexible: Search for flights with flexible dates (±days_flex)
  - Use when user wants to find cheaper flights by adjusting dates
  - Searches multiple dates around the specified date
  - Perfect for "flexible dates" or "cheapest around this date" queries

When a user asks about flights, extract the parameters from their message and use the appropriate tool.
If the user mentions flexible dates or wants to find the cheapest option, use agent_get_flights_flexible.
If any information is missing, ask the user for clarification.

Provide friendly, clear responses about flight options based on the tool results."""


async def flight_agent_node(state: AgentState) -> AgentState:
    """Flight Agent node that handles flight search queries.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with response
    """
    user_message = state.get("user_message", "")
    context = state.get("context", {})
    
    # Check if we have task context from delegation
    task_args = context.get("args", {})
    
    # Get tools available to flight agent
    tools = await FlightAgentClient.list_tools()
    
    # Prepare messages for LLM
    messages = [
        {"role": "system", "content": get_flight_agent_prompt()},
        {"role": "user", "content": user_message}
    ]
    
    # Build function calling schema for flight tools
    functions = []
    for tool in tools:
        if tool["name"] in ["agent_get_flights", "agent_get_flights_flexible"]:
            functions.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", f"Search for flights"),
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
        tool_name = tool_call.function.name
        
        if tool_name in ["agent_get_flights", "agent_get_flights_flexible"]:
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
                    if tool_name == "agent_get_flights_flexible":
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
                
                updated_state["last_response"] = response_text
                updated_state["route"] = "main_agent"  # Return to main agent
                
            except Exception as e:
                updated_state["last_response"] = f"I encountered an error while searching for flights: {str(e)}"
                updated_state["route"] = "main_agent"
            
            return updated_state
    
    # No tool call - respond directly
    assistant_message = message.content or "I can help you search for flights. Please provide departure and arrival airports, dates, and any preferences (e.g., direct flights, travel class)."
    updated_state["route"] = "main_agent"
    updated_state["last_response"] = assistant_message
    
    return updated_state

