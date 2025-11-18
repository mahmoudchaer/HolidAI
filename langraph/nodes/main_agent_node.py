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
1. CREATE INTELLIGENT PLANS: Break down user requests into logical steps with clear dependencies.
2. EXECUTE STEPS: Launch worker nodes in parallel whenever their inputs are independent.
3. ADAPT: Modify plans dynamically when results require follow-up actions.
4. DECIDE: After each step, decide whether to continue, modify the plan, ask the user, or finish.

CRITICAL: PLAN ONLY WHAT IS REQUESTED
- Add steps ONLY for the information/tools the user explicitly wants or truly depends on.
- If two tasks have no dependency (e.g., flights + eSIM), schedule their nodes in the SAME step so they run in parallel.
- When sequential order matters (e.g., “choose dates based on weather before booking flights”), make that dependency explicit.
- Never insert weather, hotels, visa, or other utilities unless the user asks for them or clearly needs their output.
- Think carefully about prerequisites before introducing dependencies.

Available worker nodes:
- utilities_agent: Weather, currency conversion, date/time, eSIM bundles, holidays
- flight_agent: Flight searches (one-way, round-trip, flexible dates)
- hotel_agent: Hotel searches (by location, price, dates)
- visa_agent: Visa requirement checks
- tripadvisor_agent: Location searches, restaurants, attractions, reviews

PLAN STRUCTURE:
Each step in your plan should be a JSON object with:
- "id": integer step number
- "nodes": list of node names to run in parallel for this step (e.g., ["utilities_agent", "flight_agent"])
- "requires": list of result keys that must exist before this step can run (e.g., ["weather_data"])
- "produces": list of result keys this step will produce (e.g., ["weather_data", "flight_options"])

PARALLEL VS SEQUENTIAL:
- Group independent tasks (no shared inputs) in the same step.
- Use sequential steps only when a later task truly needs prior output.
- Example: “Find flights and eSIM bundles” → single step with ["flight_agent", "utilities_agent"].
- Example: “Pick the driest days in the next 20 days, then book flights” → weather first, flights second.

INTELLIGENT PLANNING EXAMPLES:

Example 1: User says "I want to travel to Paris next week"
→ Step 1: Get flights and hotels (flight_agent, hotel_agent) - produces: flight_options, hotel_options
(Only add weather if the user asked about it.)

Example 2: User says "Find me flights to Dubai"
→ Step 1: Get flights (flight_agent) - produces: flight_options

Example 3: User says "What's the weather in Tokyo?"
→ Step 1: Get weather (utilities_agent) - produces: weather_data

Example 4: User says "Get me flights from Beirut to Paris and eSIM bundles in France"
→ Step 1: ["flight_agent", "utilities_agent"] (parallel) - produces: flight_options, esim_data

Example 5: User says “Over the next 20 days pick the best 5 days based on weather, then book flights”
→ Step 1: utilities_agent (weather) - produces: weather_data / good_dates
→ Step 2: flight_agent (requires: weather_data) - produces: flight_options

DYNAMIC REASONING:
- If a result indicates missing info → add new steps or ask the user.
- If results block progress → modify the remaining plan or ask for alternatives.

When responding:
- To create/update a plan: {"action": "create_plan", "plan": [...]}
- To ask the user for missing info: {"action": "ask_user", "question": "..."}
- To finish immediately: {"action": "finish"}
- To continue with the current plan: {"action": "continue", "next_step": step_id}
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
    """Check if all required result keys exist in state.results.
    Also checks for alternative key names (e.g., 'flight_options' -> 'flight_result', 'flight_agent', 'flight')."""
    results = state.get("results", {})
    for req in requires:
        # Check exact match first
        if req in results and results[req] is not None:
            continue
        
        # Check for alternative keys based on common patterns
        alternative_keys = []
        if req == "flight_options":
            alternative_keys = ["flight_result", "flight_agent", "flight"]
        elif req == "hotel_options":
            alternative_keys = ["hotel_result", "hotel_agent", "hotel"]
        elif req == "visa_info":
            alternative_keys = ["visa_result", "visa_agent", "visa"]
        elif req == "weather_data":
            alternative_keys = ["utilities_result", "utilities_agent", "utilities"]
        elif req == "activities":
            alternative_keys = ["tripadvisor_result", "tripadvisor_agent", "tripadvisor"]
        
        # Check if any alternative key exists
        found = False
        for alt_key in alternative_keys:
            if alt_key in results and results[alt_key] is not None:
                found = True
                break
        
        if not found:
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

BE INTELLIGENT BUT NOT OVERLY PROACTIVE:
- Analyze what the user explicitly asks for - do ONLY what they request.
- Add weather/date utilities ONLY if the user asks for them or explicitly needs weather-derived reasoning.
- Flights/hotels without weather requests → call only flight_agent/hotel_agent.
- Only add hotels if user explicitly asks for hotels (or mentions both flights AND hotels).
- Consider dependencies ONLY when truly relevant (e.g., weather needed before choosing dates, flights before hotels, nationality before visa).

CRITICAL: DISTINGUISH UTILITY QUERIES FROM TRAVEL PLANNING
- Utility-only queries (holidays, weather, currency, date/time, eSIM) → ONLY use utilities_agent.
- Travel planning queries (flights, hotels, visa, activities) → Use the relevant agents with clear dependencies.

INTELLIGENT PLANNING RULES:
1. If user ONLY asks about holidays/weather/currency/date/time/eSIM → Use utilities_agent (single step).
2. Flights with dates → call flight_agent (weather only if explicitly requested or clearly needed for reasoning).
3. Flights without dates → call flight_agent (single step).
4. Hotels with dates → call hotel_agent (weather only if explicitly requested).
5. Flights + hotels → schedule both; if independent, run them in the same step; add weather only when asked/needed.
6. Flights + eSIM (or any independent combo) → place nodes in the same step for parallel execution.
7. If user mentions nationality AND requests visa info → add visa_agent (parallel unless dependent on other data).
8. Activities/restaurants → call tripadvisor_agent AFTER flights/hotels if those were requested; otherwise single step.
9. Always justify dependencies: do not block other steps unless their data is required.

IMPORTANT ABOUT WORKER NODES:
- Worker nodes receive the FULL user_message.
- They determine their own parameters.
- You ONLY create the plan structure.
- DO NOT invent fake result keys like "non_rainy_dates" - use real keys such as "weather_data", "flight_options", "hotel_options".

VALID RESULT KEYS:
- "weather_data" (from utilities_agent - weather queries)
- "holidays_data" (from utilities_agent - holidays queries)
- "esim_data" (from utilities_agent - eSIM queries)
- "utilities_result" (from utilities_agent - any utility query)
- "flight_options" or "flight_result" (from flight_agent)
- "hotel_options" or "hotel_result" (from hotel_agent)
- "visa_info" or "visa_result" (from visa_agent)
- "activities" or "tripadvisor_result" (from tripadvisor_agent)

Create a plan that makes sense logically. CRITICAL: If dates are mentioned, ALWAYS check weather first. Do ONLY what the user asks for - don't add hotels unless the user explicitly requests them or mentions both flights AND hotels.

Return a JSON object with:
{{
  "action": "create_plan",
  "plan": [
    {{"id": 1, "nodes": ["utilities_agent"], "requires": [], "produces": ["holidays_data"]}},
    ...
  ]
}}

EXAMPLES:
- User: "get me holidays in Dubai, UAE in December 2025" → Plan: [{{"id": 1, "nodes": ["utilities_agent"], "requires": [], "produces": ["holidays_data"]}}]
- User: "get me flights from Beirut to Paris from december 13 2025 till december 17 2025" → Plan: [{{"id": 1, "nodes": ["flight_agent"], "requires": [], "produces": ["flight_options"]}}]
- User: "find me hotels in Dubai for December 20-25" → Plan: [{{"id": 1, "nodes": ["hotel_agent"], "requires": [], "produces": ["hotel_options"]}}]
- User: "get me flights from Beirut to Paris" (no dates) → Plan: [{{"id": 1, "nodes": ["flight_agent"], "requires": [], "produces": ["flight_options"]}}]
- User: "I want to travel to Paris next week and need good weather days" → Plan: [{{"id": 1, "nodes": ["utilities_agent"], "requires": [], "produces": ["weather_data"]}}, {{"id": 2, "nodes": ["flight_agent", "hotel_agent"], "requires": ["weather_data"], "produces": ["flight_options", "hotel_options"]}}]
- User: "what's the weather in Tokyo?" → Plan: [{{"id": 1, "nodes": ["utilities_agent"], "requires": [], "produces": ["weather_data"]}}]

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
    
    # Rule 4: Check visa if mentioned or if we have destination and nationality
    # Check for nationality mentions (common patterns: "I am [nationality]", "I'm [nationality]", "[nationality] citizen", etc.)
    # The LLM-based plan generation will catch most cases, but this is a fallback for keyword detection
    has_nationality = any(phrase in user_lower for phrase in ["citizen", "nationality", "passport", "i am", "i'm", "from"]) or any(word in user_lower for word in ["lebanese", "american", "british", "french", "german", "italian", "spanish", "canadian", "australian", "indian", "chinese", "japanese", "brazilian", "mexican", "russian", "turkish", "egyptian", "emirati", "saudi", "kuwaiti", "qatari", "omani", "bahraini", "jordanian", "syrian", "iraqi", "iranian", "pakistani", "bangladeshi", "thai", "vietnamese", "korean", "philippine", "indonesian", "malaysian", "singaporean", "nigerian", "kenyan", "ethiopian", "moroccan", "algerian", "tunisian"])
    if has_visa_query or (has_destination and has_nationality):
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
3. If we should continue to next step (default) → "continue" (do NOT provide next_step - it will be auto-incremented)
4. If we're done → "finish"

IMPORTANT: When returning "continue", do NOT provide next_step. The system will automatically move to the next step index (current_step + 1).

Return JSON:
{{
  "action": "continue|update_plan|ask_user|finish",
  "plan": [...] (if action is update_plan),
  "question": "..." (if action is ask_user)
}}

DO NOT include "next_step" in your response - it will be calculated automatically."""}
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
                # Move to next step - ALWAYS increment by 1, don't trust LLM's next_step
                # The LLM might return step IDs instead of indices, causing confusion
                next_step_idx = current_step + 1
                
                # Validate the next step index
                if next_step_idx >= len(plan):
                    # Plan is complete
                    updated_state["route"] = "conversational_agent"
                    updated_state["ready_for_response"] = True
                    print("Main agent: Plan complete, routing to conversational agent")
                    return updated_state
                
                updated_state["current_step"] = next_step_idx
                current_step = next_step_idx
                print(f"Main agent: Continuing to step index {next_step_idx} (step ID: {plan[next_step_idx].get('id')})")
            else:
                # Default: move to next step
                next_step_idx = current_step + 1
                if next_step_idx >= len(plan):
                    # Plan is complete
                    updated_state["route"] = "conversational_agent"
                    updated_state["ready_for_response"] = True
                    print("Main agent: Plan complete, routing to conversational agent")
                    return updated_state
                updated_state["current_step"] = next_step_idx
                current_step = next_step_idx
                print(f"Main agent: Default action - moving to step index {next_step_idx} (step ID: {plan[next_step_idx].get('id')})")
    
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
            # CRITICAL: Clear any old pending_nodes first, then set fresh value
            # This ensures we don't reuse stale state from previous steps
            updated_state["pending_nodes"] = step_nodes.copy()
            updated_state["route"] = step_nodes  # Route to worker nodes in parallel
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{timestamp}] Main agent: Launching step {step_id} (index {current_step}) with nodes: {step_nodes}")
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
