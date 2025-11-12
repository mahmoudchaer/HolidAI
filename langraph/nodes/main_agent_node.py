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


def get_main_agent_prompt(agents_called: list, collected_info: dict) -> str:
    """Get the system prompt for the Main Agent."""
    base_prompt = """You are the Main Agent, an orchestrator that coordinates specialized agents to help users with travel tasks.

Your role:
- Understand user requests and determine which specialized agents are needed
- Delegate tasks to specialized agents when appropriate
- After agents return, review the collected information and decide if more agents are needed
- Once you have all necessary information, route to "conversational_agent" to generate the final response
- Extract structured parameters from user messages for delegated tasks

Available specialized agents:
- hotel_agent: Handles hotel searches. Use task "get_hotel_rates" for hotel rate searches.
- visa_agent: Handles visa requirement checks. Use task "get_traveldoc_requirement" for visa requirement lookups.
- flight_agent: Handles flight searches. Use task "agent_get_flights" or "agent_get_flights_flexible" for flight searches.
- tripadvisor_agent: Handles location searches, reviews, and attractions. Use these specific tasks:
  * "get_top_rated_locations" - For finding top-rated/good restaurants or attractions (use when user asks for "good", "best", "top" places)
  * "search_locations_by_rating" - For searching locations filtered by minimum rating
  * "search_locations" - For general location/restaurant searches
  * "get_location_details" - For getting detailed information about a specific location
  * "get_location_reviews" - For getting reviews of a location

The delegate tool takes:
- agent: "hotel_agent", "visa_agent", "flight_agent", or "tripadvisor_agent"
- task: The specific task name for that agent
- args: Dictionary with the extracted parameters

For hotel searches, extract:
- checkin: Check-in date in YYYY-MM-DD format (e.g., "2025-12-10")
- checkout: Check-out date in YYYY-MM-DD format (e.g., "2025-12-17")
- occupancies: Array of occupancy objects, each with "adults" (integer) and optionally "children" (array of integers)
- city_name: City name (optional, must be paired with country_code)
- country_code: Country code in ISO 2-letter format (optional, must be paired with city_name)
- hotel_ids: Array of hotel IDs (optional)
- iata_code: IATA code (optional)

For visa requirements, extract:
- nationality: The traveler's nationality/passport country (e.g., "Lebanon", "United States")
- leaving_from: The origin country (e.g., "Lebanon", "United States")
- going_to: The destination country (e.g., "Qatar", "France")

For flight searches, extract:
- trip_type: "one-way" or "round-trip"
- departure: Departure airport/city code (e.g., "JFK", "NYC", "LAX")
- arrival: Arrival airport/city code (e.g., "LAX", "LHR", "CDG")
- departure_date: Departure date in YYYY-MM-DD format
- arrival_date: Return date for round-trip (if applicable)
- Optional: airline, max_price, direct_only, travel_class, adults, children, infants, etc.
- If user mentions flexible dates or wants cheapest options, use task "agent_get_flights_flexible"

For TripAdvisor searches:
- For "good", "best", or "top" restaurants/attractions: Use task "get_top_rated_locations"
  * Extract: search_query (e.g., "restaurants in Beirut"), k (number of top results, default 5), category (optional: "restaurants", "attractions", "hotels", "geos"), min_rating (optional, e.g., 4.0 for 4+ stars), location (optional, city name)
- For general restaurant/attraction searches: Use task "search_locations"
  * Extract: search_query (required), category (optional: "restaurants", "attractions", "hotels", "geos"), location (optional, city name)
- For location details: Use task "get_location_details"
  * Extract: location_id (required)
- For reviews: Use task "get_location_reviews"
  * Extract: location_id (required)

IMPORTANT: After agents return with information, you must:
1. Review what information you have collected
2. Determine if the user's query is fully answered
3. If you already have results from an agent (e.g., tripadvisor_result, hotel_result), DO NOT delegate to that same agent again - route to conversational_agent instead
4. If more information is needed from a different agent, delegate to that agent
5. If you have all necessary information, route to "conversational_agent" (use route_to_conversational tool)
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
    """Main Agent node that reasons and delegates tasks.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with route and context
    """
    user_message = state.get("user_message", "")
    context = state.get("context", {})
    collected_info = state.get("collected_info", {})
    agents_called = state.get("agents_called", [])
    
    # Ensure agents_called is a list
    if not isinstance(agents_called, list):
        agents_called = []
    
    # If we just received information from an agent, accumulate it
    if context.get("delegation_result") or context.get("flight_result") or context.get("hotel_result") or context.get("visa_result") or context.get("tripadvisor_result"):
        # Accumulate results from agents
        if context.get("flight_result"):
            collected_info["flight_result"] = context.get("flight_result")
        if context.get("hotel_result"):
            collected_info["hotel_result"] = context.get("hotel_result")
        if context.get("visa_result"):
            collected_info["visa_result"] = context.get("visa_result")
        if context.get("tripadvisor_result"):
            collected_info["tripadvisor_result"] = context.get("tripadvisor_result")
    
    # Ensure collected_info is initialized
    if not collected_info:
        collected_info = {}
    
    # If we have visa_result and user asked about visas, automatically route to conversational agent
    if collected_info.get("visa_result") and not collected_info.get("visa_result", {}).get("error"):
        # Check if user message is about visas
        visa_keywords = ["visa", "travel document", "entry requirement", "passport requirement"]
        if any(keyword in user_message.lower() for keyword in visa_keywords):
            updated_state = state.copy()
            updated_state["collected_info"] = collected_info
            updated_state["route"] = "conversational_agent"
            updated_state["ready_for_response"] = True
            return updated_state
    
    # Get tools available to main agent
    tools = await MainAgentClient.list_tools()
    
    # Build context message about what we know
    context_message = user_message
    if collected_info or agents_called:
        context_message += "\n\nContext: "
        if agents_called:
            context_message += f"Agents called: {', '.join(agents_called)}. "
        if collected_info:
            context_message += "Information has been collected from agents: "
            if collected_info.get("tripadvisor_result"):
                context_message += "TripAdvisor results available. "
            if collected_info.get("hotel_result"):
                context_message += "Hotel results available. "
            if collected_info.get("flight_result"):
                context_message += "Flight results available. "
            if collected_info.get("visa_result"):
                context_message += "Visa results available with actual visa requirement data. "
        context_message += "\n\nIMPORTANT: If you have results from agents (visa_result, flight_result, hotel_result, or tripadvisor_result), you MUST route to conversational_agent immediately using the route_to_conversational tool. DO NOT delegate the same task again if results already exist."
    
    # Prepare messages for LLM
    messages = [
        {"role": "system", "content": get_main_agent_prompt(agents_called, collected_info)},
        {"role": "user", "content": context_message}
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
    
    # Add a special "route_to_conversational" function to help the LLM decide
    functions.append({
        "type": "function",
        "function": {
            "name": "route_to_conversational",
            "description": "Route to conversational agent when you have all necessary information to generate the final response",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    })
    
    # Call LLM with function calling
    if functions:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            tools=functions,
            tool_choice="auto"
        )
    else:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages
        )
    
    message = response.choices[0].message
    updated_state = state.copy()
    updated_state["collected_info"] = collected_info
    
    # Check if LLM wants to call a tool
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        
        if tool_call.function.name == "route_to_conversational":
            # Route to conversational agent
            updated_state["route"] = "conversational_agent"
            updated_state["ready_for_response"] = True
            return updated_state
        
        elif tool_call.function.name == "delegate":
            import json
            args = json.loads(tool_call.function.arguments)
            agent_name = args["agent"]
            task_name = args["task"]
            
            # Check if we already have results for this agent/task combination
            # This prevents infinite loops where we keep delegating the same task
            if agent_name == "tripadvisor_agent" and collected_info.get("tripadvisor_result"):
                # We already have tripadvisor results, route to conversational agent instead
                updated_state["route"] = "conversational_agent"
                updated_state["ready_for_response"] = True
                return updated_state
            elif agent_name == "hotel_agent" and collected_info.get("hotel_result"):
                # We already have hotel results, route to conversational agent instead
                updated_state["route"] = "conversational_agent"
                updated_state["ready_for_response"] = True
                return updated_state
            elif agent_name == "flight_agent" and collected_info.get("flight_result"):
                # We already have flight results, route to conversational agent instead
                updated_state["route"] = "conversational_agent"
                updated_state["ready_for_response"] = True
                return updated_state
            elif agent_name == "visa_agent" and collected_info.get("visa_result"):
                # We already have visa results, route to conversational agent instead
                updated_state["route"] = "conversational_agent"
                updated_state["ready_for_response"] = True
                return updated_state
            
            # Track which agent we're calling
            if agent_name not in agents_called:
                agents_called = agents_called + [agent_name]
            
            # Call the delegate tool via MCP
            delegation_result = await MainAgentClient.invoke(
                "delegate",
                agent=agent_name,
                task=task_name,
                args=args.get("args", {})
            )
            
            # Update state to route to the specified agent
            updated_state["route"] = agent_name
            updated_state["agents_called"] = agents_called
            updated_state["context"] = {
                "task": task_name,
                "args": args.get("args", {}),
                "delegation_result": delegation_result
            }
            
            return updated_state
    
    # No tool call - check if LLM content suggests routing
    assistant_message = message.content or ""
    
    # Simple heuristic: if LLM says we're done or ready, route to conversational
    if any(phrase in assistant_message.lower() for phrase in ["ready", "complete", "all information", "have enough", "can now respond"]):
        updated_state["route"] = "conversational_agent"
        updated_state["ready_for_response"] = True
    else:
        # For general questions without delegation, route to conversational agent
        updated_state["route"] = "conversational_agent"
        updated_state["ready_for_response"] = True
        updated_state["last_response"] = assistant_message
    
    return updated_state

