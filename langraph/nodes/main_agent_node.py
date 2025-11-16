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

CRITICAL: BE INTELLIGENT AND SELECTIVE
- Make OBVIOUS assumptions (e.g., Paris is in France, Beirut is in Lebanon) - don't ask about these
- Ask for user input when it would help avoid wrong assumptions (e.g., if all dates have good weather, ask about price preferences)
- Don't always create deep plans - sometimes asking the user first makes life easier
- ONLY gather information the user actually needs or explicitly requested
- If user mentions travel → ASK what they need (flights? hotels? activities? visa?) instead of assuming they need everything
- If user mentions a destination and dates → Check weather first (needed for planning), then ASK what else they need
- Don't automatically check visa requirements unless user explicitly asks or it's critical for their immediate planning
- Don't automatically get activities/restaurants unless user asks for them
- Balance between being helpful and not overwhelming the user with unnecessary information

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
→ Step 2: ASK user what they need: "What do you need help with? Flights? Hotels? Both?"
→ Don't assume they need everything - let them tell you

Example 2: User says "Find me flights to Dubai"
→ Step 1: Get flights (flight_agent) - produces: flight_options
→ Only get flights - don't assume they need hotels, visa, or activities

Example 3: User says "I want to go to Paris, I have 10 days vacation, prefer no rain, cheapest possible"
→ Step 1: Check weather (utilities_agent) - needed to find no-rain days
→ Step 2: ASK user: "What do you need? Flights? Hotels? Both?"
→ Don't automatically get visa or activities unless user asks

Example 4: User says "What's the weather in Tokyo?"
→ Step 1: Get weather (utilities_agent) - produces: weather_data
→ Only get weather - nothing else needed

DYNAMIC REASONING - ASK WHEN IT HELPS:
- If weather shows all dates are good → ASK user about preferences (price, specific dates, etc.) BEFORE searching flights/hotels
- If weather shows rain all week → modify plan to suggest different dates or ask user
- If flights unavailable → adjust dates or ask user for alternatives
- If results indicate missing info → ASK user clarifying questions rather than making assumptions
- If multiple good options exist → ASK user for preferences to avoid wrong assumptions
- Don't create deep plans when asking the user first would be simpler and more accurate

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


def _generate_plan(state: AgentState) -> list:
    """Use LLM to generate an intelligent, proactive execution plan."""
    user_message = state.get("user_message", "").strip()
    
    # Check if this is just a greeting or simple query that doesn't need a plan
    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "greetings", "hi!", "hello!", "hey!"]
    user_lower = user_message.lower().strip()
    
    # If it's just a greeting or very short non-travel query, return empty plan
    if user_lower in greetings or (len(user_message.split()) <= 2 and not any(word in user_lower for word in ["flight", "hotel", "travel", "trip", "visa", "weather", "destination", "book", "search"])):
        print("Main agent: Simple greeting or query detected, no plan needed")
        return []  # Empty plan means route to conversational agent
    
    messages = [
        {"role": "system", "content": get_main_agent_prompt()},
        {"role": "user", "content": f"""Create an intelligent, proactive execution plan for this user request.

User's message: {user_message}

BE INTELLIGENT AND BALANCED:
- Make OBVIOUS assumptions (Paris = France, Beirut = Lebanon) - don't ask about these
- Ask for user input when it would help avoid wrong assumptions
- Don't always create deep plans - sometimes asking first is better
- Analyze what the user wants to accomplish
- Think about what information is needed FIRST (e.g., weather for travel destinations with dates)
- Consider dependencies: weather affects travel dates, flights affect hotels, destination affects visa

INTELLIGENT PLANNING RULES:
1. If user mentions travel to a destination with dates → Check weather first (needed for planning), then ASK what they need (flights? hotels? both?)
2. If user explicitly asks for flights → Get flights only (don't assume hotels)
3. If user explicitly asks for hotels → Get hotels only (don't assume flights)
4. If user explicitly asks for both → Get both flights and hotels
5. If user only asks about weather → Just get weather (single step)
6. If user mentions nationality and destination → DON'T automatically check visa unless user explicitly asks or it's critical
7. If user wants activities/restaurants → Only get them if user explicitly asks
8. If multiple good options exist → ASK user for preferences rather than assuming
9. ALWAYS ask what the user needs instead of assuming they need everything

Create a plan that makes sense logically, but ASK the user what they need instead of assuming they need flights, hotels, visa, and activities all at once.

Return a JSON object with:
{{
  "action": "create_plan",
  "plan": [
    {{"id": 1, "nodes": ["utilities_agent"], "requires": [], "produces": ["weather_data"]}},
    {{"id": 2, "nodes": ["flight_agent", "hotel_agent"], "requires": ["weather_data"], "produces": ["flight_options", "hotel_options"]}},
    ...
  ]
}}

Make sure the plan is intelligent and logical based on the user's request."""}
    ]
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3  # Lower temperature for more consistent, logical planning
    )
    
    content = response.choices[0].message.content or ""
    result = _extract_json_from_response(content)
    
    if result.get("action") == "create_plan" and "plan" in result:
        plan = result["plan"]
        print(f"Main agent: Generated intelligent plan with {len(plan)} steps")
        for step in plan:
            print(f"  Step {step.get('id')}: {step.get('nodes')} (requires: {step.get('requires')}, produces: {step.get('produces')})")
        return plan
    
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
    
    # Rule 2: If user mentions travel with destination and dates, check weather first (needed for planning)
    # Check if user implicitly wants flights/hotels (e.g., "cheapest possible", "book", "plan my trip")
    has_implicit_travel_request = any(word in user_lower for word in ["cheapest", "cheap", "budget", "book", "plan my trip", "help me plan", "find me"])
    
    if has_destination and has_dates:
        plan.append({
            "id": node_id,
            "nodes": ["utilities_agent"],
            "requires": [],
            "produces": ["weather_data"]
        })
        # If user implicitly wants travel planning (cheapest, book, etc.), we'll proceed with flights+hotels after weather
        # Otherwise, we'll ask what they need
        if not has_implicit_travel_request and not (has_flight_query or has_hotel_query):
            # After weather, we should ask what they need - don't assume flights/hotels/visa/activities
            # The decision logic will handle asking the user
            return plan
        node_id += 1
    
    # Rule 2b: If user implicitly wants travel planning or explicitly asks, add flights and hotels
    if (has_implicit_travel_request or has_flight_query or has_hotel_query) and has_destination:
        parallel_nodes = []
        if has_flight_query or has_implicit_travel_request:
            parallel_nodes.append("flight_agent")
        if has_hotel_query or has_implicit_travel_request:
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
    
    # Rule 3: Only get what user explicitly asks for (if not already added in Rule 2b)
    # Only add if we haven't already added them due to implicit travel request
    if has_flight_query and not has_implicit_travel_request and not any(step.get("nodes") == ["flight_agent"] or "flight_agent" in step.get("nodes", []) for step in plan):
        plan.append({
            "id": node_id,
            "nodes": ["flight_agent"],
            "requires": [],
            "produces": ["flight_options"]
        })
        node_id += 1
    
    if has_hotel_query and not has_implicit_travel_request and not any(step.get("nodes") == ["hotel_agent"] or "hotel_agent" in step.get("nodes", []) for step in plan):
        plan.append({
            "id": node_id,
            "nodes": ["hotel_agent"],
            "requires": [],
            "produces": ["hotel_options"]
        })
        node_id += 1
    
    # Rule 4: Only check visa if explicitly mentioned
    if has_visa_query:
        plan.append({
            "id": node_id,
            "nodes": ["visa_agent"],
            "requires": [],
            "produces": ["visa_info"]
        })
        node_id += 1
    
    # Rule 5: Only get activities if explicitly mentioned
    if has_activity_query:
        plan.append({
            "id": node_id,
            "nodes": ["tripadvisor_agent"],
            "requires": [],
            "produces": ["activities"]
        })
        node_id += 1
    
    # Default: if nothing matches, just get utilities
    if not plan:
        plan = [{"id": 1, "nodes": ["utilities_agent"], "requires": [], "produces": ["utilities_result"]}]
    
    print(f"Main agent: Generated fallback plan with {len(plan)} steps")
    return plan


def _decide_next_action(state: AgentState) -> dict:
    """Use LLM to decide the next action after a step completes."""
    user_message = state.get("user_message", "")
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    results = state.get("results", {})
    finished_steps = state.get("finished_steps", [])
    
    # Build context about current state with actual data for decision-making
    results_summary = {}
    for key, value in results.items():
        if isinstance(value, dict):
            if value.get("error"):
                results_summary[key] = f"Error: {value.get('error_message', 'Unknown error')}"
            else:
                # Include actual data for weather to help decision-making
                if key in ["weather_data", "utilities_agent", "utilities", "utilities_result"]:
                    # Include weather description to check if all dates are good
                    description = value.get("description", "")
                    location = value.get("location", "")
                    temperature = value.get("temperature", "")
                    results_summary[key] = f"Success - Location: {location}, Temp: {temperature}°C, Conditions: {description}"
                else:
                    results_summary[key] = "Success"
        else:
            results_summary[key] = str(value)[:100]  # Truncate long values
    
    # Check if user mentioned preferences in original message
    user_lower = user_message.lower()
    has_price_preference = any(word in user_lower for word in ["cheap", "budget", "expensive", "luxury", "price", "cost", "affordable"])
    has_date_preference = any(word in user_lower for word in ["specific date", "prefer", "favorite", "best date", "which date"])
    has_clear_preferences = has_price_preference or has_date_preference
    
    messages = [
        {"role": "system", "content": get_main_agent_prompt()},
        {"role": "user", "content": f"""You are executing a multi-step plan. Intelligently decide what to do next.

User's original request: {user_message}
User mentioned preferences: {"Yes (price/date preferences mentioned)" if has_clear_preferences else "No (no clear preferences mentioned)"}

Current plan:
{json.dumps(plan, indent=2)}

Current step: {current_step}
Finished steps: {finished_steps}

Results so far:
{json.dumps(results_summary, indent=2)}

BE INTELLIGENT IN YOUR DECISION - ASK WHEN IT HELPS:
- If weather check is complete AND user hasn't specified what they need → ASK user: "What do you need help with? Flights? Hotels? Both?"
- If weather shows ALL dates are good AND user has NO clear preferences → ASK user about preferences (price, specific dates) BEFORE searching flights/hotels
- If weather shows bad conditions (rain, storms) → consider modifying plan or asking user about alternative dates
- If flights are unavailable → consider adjusting dates or asking user for alternatives
- If multiple good options exist AND user preferences unclear → ASK user for preferences to avoid wrong assumptions
- Don't make assumptions about what user needs (flights, hotels, visa, activities) - ASK instead
- Don't automatically get visa or activities unless user explicitly asks
- Only continue automatically if user explicitly requested something (e.g., "cheapest possible" implies flights+hotels)
- If user already mentioned what they need (flights, hotels, both) → you can proceed

Decide:
1. If plan needs modification based on results → "update_plan" with new plan
2. If we need user input (when preferences unclear or multiple good options) → "ask_user" with question
3. If we should continue to next step (user preferences clear) → "continue" with next_step
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
        plan = _generate_plan(state)
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
