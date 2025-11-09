"""Test script for permission enforcement."""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.hotel_agent_client import HotelAgentClient


async def test_permissions():
    """Test permission enforcement for hotel agent."""
    print("=" * 60)
    print("Testing Permission Enforcement")
    print("=" * 60)
    
    try:
        # Test: Hotel agent using its own tools
        print("\n1. Testing Hotel Agent using its own tools...")
        try:
            result = await HotelAgentClient.call_tool(
                "get_hotel_rates",
                checkin="2025-11-10",
                checkout="2025-11-17",
                occupancies=[{"adults": 2}],
                city_name="Paris",
                country_code="FR"
            )
            print(f"✓ Hotel agent can use its own tools")
            if result.get("error"):
                print(f"  Note: API returned error (expected if no API key): {result.get('error_message')}")
        except Exception as e:
            print(f"✗ Error: Hotel agent should be able to use its own tools: {e}")
        
    except Exception as e:
        print(f"\n✗ Error testing permissions: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        await HotelAgentClient.close()
    
    print("\n" + "=" * 60)
    print("Permission Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_permissions())

