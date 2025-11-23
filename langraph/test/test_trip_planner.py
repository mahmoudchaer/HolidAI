"""Tests for Trip Planner subsystem."""

import asyncio
import pytest
import sys
import os
from pathlib import Path

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.trip_plan_db import get_trip_plan, upsert_trip_plan, clear_trip_plan
from utils.trip_plan_tools import get_trip_plan_tool, clear_trip_plan_tool, delete_step_from_plan_tool
from nodes.trip_planner_node import trip_planner_node
from nodes.trip_planner_feedback_node import trip_planner_feedback_node
from state import AgentState


# Test data
TEST_EMAIL = "test@example.com"
TEST_SESSION_ID = "test-session-123"


@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def cleanup():
    """Clean up test data after each test."""
    yield
    # Clean up: clear trip plan after each test
    try:
        await clear_trip_plan(TEST_EMAIL, TEST_SESSION_ID)
    except:
        pass
    # No pool to close - connections are created per operation


class TestTripPlanDB:
    """Tests for trip plan database functions."""
    
    @pytest.mark.asyncio
    async def test_get_trip_plan_empty(self):
        """Test getting trip plan when none exists."""
        result = await get_trip_plan(TEST_EMAIL, TEST_SESSION_ID)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_upsert_trip_plan_insert(self):
        """Test inserting a new trip plan."""
        plan = [
            {
                "id": "flight_outbound",
                "type": "flight",
                "segment": "outbound",
                "title": "Flight to Paris",
                "details": {"airline": "Air France", "price": 500},
                "price": 500.0,
                "event_time": "2025-03-01T14:30:00Z",
                "status": "not_booked"
            }
        ]
        
        success = await upsert_trip_plan(TEST_EMAIL, TEST_SESSION_ID, plan)
        assert success is True
        
        # Verify it was saved
        result = await get_trip_plan(TEST_EMAIL, TEST_SESSION_ID)
        assert result is not None
        assert len(result["plan"]) == 1
        assert result["plan"][0]["id"] == "flight_outbound"
    
    @pytest.mark.asyncio
    async def test_upsert_trip_plan_update(self):
        """Test updating an existing trip plan."""
        # Insert initial plan
        initial_plan = [
            {
                "id": "flight_outbound",
                "type": "flight",
                "segment": "outbound",
                "title": "Flight to Paris",
                "details": {},
                "price": 500.0,
                "event_time": "2025-03-01T14:30:00Z",
                "status": "not_booked"
            }
        ]
        await upsert_trip_plan(TEST_EMAIL, TEST_SESSION_ID, initial_plan)
        
        # Update plan
        updated_plan = [
            {
                "id": "flight_outbound",
                "type": "flight",
                "segment": "outbound",
                "title": "Flight to Paris (Updated)",
                "details": {},
                "price": 450.0,
                "event_time": "2025-03-01T14:30:00Z",
                "status": "not_booked"
            },
            {
                "id": "hotel_1",
                "type": "hotel",
                "segment": None,
                "title": "Hotel in Paris",
                "details": {},
                "price": 200.0,
                "event_time": "2025-03-01T18:00:00Z",
                "status": "not_booked"
            }
        ]
        
        success = await upsert_trip_plan(TEST_EMAIL, TEST_SESSION_ID, updated_plan)
        assert success is True
        
        # Verify update
        result = await get_trip_plan(TEST_EMAIL, TEST_SESSION_ID)
        assert len(result["plan"]) == 2
        assert result["plan"][0]["title"] == "Flight to Paris (Updated)"
    
    @pytest.mark.asyncio
    async def test_clear_trip_plan(self):
        """Test clearing a trip plan."""
        # Insert plan
        plan = [
            {
                "id": "flight_outbound",
                "type": "flight",
                "segment": "outbound",
                "title": "Flight to Paris",
                "details": {},
                "price": 500.0,
                "event_time": "2025-03-01T14:30:00Z",
                "status": "not_booked"
            }
        ]
        await upsert_trip_plan(TEST_EMAIL, TEST_SESSION_ID, plan)
        
        # Clear plan
        success = await clear_trip_plan(TEST_EMAIL, TEST_SESSION_ID)
        assert success is True
        
        # Verify cleared
        result = await get_trip_plan(TEST_EMAIL, TEST_SESSION_ID)
        assert result is not None
        assert len(result["plan"]) == 0


class TestTripPlanTools:
    """Tests for trip plan tools."""
    
    @pytest.mark.asyncio
    async def test_get_trip_plan_tool(self):
        """Test get_trip_plan_tool."""
        # Insert plan with multiple steps
        plan = [
            {
                "id": "flight_outbound",
                "type": "flight",
                "segment": "outbound",
                "title": "Flight to Paris",
                "details": {},
                "price": 500.0,
                "event_time": "2025-03-02T14:30:00Z",
                "status": "not_booked"
            },
            {
                "id": "flight_return",
                "type": "flight",
                "segment": "return",
                "title": "Flight from Paris",
                "details": {},
                "price": 500.0,
                "event_time": "2025-03-01T10:00:00Z",  # Earlier time
                "status": "not_booked"
            },
            {
                "id": "hotel_1",
                "type": "hotel",
                "segment": None,
                "title": "Hotel in Paris",
                "details": {},
                "price": 200.0,
                "event_time": None,  # No event time
                "status": "not_booked"
            }
        ]
        await upsert_trip_plan(TEST_EMAIL, TEST_SESSION_ID, plan)
        
        # Get plan using tool
        result = await get_trip_plan_tool(TEST_EMAIL, TEST_SESSION_ID)
        
        assert "plan" in result
        assert len(result["plan"]) == 3
        # Should be sorted by event_time (return flight first, then outbound, then hotel)
        assert result["plan"][0]["id"] == "flight_return"  # Earliest event_time
        assert result["plan"][1]["id"] == "flight_outbound"
        assert result["plan"][2]["id"] == "hotel_1"  # No event_time, goes last
    
    @pytest.mark.asyncio
    async def test_clear_trip_plan_tool(self):
        """Test clear_trip_plan_tool."""
        # Insert plan
        plan = [{"id": "test", "type": "flight", "title": "Test"}]
        await upsert_trip_plan(TEST_EMAIL, TEST_SESSION_ID, plan)
        
        # Clear using tool
        result = await clear_trip_plan_tool(TEST_EMAIL, TEST_SESSION_ID)
        
        assert result["success"] is True
        
        # Verify cleared
        plan_data = await get_trip_plan(TEST_EMAIL, TEST_SESSION_ID)
        assert len(plan_data["plan"]) == 0
    
    @pytest.mark.asyncio
    async def test_delete_step_from_plan_tool(self):
        """Test delete_step_from_plan_tool."""
        # Insert plan with multiple steps
        plan = [
            {"id": "step1", "type": "flight", "title": "Step 1"},
            {"id": "step2", "type": "hotel", "title": "Step 2"},
            {"id": "step3", "type": "activity", "title": "Step 3"}
        ]
        await upsert_trip_plan(TEST_EMAIL, TEST_SESSION_ID, plan)
        
        # Delete step2
        result = await delete_step_from_plan_tool(TEST_EMAIL, TEST_SESSION_ID, "step2")
        
        assert result["success"] is True
        assert len(result["plan"]) == 2
        assert all(s["id"] != "step2" for s in result["plan"])
        
        # Verify in DB
        plan_data = await get_trip_plan(TEST_EMAIL, TEST_SESSION_ID)
        assert len(plan_data["plan"]) == 2
        assert all(s["id"] != "step2" for s in plan_data["plan"])


class TestTripPlannerNode:
    """Tests for trip_planner_node."""
    
    @pytest.mark.asyncio
    async def test_trip_planner_add_step(self):
        """Test adding a step to trip plan."""
        state: AgentState = {
            "user_message": "I'll take option 2 for the outbound flight",
            "session_id": TEST_SESSION_ID,
            "user_email": TEST_EMAIL,
            "trip_planner_result": None
        }
        
        # Mock STM data with previous agent message containing options
        from stm.short_term_memory import set_trip_plan_summary
        set_trip_plan_summary(TEST_SESSION_ID, {"steps": []})
        
        # Note: This test would require mocking the LLM call
        # For now, we'll test the structure
        # In a real test, you'd mock the OpenAI client
        
        # This is a placeholder - actual implementation would mock LLM
        pass
    
    @pytest.mark.asyncio
    async def test_trip_planner_update_step(self):
        """Test updating an existing step."""
        # Create initial plan
        initial_plan = [
            {
                "id": "flight_outbound",
                "type": "flight",
                "segment": "outbound",
                "title": "Flight to Paris",
                "details": {},
                "price": 500.0,
                "event_time": "2025-03-01T14:30:00Z",
                "status": "not_booked"
            }
        ]
        await upsert_trip_plan(TEST_EMAIL, TEST_SESSION_ID, initial_plan)
        
        state: AgentState = {
            "user_message": "Change my outbound flight to option 3",
            "session_id": TEST_SESSION_ID,
            "user_email": TEST_EMAIL,
            "trip_planner_result": None
        }
        
        # Mock STM and LLM for actual test
        # This is a placeholder
        pass
    
    @pytest.mark.asyncio
    async def test_trip_planner_delete_step(self):
        """Test deleting a step from trip plan."""
        # Create initial plan
        initial_plan = [
            {
                "id": "flight_outbound",
                "type": "flight",
                "segment": "outbound",
                "title": "Flight to Paris",
                "details": {},
                "price": 500.0,
                "event_time": "2025-03-01T14:30:00Z",
                "status": "not_booked"
            },
            {
                "id": "flight_return",
                "type": "flight",
                "segment": "return",
                "title": "Flight from Paris",
                "details": {},
                "price": 500.0,
                "event_time": "2025-03-10T14:30:00Z",
                "status": "not_booked"
            }
        ]
        await upsert_trip_plan(TEST_EMAIL, TEST_SESSION_ID, initial_plan)
        
        state: AgentState = {
            "user_message": "Delete the return flight",
            "session_id": TEST_SESSION_ID,
            "user_email": TEST_EMAIL,
            "trip_planner_result": None
        }
        
        # Mock STM and LLM for actual test
        # This is a placeholder
        pass


class TestTripPlannerFeedbackNode:
    """Tests for trip_planner_feedback_node."""
    
    @pytest.mark.asyncio
    async def test_feedback_success_add(self):
        """Test feedback node with successful add action."""
        state: AgentState = {
            "trip_planner_result": {
                "status": "success",
                "action": "add",
                "step_type": "flight",
                "segment": "outbound",
                "message": "Trip plan updated: add action completed"
            },
            "last_response": ""
        }
        
        # Mock LLM for actual test
        # This is a placeholder
        pass
    
    @pytest.mark.asyncio
    async def test_feedback_error_not_found(self):
        """Test feedback node with error (step not found)."""
        state: AgentState = {
            "trip_planner_result": {
                "status": "error",
                "action": "update",
                "step_id": "nonexistent",
                "message": "Step with id 'nonexistent' not found in plan"
            },
            "last_response": ""
        }
        
        # Mock LLM for actual test
        # This is a placeholder
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

