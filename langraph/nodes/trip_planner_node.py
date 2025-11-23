"""Trip Planner node for managing trip plans in the database."""

import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from state import AgentState
from utils.trip_plan_db import get_trip_plan, upsert_trip_plan
from stm.short_term_memory import get_stm, get_trip_plan_summary, set_trip_plan_summary

# Load environment variables
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_trip_planner_prompt() -> str:
    """Get the system prompt for the Trip Planner."""
    return """You are the Trip Planner that manages user trip plans stored in a database.

Your role:
- Understand user intent: ADD, UPDATE, REPLACE, or DELETE a step in their trip plan
- Identify which step is being referenced (outbound flight, return flight, hotel, activity, car rental, etc.)
- Extract necessary information from the user message and previous agent outputs
- Generate structured instructions for modifying the trip plan

TRIP PLAN STRUCTURE:
Each step in the plan has:
- id: unique identifier (e.g., "flight_outbound", "flight_return", "hotel_1", "activity_1")
- type: "flight" | "hotel" | "activity" | "car_rental" | ...
- segment: "outbound" | "return" | null (for flights: distinguishes outbound vs return)
- title: human-readable title
- details: raw option JSON from tools
- price: numeric price
- event_time: ISO datetime string (when the event happens)
- status: "not_booked" | "booked" | "cancelled"

FLIGHT HANDLING:
- Outbound flights: type="flight", segment="outbound"
- Return flights: type="flight", segment="return"
- When user says "change my return flight" → find step with type="flight" AND segment="return"
- When user says "update the outbound" → find step with type="flight" AND segment="outbound"

USER INTENT DETECTION:

0. VIEW/SHOW:
   - "Show me my trip plan"
   - "What's in my trip plan"
   - "Display my plan"
   - "View my trip"
   - User wants to see their current trip plan

1. ADD/CONFIRM:
   - "I'll take option 2"
   - "Book the first hotel"
   - "Yes, select this flight"
   - "Add this to my plan"
   - User is confirming a choice from a previous list of options

2. UPDATE/CHANGE/REPLACE:
   - "Change my return flight"
   - "Replace the hotel with option 3"
   - "Update the activity to the evening slot"
   - "Switch to a different flight"
   - User wants to modify an existing step

3. DELETE/REMOVE:
   - "Remove the second hotel"
   - "Delete the outbound flight"
   - "Cancel the desert tour"
   - User wants to remove a step

STEP IDENTIFICATION:
Use context from:
- STM (short-term memory) - recent messages and trip plan summary
- Previous agent outputs - may contain lists of options
- Current trip plan - existing steps to identify which one to modify

For flights:
- "outbound flight" / "departure flight" → segment="outbound"
- "return flight" / "returning flight" → segment="return"

For hotels/activities:
- "first hotel" / "hotel 1" → find first hotel step
- "second hotel" / "hotel 2" → find second hotel step
- "the hotel" → if only one hotel, use it; otherwise ambiguous

OPTION EXTRACTION:
If user says "option 2" or "the first one":
- Check previous agent messages in STM for lists of options
- Extract the full option details (JSON) from the list
- Use that as the "details" field

EVENT TIME EXTRACTION:
When adding/updating, extract event_time from option details:
- flight → departure_time or departure_datetime
- hotel → checkin or check_in_datetime
- activity → start_time or start_datetime
- car_rental → pickup_time or pickup_datetime

Respond with JSON:
{
  "action": "view" | "add" | "update" | "replace" | "delete",
  "step_id": "string (for update/replace/delete - the id of step to modify)",
  "step_type": "flight" | "hotel" | "activity" | "car_rental" | ...,
  "segment": "outbound" | "return" | null (only for flights),
  "new_step": {
    "id": "string-unique-within-plan",
    "type": "flight | hotel | ...",
    "segment": "outbound | return | null",
    "title": "string",
    "details": { /* raw option JSON */ },
    "price": 123.45,
    "event_time": "2025-03-01T14:30:00Z",
    "status": "not_booked"
  } (only for add/update/replace),
  "error": "error message if action cannot be determined" (optional)
}

IMPORTANT:
- For "add": provide full new_step, generate unique id
- For "update": provide step_id and new_step with updated fields
- For "replace": provide step_id and complete new_step
- For "delete": provide step_id only
- If ambiguous or cannot determine intent, set error field
"""


def _extract_event_time(step_type: str, details: Dict[str, Any]) -> Optional[str]:
    """Extract event_time from option details based on step type.
    
    Args:
        step_type: Type of step (flight, hotel, activity, car_rental)
        details: Raw option JSON from tools
        
    Returns:
        ISO datetime string or None if not found
    """
    if step_type == "flight":
        # Try various field names for departure time
        for field in ["departure_time", "departure_datetime", "departure", "departureDate", "departure_date"]:
            if field in details:
                dt = details[field]
                if isinstance(dt, str):
                    return dt
                elif hasattr(dt, 'isoformat'):
                    return dt.isoformat()
    elif step_type == "hotel":
        for field in ["checkin", "check_in", "check_in_datetime", "checkin_datetime", "check_in_date"]:
            if field in details:
                dt = details[field]
                if isinstance(dt, str):
                    return dt
                elif hasattr(dt, 'isoformat'):
                    return dt.isoformat()
    elif step_type == "activity":
        for field in ["start_time", "start_datetime", "start", "startDate", "start_date"]:
            if field in details:
                dt = details[field]
                if isinstance(dt, str):
                    return dt
                elif hasattr(dt, 'isoformat'):
                    return dt.isoformat()
    elif step_type == "car_rental":
        for field in ["pickup_time", "pickup_datetime", "pickup", "pickupDate", "pickup_date"]:
            if field in details:
                dt = details[field]
                if isinstance(dt, str):
                    return dt
                elif hasattr(dt, 'isoformat'):
                    return dt.isoformat()
    
    return None


def _generate_step_id(step_type: str, segment: Optional[str], existing_plan: List[Dict]) -> str:
    """Generate a unique step ID within the plan.
    
    Args:
        step_type: Type of step
        segment: Segment (for flights) or None
        existing_plan: Current plan steps
        
    Returns:
        Unique step ID
    """
    existing_ids = {step.get("id") for step in existing_plan if step.get("id")}
    
    if step_type == "flight":
        if segment == "outbound":
            base_id = "flight_outbound"
        elif segment == "return":
            base_id = "flight_return"
        else:
            base_id = "flight_1"
    elif step_type == "hotel":
        # Count existing hotels
        hotel_count = sum(1 for s in existing_plan if s.get("type") == "hotel")
        base_id = f"hotel_{hotel_count + 1}"
    elif step_type == "activity":
        activity_count = sum(1 for s in existing_plan if s.get("type") == "activity")
        base_id = f"activity_{activity_count + 1}"
    elif step_type == "car_rental":
        car_count = sum(1 for s in existing_plan if s.get("type") == "car_rental")
        base_id = f"car_rental_{car_count + 1}"
    else:
        base_id = f"{step_type}_1"
    
    # Ensure uniqueness
    step_id = base_id
    counter = 1
    while step_id in existing_ids:
        counter += 1
        if step_type == "flight" and segment:
            step_id = f"flight_{segment}_{counter}"
        else:
            step_id = f"{base_id}_{counter}"
    
    return step_id


def _create_trip_plan_summary(plan: List[Dict]) -> Dict[str, Any]:
    """Create a condensed summary of the trip plan for STM.
    
    Args:
        plan: Full trip plan (list of steps)
        
    Returns:
        Condensed summary dictionary
    """
    summary = {
        "steps": []
    }
    
    for step in plan:
        step_summary = {
            "id": step.get("id"),
            "type": step.get("type"),
            "segment": step.get("segment"),
            "title": step.get("title"),
            "event_time": step.get("event_time"),
            "status": step.get("status")
        }
        summary["steps"].append(step_summary)
    
    return summary


async def trip_planner_node(state: AgentState) -> AgentState:
    """Trip Planner node that manages trip plans.
    
    This node:
    1. Reads STM to get email, session_id, and context
    2. Reads current plan from database
    3. Uses LLM to understand user intent and determine action
    4. Applies transformation (add/update/replace/delete)
    5. Saves updated plan to database
    6. Updates STM with plan summary
    7. Returns structured result for feedback node
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with trip_planner_result
    """
    print(f"\n=== Trip Planner Node ===")
    
    user_message = state.get("user_message", "")
    session_id = state.get("session_id")
    user_email = state.get("user_email")
    
    if not session_id or not user_email:
        print("[TRIP_PLANNER] Missing session_id or user_email")
        return {
            "trip_planner_result": {
                "status": "error",
                "message": "Missing session information"
            }
        }
    
    # Get STM data for context
    stm_data = get_stm(session_id) if session_id else None
    trip_plan_summary = get_trip_plan_summary(session_id) if session_id else None
    
    # Get current plan from database
    print(f"[TRIP_PLANNER] Retrieving plan for email={user_email}, session_id={session_id}")
    current_plan_data = await get_trip_plan(user_email, session_id)
    current_plan = current_plan_data["plan"] if current_plan_data else []
    
    print(f"[TRIP_PLANNER] Current plan has {len(current_plan)} steps")
    if current_plan:
        print(f"[TRIP_PLANNER] Plan steps: {[s.get('id') + ' - ' + s.get('title', 'N/A') for s in current_plan]}")
    
    # Build context for LLM
    context_parts = []
    
    # Add STM context
    if stm_data:
        last_messages = stm_data.get("last_messages", [])
        if last_messages:
            recent_context = "\n".join([
                f"{msg['role'].upper()}: {msg['text']}"
                for msg in last_messages[-5:]  # Last 5 messages
            ])
            context_parts.append(f"Recent conversation:\n{recent_context}")
    
    # Add trip plan summary
    if trip_plan_summary:
        context_parts.append(f"Current trip plan summary:\n{json.dumps(trip_plan_summary, indent=2)}")
    elif current_plan:
        # Create summary on the fly
        summary = _create_trip_plan_summary(current_plan)
        context_parts.append(f"Current trip plan:\n{json.dumps(summary, indent=2)}")
    
    # Add current plan details (limited to avoid token limits)
    if current_plan:
        plan_preview = []
        for step in current_plan[:10]:  # Limit to first 10 steps
            plan_preview.append({
                "id": step.get("id"),
                "type": step.get("type"),
                "segment": step.get("segment"),
                "title": step.get("title")
            })
        context_parts.append(f"Existing plan steps:\n{json.dumps(plan_preview, indent=2)}")
    
    context = "\n\n".join(context_parts) if context_parts else "No previous context available."
    
    # Call LLM to determine action
    prompt = get_trip_planner_prompt()
    
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"""Context:
{context}

User message: {user_message}

Determine the action to take on the trip plan. Respond with JSON only."""}
    ]
    
    try:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
        except Exception as e:
            # Fallback if JSON mode not supported
            print(f"[TRIP_PLANNER] JSON mode not supported, using regular mode: {e}")
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.3
            )
        
        result_json = json.loads(response.choices[0].message.content)
        print(f"[TRIP_PLANNER] LLM result: {json.dumps(result_json, indent=2)}")
        
        action = result_json.get("action")
        error = result_json.get("error")
        
        if error:
            return {
                "trip_planner_result": {
                    "status": "error",
                    "message": error,
                    "action": None
                }
            }
        
        # Handle view action (just retrieve and return plan)
        if action == "view":
            # Return the current plan for display
            return {
                "trip_planner_result": {
                    "status": "success",
                    "action": "view",
                    "plan": current_plan,
                    "message": f"Retrieved trip plan with {len(current_plan)} step(s)"
                }
            }
        
        # Apply transformation
        updated_plan = current_plan.copy()
        
        if action == "add":
            new_step = result_json.get("new_step")
            if not new_step:
                return {
                    "trip_planner_result": {
                        "status": "error",
                        "message": "Add action requires new_step",
                        "action": "add"
                    }
            }
            
            # Ensure step has required fields
            if "id" not in new_step:
                step_type = new_step.get("type", "unknown")
                segment = new_step.get("segment")
                new_step["id"] = _generate_step_id(step_type, segment, updated_plan)
            
            # Extract event_time if not provided
            if not new_step.get("event_time"):
                event_time = _extract_event_time(new_step.get("type"), new_step.get("details", {}))
                if event_time:
                    new_step["event_time"] = event_time
                else:
                    print(f"[TRIP_PLANNER] Warning: Could not extract event_time for {new_step.get('type')}")
            
            updated_plan.append(new_step)
            print(f"[TRIP_PLANNER] Added step: {new_step.get('id')}")
            
        elif action == "update" or action == "replace":
            step_id = result_json.get("step_id")
            new_step = result_json.get("new_step")
            
            if not step_id or not new_step:
                return {
                    "trip_planner_result": {
                        "status": "error",
                        "message": f"{action} action requires step_id and new_step",
                        "action": action
                    }
                }
            
            # Find step to update
            step_index = None
            for i, step in enumerate(updated_plan):
                if step.get("id") == step_id:
                    step_index = i
                    break
            
            if step_index is None:
                return {
                    "trip_planner_result": {
                        "status": "error",
                        "message": f"Step with id '{step_id}' not found in plan",
                        "action": action,
                        "step_id": step_id
                    }
                }
            
            # For update, merge fields; for replace, replace entirely
            if action == "update":
                # Merge new fields into existing step
                existing_step = updated_plan[step_index]
                existing_step.update(new_step)
                # Preserve id
                existing_step["id"] = step_id
                updated_plan[step_index] = existing_step
            else:  # replace
                new_step["id"] = step_id  # Preserve id
                updated_plan[step_index] = new_step
            
            # Extract event_time if not provided
            if not updated_plan[step_index].get("event_time"):
                event_time = _extract_event_time(
                    updated_plan[step_index].get("type"),
                    updated_plan[step_index].get("details", {})
                )
                if event_time:
                    updated_plan[step_index]["event_time"] = event_time
            
            print(f"[TRIP_PLANNER] {action.capitalize()}d step: {step_id}")
            
        elif action == "delete":
            step_id = result_json.get("step_id")
            
            if not step_id:
                return {
                    "trip_planner_result": {
                        "status": "error",
                        "message": "Delete action requires step_id",
                        "action": "delete"
                    }
                }
            
            # Find and remove step
            step_index = None
            for i, step in enumerate(updated_plan):
                if step.get("id") == step_id:
                    step_index = i
                    break
            
            if step_index is None:
                return {
                    "trip_planner_result": {
                        "status": "error",
                        "message": f"Step with id '{step_id}' not found in plan",
                        "action": "delete",
                        "step_id": step_id
                    }
                }
            
            removed_step = updated_plan.pop(step_index)
            print(f"[TRIP_PLANNER] Deleted step: {step_id} ({removed_step.get('title', 'N/A')})")
            
        else:
            return {
                "trip_planner_result": {
                    "status": "error",
                    "message": f"Unknown action: {action}",
                    "action": action
                }
            }
        
        # Save to database
        print(f"[TRIP_PLANNER] Saving plan for email={user_email}, session_id={session_id}, steps={len(updated_plan)}")
        success = await upsert_trip_plan(user_email, session_id, updated_plan)
        
        if not success:
            return {
                "trip_planner_result": {
                    "status": "error",
                    "message": "Failed to save trip plan to database",
                    "action": action
                }
            }
        
        # Update STM with plan summary
        plan_summary = _create_trip_plan_summary(updated_plan)
        set_trip_plan_summary(session_id, plan_summary)
        
        # Return success result
        return {
            "trip_planner_result": {
                "status": "success",
                "action": action,
                "step_id": result_json.get("step_id"),
                "step_type": result_json.get("step_type"),
                "segment": result_json.get("segment"),
                "message": f"Trip plan updated: {action} action completed"
            }
        }
        
    except Exception as e:
        print(f"[TRIP_PLANNER] Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "trip_planner_result": {
                "status": "error",
                "message": f"Error processing trip plan: {str(e)}",
                "action": None
            }
        }

