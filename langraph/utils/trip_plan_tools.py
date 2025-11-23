"""Tools for interacting with trip plans.

These tools can be used by agents to get, clear, or modify trip plans.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.trip_plan_db import get_trip_plan, upsert_trip_plan, clear_trip_plan


async def get_trip_plan_tool(email: str, session_id: str) -> Dict[str, Any]:
    """Get the current trip plan for a user and session.
    
    Args:
        email: User's email address
        session_id: Session identifier
        
    Returns:
        Dictionary with 'plan' (list of steps sorted by event_time) and 'updated_at'
    """
    try:
        result = await get_trip_plan(email, session_id)
        
        if not result:
            return {
                "plan": [],
                "updated_at": None
            }
        
        plan = result.get("plan", [])
        
        # Sort by event_time
        def get_event_time(step):
            event_time = step.get("event_time")
            if event_time:
                try:
                    from datetime import datetime
                    if isinstance(event_time, str):
                        return datetime.fromisoformat(event_time.replace('Z', '+00:00'))
                    return event_time
                except:
                    return None
            return None
        
        # Sort: steps with event_time first (by time), then steps without event_time
        plan_with_time = [s for s in plan if get_event_time(s) is not None]
        plan_without_time = [s for s in plan if get_event_time(s) is None]
        
        plan_with_time.sort(key=get_event_time)
        
        sorted_plan = plan_with_time + plan_without_time
        
        return {
            "plan": sorted_plan,
            "updated_at": result.get("updated_at")
        }
    except Exception as e:
        print(f"[TRIP_PLAN_TOOLS] Error getting trip plan: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": True,
            "error_message": str(e),
            "plan": [],
            "updated_at": None
        }


async def clear_trip_plan_tool(email: str, session_id: str) -> Dict[str, Any]:
    """Clear the trip plan (reset to empty array).
    
    Args:
        email: User's email address
        session_id: Session identifier
        
    Returns:
        Dictionary with success status
    """
    try:
        success = await clear_trip_plan(email, session_id)
        
        if success:
            return {
                "success": True,
                "message": "Trip plan cleared successfully"
            }
        else:
            return {
                "success": False,
                "error": True,
                "error_message": "Failed to clear trip plan"
            }
    except Exception as e:
        print(f"[TRIP_PLAN_TOOLS] Error clearing trip plan: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": True,
            "error_message": str(e)
        }


async def delete_step_from_plan_tool(email: str, session_id: str, step_id: str) -> Dict[str, Any]:
    """Delete a specific step from the trip plan.
    
    Args:
        email: User's email address
        session_id: Session identifier
        step_id: ID of the step to delete
        
    Returns:
        Dictionary with success status and updated plan
    """
    try:
        # Get current plan
        current_plan_data = await get_trip_plan(email, session_id)
        current_plan = current_plan_data["plan"] if current_plan_data else []
        
        # Find and remove step
        updated_plan = [s for s in current_plan if s.get("id") != step_id]
        
        if len(updated_plan) == len(current_plan):
            # Step not found
            return {
                "success": False,
                "error": True,
                "error_message": f"Step with id '{step_id}' not found in plan"
            }
        
        # Save updated plan
        success = await upsert_trip_plan(email, session_id, updated_plan)
        
        if success:
            return {
                "success": True,
                "message": f"Step '{step_id}' deleted successfully",
                "plan": updated_plan
            }
        else:
            return {
                "success": False,
                "error": True,
                "error_message": "Failed to save updated trip plan"
            }
    except Exception as e:
        print(f"[TRIP_PLAN_TOOLS] Error deleting step: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": True,
            "error_message": str(e)
        }

