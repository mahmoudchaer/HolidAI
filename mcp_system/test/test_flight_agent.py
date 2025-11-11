"""Test script for Flight Agent Client."""

import asyncio
import io
import sys
import os

# Fix encoding for Windows console (only if buffer is available and when run directly)
if __name__ == "__main__":
    try:
        if hasattr(sys.stdout, 'buffer') and sys.stdout.buffer is not None:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except (AttributeError, ValueError, OSError):
        # If buffer is not available or closed, skip encoding fix
        pass

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.flight_agent_client import FlightAgentClient


async def test_flight_agent():
    """Test Flight Agent Client."""
    print("=" * 60)
    print("Testing Flight Agent Client")
    print("=" * 60)
    
    try:
        # List tools
        flight_tools = await FlightAgentClient.list_tools()
        print(f"\n✓ Available tools: {[t['name'] for t in flight_tools]}")
        
        # Display tool descriptions
        print("\n📋 Tool Descriptions:")
        print("-" * 60)
        for tool in flight_tools:
            print(f"\n  • {tool['name']}:")
            description = tool.get('description', 'N/A')
            # Show first line of description (main description)
            desc_lines = description.split('\n')
            main_desc = desc_lines[0].strip()
            print(f"    Description: {main_desc}")
            if 'inputSchema' in tool and 'properties' in tool['inputSchema']:
                params = list(tool['inputSchema']['properties'].keys())
                required = tool['inputSchema'].get('required', [])
                print(f"    Parameters: {', '.join(params)}")
                if required:
                    print(f"    Required: {', '.join(required)}")
        
        # Test tools
        print("\n" + "=" * 60)
        print("Testing Tools")
        print("=" * 60)
        
        # Test 1: One-way flight search
        print("\n1. Testing agent_get_flights (one-way, JFK to LAX)...")
        print("   Note: This test uses SerpAPI and may take 10-30 seconds")
        result = await FlightAgentClient.call_tool(
            "agent_get_flights",
            trip_type="one-way",
            departure="JFK",
            arrival="LAX",
            departure_date="2025-12-10",
            adults=1,
            travel_class="economy"
        )
        if not result.get("error"):
            outbound = result.get("outbound", [])
            print(f"✓ Successfully retrieved flight search results")
            print(f"  Trip type: {result.get('trip_type')}")
            print(f"  Route: {result.get('departure')} → {result.get('arrival')}")
            print(f"  Departure date: {result.get('departure_date')}")
            print(f"  Outbound flights found: {len(outbound)}")
            if outbound:
                # Show first flight details
                first_flight = outbound[0]
                price = first_flight.get("price", "N/A")
                print(f"  First flight price: {price}")
                if "flights" in first_flight and len(first_flight["flights"]) > 0:
                    first_leg = first_flight["flights"][0]
                    airline = first_leg.get("airline", "N/A")
                    print(f"  First flight airline: {airline}")
        else:
            print(f"✗ Error: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 2: Round-trip flight search
        print("\n2. Testing agent_get_flights (round-trip, NYC to LHR)...")
        print("   Note: This test uses SerpAPI and may take 10-30 seconds")
        result = await FlightAgentClient.call_tool(
            "agent_get_flights",
            trip_type="round-trip",
            departure="NYC",
            arrival="LHR",
            departure_date="2025-12-10",
            arrival_date="2025-12-17",
            adults=2,
            travel_class="economy"
        )
        if not result.get("error"):
            outbound = result.get("outbound", [])
            return_flights = result.get("return", [])
            print(f"✓ Successfully retrieved round-trip flight search results")
            print(f"  Outbound flights found: {len(outbound)}")
            print(f"  Return flights found: {len(return_flights)}")
            if outbound:
                price = outbound[0].get("price", "N/A")
                print(f"  First outbound flight price: {price}")
        else:
            print(f"✗ Error: {result.get('error_message')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 3: Flexible flight search
        print("\n3. Testing agent_get_flights_flexible (one-way, JFK to LAX, ±3 days)...")
        print("   Note: This test uses SerpAPI and may take 30-60 seconds (searches multiple dates)")
        result = await FlightAgentClient.call_tool(
            "agent_get_flights_flexible",
            trip_type="one-way",
            departure="JFK",
            arrival="LAX",
            departure_date="2025-12-10",
            days_flex=3,
            adults=1,
            travel_class="economy"
        )
        if not result.get("error"):
            flights = result.get("flights", [])
            print(f"✓ Successfully retrieved flexible flight search results")
            print(f"  Days flexibility: {result.get('days_flex')}")
            print(f"  Total flights found across dates: {len(flights)}")
            if flights:
                # Show first few flights with their search dates
                print(f"  Sample flights:")
                for i, flight in enumerate(flights[:3], 1):
                    price = flight.get("price", "N/A")
                    search_date = flight.get("search_date", "N/A")
                    print(f"    {i}. Date: {search_date}, Price: {price}")
        else:
            print(f"✗ Error: {result.get('error_message')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test error handling
        print("\n" + "=" * 60)
        print("Testing Error Handling")
        print("=" * 60)
        
        # Test 4: Validation error - missing departure
        print("\n4. Testing validation error (missing departure)...")
        result = await FlightAgentClient.call_tool(
            "agent_get_flights",
            trip_type="one-way",
            departure="",
            arrival="LAX",
            departure_date="2025-12-10"
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 5: Validation error - missing arrival_date for round-trip
        print("\n5. Testing validation error (missing arrival_date for round-trip)...")
        result = await FlightAgentClient.call_tool(
            "agent_get_flights",
            trip_type="round-trip",
            departure="JFK",
            arrival="LAX",
            departure_date="2025-12-10"
            # Missing arrival_date
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 6: Validation error - invalid trip_type
        print("\n6. Testing validation error (invalid trip_type)...")
        result = await FlightAgentClient.call_tool(
            "agent_get_flights",
            trip_type="invalid",
            departure="JFK",
            arrival="LAX",
            departure_date="2025-12-10"
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 7: Validation error - invalid date format
        print("\n7. Testing validation error (invalid date format)...")
        result = await FlightAgentClient.call_tool(
            "agent_get_flights",
            trip_type="one-way",
            departure="JFK",
            arrival="LAX",
            departure_date="12/10/2025"  # Wrong format
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 8: Validation error - invalid days_flex
        print("\n8. Testing agent_get_flights_flexible validation error (days_flex > 7)...")
        result = await FlightAgentClient.call_tool(
            "agent_get_flights_flexible",
            trip_type="one-way",
            departure="JFK",
            arrival="LAX",
            departure_date="2025-12-10",
            days_flex=10  # Too large
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 9: Test permission enforcement (try to call hotel tool)
        print("\n9. Testing permission enforcement (try to call unauthorized tool)...")
        try:
            result = await FlightAgentClient.call_tool(
                "get_hotel_rates",
                checkin="2025-12-10",
                checkout="2025-12-17",
                occupancies=[{"adults": 2}],
                city_name="Paris",
                country_code="FR"
            )
            print(f"✗ Expected PermissionError but got: {result}")
        except PermissionError as e:
            print(f"✓ Permission error caught: {str(e)}")
        except Exception as e:
            # Might also get an error from the server
            print(f"✓ Error caught (expected): {type(e).__name__}: {str(e)}")
        
    except Exception as e:
        print(f"\n✗ Error testing Flight Agent: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        await FlightAgentClient.close()
    
    print("\n" + "=" * 60)
    print("Flight Agent Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_flight_agent())

