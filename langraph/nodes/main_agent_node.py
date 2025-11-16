"""Main Agent node for LangGraph orchestration with dynamic multi-step planning."""

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

# Load environment variables from .env file in main directory
# Get the project root directory (2 levels up from langraph/nodes/)
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_main_agent_prompt() -> str:
    """Get the system prompt for the Main Agent as a dynamic planner."""
    return """You are the Main Agent, an intelligent orchestrator that proactively creates and executes multi-step plans for travel tasks.

Your role:
1. CREATE INTELLIGENT PLANS: Automatically break down user requests into logical sequential steps with dependencies - BE PROACTIVE
2. EXECUTE STEPS: Launch worker nodes in parallel when their dependencies are satisfied
3. ADAPT: Modify plans dynamically based on results (e.g., weather affects dates, flight availability affects hotels)
4. DECIDE: After each step, decide whether to continue, modify the plan, ask the user, or finish

CRITICAL: BE INTELLIGENT AND PROACTIVE
- If user mentions a destination and dates → AUTOMATICALLY check weather first (weather affects travel planning)
- If user wants to travel → AUTOMATICALLY check weather, then flights/hotels, then visa requirements
- If user mentions a country → AUTOMATICALLY check visa requirements if nationality is mentioned
- If user wants activities → AUTOMATICALLY get them after flights/hotels are confirmed
- You should create logical sequences WITHOUT the user explicitly telling you step-by-step what to do
- Think about what information is needed FIRST before other steps can proceed

Available worker nodes:
- utilities_agent: Weather, currency conversion, date/time, eSIM bundles
- flight_agent: Flight searches (one-way, round-trip, flexible dates)
- hotel_agent: Hotel searches (by location, price, dates)
- visa_agent: Visa requirement checks
- tripadvisor_agent: Location searches, restaurants, attractions, reviews

PLAN STRUCTURE:
Each step in your plan should be a JSON object with:
- "id": unique step number (integer)
- "nodes": list of node names to run in parallel for this step (e.g., ["utilities_agent"])
- "requires": list of result keys that must exist before this step can run (e.g., ["weather_data"])
- "produces": list of result keys this step will produce (e.g., ["weather_data", "good_dates"])

INTELLIGENT PLANNING EXAMPLES:

Example 1: User says "I want to travel to Paris next week"
→ Step 1: Check weather for Paris (utilities_agent) - produces: weather_data
→ Step 2: Get flights and hotels (flight_agent, hotel_agent) - requires: weather_data, produces: flight_options, hotel_options
→ Step 3: Check visa if nationality mentioned (visa_agent) - requires: flight_options
→ Step 4: Get activities (tripadvisor_agent) - requires: flight_options, hotel_options

Example 2: User says "Find me flights to Dubai"
→ Step 1: Get flights (flight_agent) - produces: flight_options
→ Step 2: Get hotels (hotel_agent) - requires: flight_options, produces: hotel_options
→ Step 3: Check visa if nationality mentioned (visa_agent) - requires: flight_options

Example 3: User says "What's the weather in Tokyo?"
→ Step 1: Get weather (utilities_agent) - produces: weather_data

DYNAMIC REASONING:
- If weather shows rain all week → modify plan to suggest different dates or ask user
- If flights unavailable → adjust dates or ask user for alternatives
- If results indicate missing info → add new steps or ask user clarifying questions

When responding:
- If creating/updating a plan: Return JSON with "action": "create_plan" or "update_plan" and "plan": [...]
- If asking user: Return JSON with "action": "ask_user" and "question": "..."
- If ready to finish: Return JSON with "action": "finish"
- If continuing: Return JSON with "action": "continue" and "next_step": step_id
"""


def _extract_json_from_response(content: str) -> dict:
    """Extract JSON from LLM response, handling various formats."""
    try:
        # Try to find JSON in the response
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
                return json.loads(json_str)
                # Try parsing the whole content as JSON
        return json.loads(content)
    except Exception as e:
        print(f"Warning: Could not parse LLM response as JSON: {e}")
        print(f"LLM response content: {content[:500]}")
        return {}


def _check_requirements_satisfied(state: AgentState, requires: list) -> bool:
    """Check if all required result keys exist in state.results."""
    results = state.get("results", {})
    for req in requires:
        if req not in results or results[req] is None:
            return False
    return True


def _generate_plan(state: AgentState) -> tuple:
    """Use LLM to generate an intelligent, proactive execution plan.
    
    Returns:
        tuple: (plan_list, question_or_none) - If question is not None, ask user first
    """
    user_message = state.get("user_message", "").strip()
    
    # Check if this is just a greeting or simple query that doesn't need a plan
    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "greetings", "hi!", "hello!", "hey!"]
    user_lower = user_message.lower().strip()
    
    # If it's just a greeting or very short non-travel query, return empty plan
    if user_lower in greetings or (len(user_message.split()) <= 2 and not any(word in user_lower for word in ["flight", "hotel", "travel", "trip", "visa", "weather", "destination", "book", "search"])):
        print("Main agent: Simple greeting or query detected, no plan needed")
        return ([], None)  # Empty plan means route to conversational agent
    
    messages = [
        {"role": "system", "content": get_main_agent_prompt()},
        {"role": "user", "content": f"""Analyze this user request and create an intelligent execution plan.

User's message: {user_message}

CRITICAL: Use your LLM reasoning to check if critical information is missing:
- Read and understand the user's message completely
- If user asks for hotels/flights but NO LOCATION/DESTINATION is mentioned → Return {{"action": "ask_user", "question": "Which city or destination are you interested in?"}}
- If user asks for weather but NO LOCATION is mentioned → Return {{"action": "ask_user", "question": "Which city would you like to check the weather for?"}}
- If user asks for visa but NO NATIONALITY or DESTINATION → Return {{"action": "ask_user", "question": "What is your nationality and which country are you traveling to?"}}
- Use your understanding of the message - do NOT use regex or pattern matching, use LLM reasoning

If all critical information is present, create a plan:
{{
  "action": "create_plan",
  "plan": [...]
}}

If information is missing, ask:
{{
  "action": "ask_user",
  "question": "..."
}}

Remember: Worker nodes will extract ALL parameters from the user message using LLM reasoning. You just need to check if the basic information (location, dates) is present in the message.

BE INTELLIGENT AND PROACTIVE:
- Analyze what the user wants to accomplish
- Think about what information is needed FIRST (e.g., weather for travel destinations with dates)
- Create logical sequences automatically - don't wait for explicit step-by-step instructions
- Consider dependencies: weather affects travel dates, flights affect hotels, destination affects visa

INTELLIGENT PLANNING RULES:
1. If user mentions travel to a destination with dates → ALWAYS check weather first (Step 1)
2. If user wants flights/hotels → Get weather first if dates mentioned, then flights/hotels in parallel
3. If user mentions nationality and destination → Check visa requirements
4. If user wants activities/restaurants → Get them after flights/hotels are found
5. If user only asks about weather → Just get weather (single step)
6. If user only asks about flights → Get flights, then hotels (logical sequence)

IMPORTANT ABOUT WORKER NODES:
- Worker nodes (utilities_agent, flight_agent, hotel_agent, etc.) receive the FULL user_message
- They use LLM reasoning to extract ALL parameters from the user message (location, dates, preferences, etc.)
- You do NOT need to extract or pass parameters - just create the plan
- The worker nodes will intelligently understand the user's message and extract what they need
- DO NOT create steps that produce fake result keys like "non_rainy_dates" - use real result keys like "weather_data", "flight_options", "hotel_options"

VALID RESULT KEYS:
- "weather_data" (from utilities_agent)
- "flight_options" or "flight_result" (from flight_agent)
- "hotel_options" or "hotel_result" (from hotel_agent)
- "visa_info" or "visa_result" (from visa_agent)
- "activities" or "tripadvisor_result" (from tripadvisor_agent)

Create a plan that makes sense logically. Be proactive - the user doesn't need to tell you "check weather first".

Return a JSON object with:
{{
  "action": "create_plan",
  "plan": [
    {{"id": 1, "nodes": ["utilities_agent"], "requires": [], "produces": ["weather_data"]}},
    {{"id": 2, "nodes": ["flight_agent", "hotel_agent"], "requires": ["weather_data"], "produces": ["flight_options", "hotel_options"]}},
    ...
  ]
}}

Make sure the plan is intelligent and logical based on the user's request. Use only valid result keys."""}
    ]
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3  # Lower temperature for more consistent, logical planning
    )
    
    content = response.choices[0].message.content or ""
    result = _extract_json_from_response(content)
    
    # Check if we need to ask the user first
    if result.get("action") == "ask_user":
        question = result.get("question", "I need more information to proceed.")
        print(f"Main agent: Need to ask user: {question}")
        return ([], question)
    
    if result.get("action") == "create_plan" and "plan" in result:
        plan = result["plan"]
        print(f"Main agent: Generated intelligent plan with {len(plan)} steps")
        for step in plan:
            print(f"  Step {step.get('id')}: {step.get('nodes')} (requires: {step.get('requires')}, produces: {step.get('produces')})")
        return (plan, None)
    
    # Fallback: intelligent heuristic-based plan
    print("Warning: LLM did not return valid plan, using intelligent fallback")
    plan = []
    node_id = 1
    user_lower = user_message.lower()
    
    # Intelligent heuristics for proactive planning
    has_destination = any(word in user_lower for word in ["to ", "in ", "visit", "travel", "trip", "go to", "going to"])
    has_dates = any(word in user_lower for word in ["next week", "this week", "tomorrow", "today", "in ", "on ", "date", "when"])
    has_weather_query = any(word in user_lower for word in ["weather", "rain", "temperature", "climate", "forecast"])
    has_flight_query = any(word in user_lower for word in ["flight", "fly", "airline", "ticket", "airfare"])
    has_hotel_query = any(word in user_lower for word in ["hotel", "accommodation", "stay", "room", "lodging"])
    has_visa_query = any(word in user_lower for word in ["visa", "visa requirement", "entry requirement", "passport"])
    has_activity_query = any(word in user_lower for word in ["restaurant", "attraction", "activity", "thing to do", "places to visit", "what to see"])
    
    # Rule 1: If user asks about weather only, just get weather
    if has_weather_query and not (has_flight_query or has_hotel_query):
        plan.append({
            "id": node_id,
            "nodes": ["utilities_agent"],
            "requires": [],
            "produces": ["weather_data"]
        })
        return plan
    
    # Rule 2: If user mentions travel with destination and dates, check weather first
    if has_destination and has_dates and (has_flight_query or has_hotel_query):
        plan.append({
            "id": node_id,
            "nodes": ["utilities_agent"],
            "requires": [],
            "produces": ["weather_data"]
        })
        node_id += 1
    
    # Rule 3: Get flights and hotels (can run in parallel after weather if needed)
    parallel_nodes = []
    if has_flight_query:
        parallel_nodes.append("flight_agent")
    if has_hotel_query:
        parallel_nodes.append("hotel_agent")
    
    if parallel_nodes:
        requires = ["weather_data"] if node_id > 1 else []
        produces = [f"{node.replace('_agent', '')}_options" for node in parallel_nodes]
        plan.append({
            "id": node_id,
            "nodes": parallel_nodes,
            "requires": requires,
            "produces": produces
        })
        node_id += 1
    
    # Rule 4: Check visa if mentioned or if we have destination
    if has_visa_query or (has_destination and any(word in user_lower for word in ["citizen", "nationality", "passport", "from"])):
        requires = ["flight_options"] if node_id > 1 else []
        plan.append({
            "id": node_id,
            "nodes": ["visa_agent"],
            "requires": requires,
            "produces": ["visa_info"]
        })
        node_id += 1
    
    # Rule 5: Get activities after flights/hotels
    if has_activity_query:
        requires = []
        if has_flight_query:
            requires.append("flight_options")
        if has_hotel_query:
            requires.append("hotel_options")
        if not requires:
            requires = ["weather_data"] if node_id > 1 else []
        
        plan.append({
            "id": node_id,
            "nodes": ["tripadvisor_agent"],
            "requires": requires,
            "produces": ["activities"]
        })
        node_id += 1
    
    # Rule 6: If only flights mentioned, still get hotels (logical sequence)
    if has_flight_query and not has_hotel_query and not plan:
        plan.append({
            "id": 1,
            "nodes": ["flight_agent"],
            "requires": [],
            "produces": ["flight_options"]
        })
        plan.append({
            "id": 2,
            "nodes": ["hotel_agent"],
            "requires": ["flight_options"],
            "produces": ["hotel_options"]
        })
    
    # Default: if nothing matches, just get utilities
    if not plan:
        plan = [{"id": 1, "nodes": ["utilities_agent"], "requires": [], "produces": ["utilities_result"]}]
    
    print(f"Main agent: Generated fallback plan with {len(plan)} steps")
    return (plan, None)


def _decide_next_action(state: AgentState) -> dict:
    """Use LLM to decide the next action after a step completes."""
    user_message = state.get("user_message", "")
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    results = state.get("results", {})
    finished_steps = state.get("finished_steps", [])
    
    # Build context about current state
    results_summary = {}
    for key, value in results.items():
        if isinstance(value, dict):
            if value.get("error"):
                results_summary[key] = f"Error: {value.get('error_message', 'Unknown error')}"
            else:
                results_summary[key] = "Success"
        else:
            results_summary[key] = str(value)[:100]  # Truncate long values
    
    messages = [
        {"role": "system", "content": get_main_agent_prompt()},
        {"role": "user", "content": f"""You are executing a multi-step plan. Intelligently decide what to do next.

User's original request: {user_message}

Current plan:
{json.dumps(plan, indent=2)}

Current step: {current_step}
Finished steps: {finished_steps}

Results so far:
{json.dumps(results_summary, indent=2)}

BE INTELLIGENT IN YOUR DECISION:
- If weather shows bad conditions (rain, storms) → consider modifying plan or asking user about alternative dates
- If flights are unavailable → consider adjusting dates or asking user for alternatives
- If results are good → continue to next step automatically
- Only ask user if absolutely necessary (missing critical info) or if results suggest alternatives
- Default to continuing the plan if results are satisfactory

Decide:
1. If plan needs modification based on results → "update_plan" with new plan
2. If we need user input (only if critical) → "ask_user" with question
3. If we should continue to next step (default) → "continue" with next_step
4. If we're done → "finish"

Return JSON:
{{
  "action": "continue|update_plan|ask_user|finish",
  "next_step": <step_id> (if action is continue),
  "plan": [...] (if action is update_plan),
  "question": "..." (if action is ask_user)
}}"""}
    ]
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )
    
    content = response.choices[0].message.content or ""
    result = _extract_json_from_response(content)
    
    # Default action if LLM response is invalid
    if "action" not in result:
        # Check if we have more steps
        if current_step < len(plan) - 1:
            result = {"action": "continue", "next_step": current_step + 1}
        else:
            result = {"action": "finish"}
    
    return result


async def main_agent_node(state: AgentState) -> AgentState:
    """Main Agent node that acts as a dynamic planner.
    
    This node:
    1. Creates or updates execution plans
    2. Launches worker nodes for the current step
    3. Decides next actions after steps complete
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with routing decision
    """
    updated_state = state.copy()
    
    # Initialize execution state if not present
    if "plan" not in state or not state.get("plan"):
        # First time: create a plan
        print("Main agent: Creating initial plan...")
        plan_result = _generate_plan(state)
        if isinstance(plan_result, tuple):
            plan, question = plan_result
        else:
            # Backward compatibility
            plan = plan_result
            question = None
        
        # If we need to ask the user, route to conversational agent
        if question:
            updated_state["user_questions"] = [question]
            updated_state["route"] = "conversational_agent"
            updated_state["ready_for_response"] = True
            print(f"Main agent: Need to ask user before proceeding: {question}")
            return updated_state
        
        updated_state["plan"] = plan
        updated_state["current_step"] = 0
        updated_state["results"] = {}
        updated_state["pending_nodes"] = []
        updated_state["finished_steps"] = []
        updated_state["user_questions"] = []
        print(f"Main agent: Created plan with {len(plan)} steps")
    
    plan = updated_state.get("plan", [])
    current_step = updated_state.get("current_step", 0)
    
    # Check if plan is empty (no steps needed, e.g., just a greeting)
    if not plan:
        updated_state["route"] = "conversational_agent"
        updated_state["ready_for_response"] = True
        print("Main agent: No plan needed, routing to conversational agent")
        return updated_state
    
    # Check if we're coming back from a completed step (pending_nodes should be empty)
    pending_nodes = updated_state.get("pending_nodes", [])
    finished_steps = updated_state.get("finished_steps", [])
    
    # If we just completed a step (pending_nodes is empty and current step is finished)
    if not pending_nodes and current_step < len(plan):
        current_step_obj = plan[current_step]
        step_id = current_step_obj.get("id")
        
        # If this step is already finished, we need to move to the next step
        if step_id in finished_steps:
            # Step was completed, decide next action
            print(f"Main agent: Step {step_id} (index {current_step}) completed, deciding next action...")
            action = _decide_next_action(updated_state)
            
            if action.get("action") == "ask_user":
                # Need to ask user a question
                question = action.get("question", "I need more information to proceed.")
                updated_state["user_questions"] = updated_state.get("user_questions", []) + [question]
                updated_state["route"] = "conversational_agent"  # Route to conversational to ask
                updated_state["ready_for_response"] = True
                print(f"Main agent: Asking user: {question}")
                return updated_state
            
            elif action.get("action") == "update_plan":
                # Modify the plan
                new_plan = action.get("plan", plan)
                updated_state["plan"] = new_plan
                updated_state["current_step"] = 0  # Reset to start of new plan
                current_step = 0
                plan = new_plan
                print(f"Main agent: Updated plan, now has {len(new_plan)} steps")
                # Continue with current step logic below
            
            elif action.get("action") == "finish":
                # All done, route to conversational agent
                updated_state["route"] = "conversational_agent"
                updated_state["ready_for_response"] = True
                print("Main agent: Plan complete, routing to conversational agent")
                return updated_state
            
            elif action.get("action") == "continue":
                # Move to next step - use next_step from action, or increment current_step
                next_step_idx = action.get("next_step")
                # next_step from action should be an index (0-based), but check if it's valid
                if next_step_idx is None or next_step_idx < 0 or next_step_idx >= len(plan):
                    # If invalid, just increment
                    next_step_idx = current_step + 1
                
                updated_state["current_step"] = next_step_idx
                current_step = next_step_idx
                print(f"Main agent: Continuing to step index {next_step_idx}")
            else:
                # Default: move to next step
                next_step_idx = current_step + 1
                updated_state["current_step"] = next_step_idx
                current_step = next_step_idx
                print(f"Main agent: Default action - moving to step index {next_step_idx}")
    
    # Execute current step
    if current_step < len(plan):
        step = plan[current_step]
        step_id = step.get("id")
        step_nodes = step.get("nodes", [])
        step_requires = step.get("requires", [])
        finished_steps = updated_state.get("finished_steps", [])
        
        # Check if this step is already finished - if so, skip to next step
        if step_id in finished_steps:
            print(f"Main agent: Step {step_id} (index {current_step}) already finished, skipping to next step")
            updated_state["current_step"] = current_step + 1
            updated_state["route"] = "main_agent"  # Loop back to process next step
            return updated_state
        
        # Check if requirements are satisfied
        if not _check_requirements_satisfied(updated_state, step_requires):
            print(f"Main agent: Step {step_id} requirements not satisfied: {step_requires}")
            # Try to adjust plan or wait
            # For now, we'll try to continue anyway (requirements might be optional)
            # In a more sophisticated version, we could replan here
        
        # Launch nodes for this step
        if step_nodes:
            updated_state["pending_nodes"] = step_nodes.copy()
            updated_state["route"] = step_nodes  # Route to worker nodes in parallel
            print(f"Main agent: Launching step {step_id} (index {current_step}) with nodes: {step_nodes}")
        else:
            # Empty step, mark as finished and continue
            finished_steps = updated_state.get("finished_steps", [])
            if step_id not in finished_steps:
                finished_steps.append(step_id)
            updated_state["finished_steps"] = finished_steps
            updated_state["current_step"] = current_step + 1
            updated_state["route"] = "main_agent"  # Loop back to continue
    else:
        # Plan is complete
        updated_state["route"] = "conversational_agent"
        updated_state["ready_for_response"] = True
        print("Main agent: Plan complete, routing to conversational agent")
    
    return updated_state
