"""Feedback node for Trip Planner that generates user-friendly messages."""

import sys
import os
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import AgentState

# Load environment variables
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_trip_planner_feedback_prompt() -> str:
    """Get the system prompt for the Trip Planner Feedback node."""
    return """You are the Trip Planner Feedback Generator that creates user-friendly messages about trip plan changes.

Your role:
- Take the result from trip_planner_node
- Generate clear, natural messages for the user
- Explain what was done (added, updated, deleted)
- Provide helpful error messages if something went wrong
- Be conversational and friendly

MESSAGE TYPES:

0. SUCCESS - View:
   - Format the trip plan steps in a clear, organized way
   - List each step with its details (type, title, event_time, price, status)
   - If plan is empty: "Your trip plan is currently empty. Would you like to add flights, hotels, or activities?"
   - If plan has steps: Present them in chronological order (by event_time) or by type
   - Example: "Here's your current trip plan:\n\n1. Outbound Flight: MEA Flight ME 428 from Beirut to Dubai on December 24, 2025 at 4:15 PM - $243 (Not booked)\n\n2. Hotel: [Hotel name] in Dubai - Check-in: December 24, 2025 - $200/night (Not booked)"

1. SUCCESS - Add:
   - "I've added [step title] to your trip plan."
   - "Your [step type] has been added to the plan."
   - Example: "I've added your outbound flight to Paris on March 1st to your trip plan."

2. SUCCESS - Update/Replace:
   - "I've updated your [step type] in your trip plan."
   - "Your [step description] has been changed."
   - Example: "I've updated your return flight to the new option you selected."

3. SUCCESS - Delete:
   - "I've removed [step description] from your trip plan."
   - "Your [step type] has been deleted."
   - Example: "I've removed the second hotel from your trip plan."

4. ERROR - Step not found:
   - "I couldn't find [step description] in your trip plan. Please make sure it exists first."
   - Example: "I couldn't update your return flight because I couldn't find any saved return flight. Please choose one first."

5. ERROR - Missing information:
   - "I couldn't [action] because [reason]. [How to fix]."
   - Example: "I couldn't add the flight because I couldn't determine which option you selected. Please specify which option you'd like (e.g., 'option 1' or 'the first flight')."

6. ERROR - General:
   - "I encountered an issue updating your trip plan: [error]. Please try again or rephrase your request."

IMPORTANT:
- Be specific about what was changed (outbound flight, return flight, first hotel, etc.)
- For flights, mention "outbound" or "return" to be clear
- For hotels/activities, mention which one if there are multiple
- Keep messages concise but informative
- Use natural language, not technical jargon

Respond with JSON:
{
  "message": "user-friendly message",
  "status": "success" | "error"
}"""


async def trip_planner_feedback_node(state: AgentState) -> AgentState:
    """Trip Planner feedback node that generates user-friendly messages.
    
    Args:
        state: Current agent state with trip_planner_result
        
    Returns:
        Updated agent state with last_response
    """
    print(f"\n=== Trip Planner Feedback Node ===")
    
    trip_planner_result = state.get("trip_planner_result", {})
    
    if not trip_planner_result:
        print("[TRIP_PLANNER_FEEDBACK] No trip_planner_result found")
        return {
            "last_response": "I'm sorry, but I couldn't process your trip plan request. Please try again.",
            "route": "end"
        }
    
    status = trip_planner_result.get("status")
    action = trip_planner_result.get("action")
    message = trip_planner_result.get("message", "")
    step_id = trip_planner_result.get("step_id")
    step_type = trip_planner_result.get("step_type")
    segment = trip_planner_result.get("segment")
    plan = trip_planner_result.get("plan", [])
    
    print(f"[TRIP_PLANNER_FEEDBACK] Status: {status}, Action: {action}, Plan steps: {len(plan)}")
    
    # Build context for LLM
    if action == "view" and plan:
        import json
        plan_json = json.dumps(plan, indent=2)
        context = f"""Trip Planner Result:
- Status: {status}
- Action: {action}
- Message: {message}
- Plan has {len(plan)} step(s)

Trip Plan Data:
{plan_json}

Format this trip plan in a clear, user-friendly way. List each step with its details (type, title, event_time, price, status). Present them in chronological order if event_times are available."""
    else:
        context = f"""Trip Planner Result:
- Status: {status}
- Action: {action}
- Step ID: {step_id}
- Step Type: {step_type}
- Segment: {segment}
- Message: {message}

Generate a user-friendly message based on this result."""
    
    try:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": get_trip_planner_feedback_prompt()},
                    {"role": "user", "content": context}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
        except Exception as e:
            # Fallback if JSON mode not supported
            print(f"[TRIP_PLANNER_FEEDBACK] JSON mode not supported, using regular mode: {e}")
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": get_trip_planner_feedback_prompt()},
                    {"role": "user", "content": context}
                ],
                temperature=0.7
            )
        
        result = response.choices[0].message.content
        import json
        feedback_data = json.loads(result)
        
        user_message = feedback_data.get("message", message)
        
        print(f"[TRIP_PLANNER_FEEDBACK] Generated message: {user_message}")
        
        return {
            "last_response": user_message,
            "route": "conversational_agent_feedback"
        }
        
    except Exception as e:
        print(f"[TRIP_PLANNER_FEEDBACK] Error generating feedback: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback message
        if status == "success":
            if action == "view":
                if plan:
                    # Format plan manually if LLM failed
                    plan_lines = []
                    for i, step in enumerate(plan, 1):
                        step_type = step.get("type", "item")
                        title = step.get("title", "Untitled")
                        event_time = step.get("event_time", "")
                        price = step.get("price")
                        status_step = step.get("status", "not_booked")
                        
                        line = f"{i}. {step_type.title()}: {title}"
                        if event_time:
                            line += f" - {event_time}"
                        if price:
                            line += f" - ${price}"
                        line += f" ({status_step})"
                        plan_lines.append(line)
                    
                    fallback = "Here's your current trip plan:\n\n" + "\n".join(plan_lines)
                else:
                    fallback = "Your trip plan is currently empty. Would you like to add flights, hotels, or activities?"
            elif action == "add":
                fallback = "I've added the item to your trip plan."
            elif action == "update" or action == "replace":
                fallback = "I've updated your trip plan."
            elif action == "delete":
                fallback = "I've removed the item from your trip plan."
            else:
                fallback = "Your trip plan has been updated."
        else:
            fallback = message or "I encountered an issue updating your trip plan. Please try again."
        
        return {
            "last_response": fallback,
            "route": "conversational_agent_feedback"
        }

