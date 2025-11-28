"""Main Agent node for LangGraph orchestration."""

import sys
import os
import time
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from agent_logger import log_llm_call

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
- Analyze user requests and create a sequential execution plan using LLM REASONING
- CRITICAL: You ONLY work with TRAVEL-RELATED queries (flights, hotels, visa, restaurants, weather, currency, eSIM, holidays, date/time)
- CRITICAL: If the user message contains non-travel parts, IGNORE them completely - only process travel-related parts
- CRITICAL: Use LLM REASONING to check if data already exists in state/memory before creating execution plans
- CRITICAL: If data already exists that fulfills the user's request, DO NOT include agents in the plan - return empty execution_plan
- CRITICAL: Identify dependencies - if one task needs results from another, they MUST be in separate steps
- Group only truly independent agents in the same step (they'll run in parallel)
- Place dependent agents in later steps

IMPORTANT: This is a TRAVEL ASSISTANT ONLY. Do NOT create plans for:
- General knowledge questions (science, history, math, sports, etc.)
- Non-travel topics
- If you see non-travel content in the user message, completely ignore it and only process travel parts

Available specialized agents:
- flight_agent: For flight searches (one-way, round-trip, flexible dates, etc.)
- hotel_agent: For hotel searches (by location, price, dates, etc.)
- visa_agent: For visa requirement checks
- tripadvisor_agent: For location searches, restaurants, attractions, reviews, photos, etc. **CRITICAL: Use tripadvisor_agent when user asks for restaurants, food, dining, attractions, things to do, places to visit, or photos of locations**
- utilities_agent: For utility functions including:
  * get_holidays: Get holidays for a country (to avoid booking on holidays)
  * Weather, currency conversion, date/time
  * eSIM bundles for mobile data

IMPORTANT ARCHITECTURE NOTE:
- Plan management (adding/updating/deleting items to user's travel plan) is handled AUTOMATICALLY at the end of the workflow by the final_planner_agent.
- You should NEVER include planner_agent in execution plans.
- If the user asks to "add to plan", "save", etc., just proceed with normal search/query agents. The final planner will handle the plan update automatically.

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

Example 1b - Restaurants (1 step):
User: "Get me restaurants in Paris with photos"
Plan: Step 1: [tripadvisor_agent]

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

Respond with a JSON object containing the execution plan.

NOTE: If you find placeholders like <NAME_1>, <EMAIL_1>, etc. in the user's message, this is due to the PII redaction node and is expected behavior."""


async def main_agent_node(state: AgentState) -> AgentState:
    """Main Agent node that creates a multi-step execution plan.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with execution plan
    """
    user_message = state.get("user_message", "")
    feedback_message = state.get("feedback_message")
    
    # Get memory/STM context for LLM reasoning
    relevant_memories = state.get("relevant_memories", [])
    stm_context = state.get("stm_context", "")  # Short-term memory context from memory_agent
    
    # Check what data already exists in state
    collected_info = state.get("collected_info", {})
    flight_result = collected_info.get("flight_result") or state.get("flight_result")
    hotel_result = collected_info.get("hotel_result") or state.get("hotel_result")
    visa_result = collected_info.get("visa_result") or state.get("visa_result")
    tripadvisor_result = collected_info.get("tripadvisor_result") or state.get("tripadvisor_result")
    utilities_result = collected_info.get("utilities_result") or state.get("utilities_result")
    
    # Build context about existing data
    existing_data_context = {
        "has_flight_data": bool(flight_result and not flight_result.get("error")),
        "has_hotel_data": bool(hotel_result and not hotel_result.get("error")),
        "has_visa_data": bool(visa_result and not visa_result.get("error")),
        "has_tripadvisor_data": bool(tripadvisor_result and not tripadvisor_result.get("error")),
        "has_utilities_data": bool(utilities_result and not utilities_result.get("error")),
    }
    
    # Log the message being used (may be enriched by RFI)
    print(f"[MAIN AGENT] Processing user message: '{user_message}'")
    print(f"[MAIN AGENT] Existing data: {existing_data_context}")
    
    # Build summary of existing flight/hotel data for LLM reasoning
    flight_summary = ""
    if flight_result and not flight_result.get("error"):
        outbound = flight_result.get("outbound", [])
        returns = flight_result.get("return", [])
        flight_summary = f"Flight data exists: {len(outbound)} outbound, {len(returns)} return flights available."
        if outbound:
            first = outbound[0]
            dep = first.get("departure_airport", {}).get("id", "?")
            arr = first.get("arrival_airport", {}).get("id", "?")
            date = first.get("departure_airport", {}).get("time", "?")
            flight_summary += f" Example: {dep}→{arr} on {date}."
    
    hotel_summary = ""
    if hotel_result and not hotel_result.get("error"):
        hotels = hotel_result.get("hotels", [])
        hotel_summary = f"Hotel data exists: {len(hotels)} hotels available."
    
    # Build user prompt with optional feedback
    user_prompt = f"""Analyze the user's request and create a multi-step execution plan.

User's message: {user_message}

MEMORY CONTEXT (from previous conversation):
{stm_context if stm_context else "No recent conversation context available."}

RELEVANT MEMORIES:
{chr(10).join([f"- {mem}" for mem in relevant_memories]) if relevant_memories else "No relevant memories."}

EXISTING DATA IN STATE (DO NOT RE-FETCH IF ALREADY AVAILABLE):
- Flight data: {"AVAILABLE" if existing_data_context["has_flight_data"] else "NOT AVAILABLE"}
  {flight_summary if flight_summary else ""}
- Hotel data: {"AVAILABLE" if existing_data_context["has_hotel_data"] else "NOT AVAILABLE"}
  {hotel_summary if hotel_summary else ""}
- Visa data: {"AVAILABLE" if existing_data_context["has_visa_data"] else "NOT AVAILABLE"}
- Tripadvisor data: {"AVAILABLE" if existing_data_context["has_tripadvisor_data"] else "NOT AVAILABLE"}
- Utilities data: {"AVAILABLE" if existing_data_context["has_utilities_data"] else "NOT AVAILABLE"}

CRITICAL REASONING RULES:
1. Use LLM reasoning to determine if the user's request can be fulfilled with EXISTING data in state/memory.
2. If the user asks for something that was ALREADY shown in this conversation (check STM context), DO NOT call agents again.
3. If the user asks to "add to plan" and the data already exists, DO NOT re-fetch - just proceed to conversational_agent.
4. Only call agents if:
   - The data is NOT available in state
   - The user is asking for NEW/Different data (different dates, locations, etc.)
   - The user explicitly wants to search again

Example reasoning:
- User: "add the flydubai flight to my plan" + Flight data exists → NO agent call needed, data already available
- User: "find flights to Paris" + No flight data → Call flight_agent
- User: "show me hotels in Dubai" + Hotel data exists for Dubai → NO agent call needed
- User: "find hotels in Paris" + Hotel data exists for Dubai (different city) → Call hotel_agent"""
    
    # If there's feedback from the feedback node, include it
    if feedback_message:
        user_prompt += f"""

FEEDBACK FROM VALIDATOR:
{feedback_message}

Please revise the execution plan based on this feedback."""
        print(f"Main Agent: Received feedback - {feedback_message}")
    
    user_prompt += """

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

IMPORTANT: 
- Do NOT include planner_agent in execution plans. Plan management is handled automatically at the end.
- If user asks to "add to plan" or "save", just proceed with normal agents (flight_agent, hotel_agent, etc.) to get the data.
- The final_planner_agent will automatically handle adding items to the plan based on user intent.
- **CRITICAL**: Check the "EXISTING DATA IN STATE" section above. If data is already available, DO NOT include that agent in the plan. Only fetch data that is missing.

If no agents are needed (all data already exists or no new data needed), return an empty execution_plan array."""
    
    # Prepare messages for LLM to create execution plan
    messages = [
        {"role": "system", "content": get_main_agent_prompt()},
        {"role": "user", "content": user_prompt}
    ]
    
    # Call LLM to create execution plan
    session_id = state.get("session_id", "unknown")
    user_email = state.get("user_email")
    llm_start_time = time.time()
    
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
        agent_name="main_agent",
        model="gpt-4.1",
        prompt_preview=prompt_preview,
        response_preview=response_preview,
        token_usage=token_usage,
        latency_ms=llm_latency_ms
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
    user_msg_lower = user_message.lower()

    # Heuristic guard: only keep tripadvisor agent when user explicitly asks
    tripadvisor_keywords = [
        "restaurant",
        "food",
        "dining",
        "eat",
        "cuisine",
        "attraction",
        "things to do",
        "places to visit",
        "places to go",
        "recommendation",
        "sightseeing",
        "activities",
        "nightlife",
        "coffee shop",
        "bar",
        "museum"
    ]
    wants_tripadvisor = any(keyword in user_msg_lower for keyword in tripadvisor_keywords)

    if execution_plan and not wants_tripadvisor:
        filtered_plan = []
        for step in execution_plan:
            agents = step.get("agents", [])
            filtered_agents = [agent for agent in agents if agent != "tripadvisor_agent"]
            if filtered_agents:
                new_step = step.copy()
                new_step["agents"] = filtered_agents
                filtered_plan.append(new_step)
        # Re-number steps to keep sequence consistent
        for idx, step in enumerate(filtered_plan, 1):
            step["step_number"] = idx
        execution_plan = filtered_plan
    
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
        # Route to feedback node for validation before execution
        updated_state["route"] = "feedback"
    
    return updated_state

