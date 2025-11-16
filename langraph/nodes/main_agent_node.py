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


def get_main_agent_prompt() -> str:
    """Get the system prompt for the Main Agent."""
    return """You are the Main Agent, an orchestrator that creates multi-step execution plans for specialized travel agents.

Your role:
- Analyze user requests and create a sequential execution plan
- CRITICAL: Identify dependencies - if one task needs results from another, they MUST be in separate steps
- Group only truly independent agents in the same step (they'll run in parallel)
- Place dependent agents in later steps

Available specialized agents:
- flight_agent: For flight searches (one-way, round-trip, flexible dates, etc.)
- hotel_agent: For hotel searches (by location, price, dates, etc.)
- visa_agent: For visa requirement checks
- tripadvisor_agent: For location searches, restaurants, attractions, reviews, etc.
- utilities_agent: For utility functions including:
  * get_holidays: Get holidays for a country (to avoid booking on holidays)
  * Weather, currency conversion, date/time
  * eSIM bundles for mobile data

CRITICAL DEPENDENCY RULES:
1. HOLIDAYS affect booking → must be fetched BEFORE flight/hotel booking
2. eSIM, weather, currency DON'T depend on booking → can run in parallel with booking
3. utilities_agent can execute MULTIPLE tools in one call (e.g., holidays + eSIM together)
4. Minimize steps by grouping truly independent tasks

TRUE DEPENDENCIES (must be sequential):
- Holidays → Flights/Hotels (if user wants to avoid holidays)
- City search → Flights/Hotels (if booking depends on finding city)
- eSIM prices → Currency conversion (conversion needs prices)
- Flights/Hotels results → Currency conversion (if converting booking prices)

INDEPENDENT TASKS (can run in parallel):
- eSIM bundles are independent of flights/hotels/holidays
- Weather is independent of everything
- Getting holidays + getting eSIM = both can happen in same utilities_agent call!

OPTIMIZATION STRATEGY:
- If ONLY holidays needed: utilities_agent can get holidays + eSIM in SAME step
- After holidays known: flights, hotels, AND more utilities (weather) can all run parallel
- Only currency conversion needs to wait (needs prices from previous steps)

Example 1 - Simple independent (1 step):
User: "Find flights and hotels to Paris"
Plan: Step 1: [flight_agent, hotel_agent]

Example 2 - Optimized with holidays (3 steps NOT 4!):
User: "Book flight/hotel avoiding holidays, get eSIM, convert to AED"
Plan:
  Step 1: [utilities_agent] - get holidays AND eSIM bundles (2 tools, 1 step!)
  Step 2: [flight_agent, hotel_agent] - book avoiding holidays
  Step 3: [utilities_agent] - convert eSIM prices to AED

Example 3 - Maximum parallelization (3 steps):
User: "Avoid holidays, book flights/hotels, get eSIM and weather, convert to AED"
Plan:
  Step 1: [utilities_agent] - get holidays
  Step 2: [flight_agent, hotel_agent, utilities_agent] - book + eSIM/weather (all parallel!)
  Step 3: [utilities_agent] - convert prices to AED

Respond with a JSON object containing the execution plan."""


async def main_agent_node(state: AgentState) -> AgentState:
    """Main Agent node that creates a multi-step execution plan.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with execution plan
    """
    user_message = state.get("user_message", "")
    
    # Prepare messages for LLM to create execution plan
    messages = [
        {"role": "system", "content": get_main_agent_prompt()},
        {"role": "user", "content": f"""Analyze the user's request and create a multi-step execution plan.

User's message: {user_message}

Create a plan with steps. Each step should contain agents that can run in parallel.
If agents have dependencies (one needs results from another), place them in separate steps.

Respond with a JSON object in this format:
{{
  "execution_plan": [
    {{
      "step_number": 1,
      "agents": ["agent1", "agent2"],
      "description": "What this step does"
    }},
    {{
      "step_number": 2,
      "agents": ["agent3"],
      "description": "What this step does (may use results from step 1)"
    }}
  ]
}}

Available agent names: flight_agent, hotel_agent, visa_agent, tripadvisor_agent, utilities_agent

If no agents are needed, return an empty execution_plan array."""}
    ]
    
    # Call LLM to create execution plan
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )
    
    message = response.choices[0].message
    import json
    
    # Extract JSON from the LLM response
    content = message.content or ""
    
    # Parse the execution plan
    try:
        # Find JSON in response
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
                plan_data = json.loads(json_str)
            else:
                plan_data = json.loads(content)
        else:
            plan_data = json.loads(content)
    except Exception as e:
        print(f"Warning: Could not parse LLM response as JSON: {e}")
        print(f"LLM response content: {content[:500]}")
        plan_data = {"execution_plan": []}
    
    execution_plan = plan_data.get("execution_plan", [])
    
    # Log the execution plan
    print("\n=== Main Agent: Created Execution Plan ===")
    if not execution_plan:
        print("No agents needed for this request")
    else:
        for step in execution_plan:
            step_num = step.get("step_number", 0)
            agents = step.get("agents", [])
            description = step.get("description", "")
            print(f"Step {step_num}: {agents} - {description}")
    print("=========================================\n")
    
    # Set needs flags based on all agents in the plan
    all_agents = []
    for step in execution_plan:
        all_agents.extend(step.get("agents", []))
    
    updated_state = {
        "execution_plan": execution_plan,
        "current_step": 0,
        "needs_flights": "flight_agent" in all_agents,
        "needs_hotels": "hotel_agent" in all_agents,
        "needs_visa": "visa_agent" in all_agents,
        "needs_tripadvisor": "tripadvisor_agent" in all_agents,
        "needs_utilities": "utilities_agent" in all_agents,
    }
    
    # Clear results for agents not in plan
    if "flight_agent" not in all_agents:
        updated_state["flight_result"] = None
    if "hotel_agent" not in all_agents:
        updated_state["hotel_result"] = None
    if "visa_agent" not in all_agents:
        updated_state["visa_result"] = None
    if "tripadvisor_agent" not in all_agents:
        updated_state["tripadvisor_result"] = None
    if "utilities_agent" not in all_agents:
        updated_state["utilities_result"] = None
    
    # If no agents needed, route directly to conversational
    if not execution_plan:
        updated_state["route"] = "conversational_agent"
        updated_state["ready_for_response"] = True
    else:
        # Route to plan executor to start executing the plan
        updated_state["route"] = "plan_executor"
    
    return updated_state

