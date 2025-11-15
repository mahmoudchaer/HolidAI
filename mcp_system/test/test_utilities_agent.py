"""Test script for Utilities Agent Client."""

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

from clients.utilities_agent_client import UtilitiesAgentClient


async def test_utilities_agent():
    """Test Utilities Agent Client."""
    print("=" * 60)
    print("Testing Utilities Agent Client")
    print("=" * 60)
    
    try:
        # List tools
        utilities_tools = await UtilitiesAgentClient.list_tools()
        print(f"\n✓ Available tools: {[t['name'] for t in utilities_tools]}")
        
        # Display tool descriptions
        print("\n📋 Tool Descriptions:")
        print("-" * 60)
        for tool in utilities_tools:
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
        
        # Test 1: Weather
        print("\n1. Testing get_real_time_weather (New York)...")
        result = await UtilitiesAgentClient.call_tool(
            "get_real_time_weather",
            location="New York"
        )
        if not result.get("error"):
            print(f"✓ Successfully retrieved weather")
            print(f"  Location: {result.get('location')}")
            print(f"  Temperature: {result.get('temperature')}°C")
            print(f"  Description: {result.get('description')}")
            print(f"  Humidity: {result.get('humidity')}%")
        else:
            print(f"✗ Error: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        
        # Test 2: Currency conversion
        print("\n2. Testing convert_currencies (USD to EUR, 100)...")
        result = await UtilitiesAgentClient.call_tool(
            "convert_currencies",
            from_currency="USD",
            to_currency="EUR",
            amount=100
        )
        if not result.get("error"):
            print(f"✓ Successfully converted currency")
            print(f"  {result.get('amount')} {result.get('from_currency')} = {result.get('converted_amount')} {result.get('to_currency')}")
            print(f"  Exchange rate: {result.get('exchange_rate')}")
        else:
            print(f"✗ Error: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        
        # Test 3: Date/Time
        print("\n3. Testing get_real_time_date_time (Tokyo)...")
        result = await UtilitiesAgentClient.call_tool(
            "get_real_time_date_time",
            location="Tokyo"
        )
        if not result.get("error"):
            print(f"✓ Successfully retrieved date/time")
            print(f"  Location: {result.get('location')}")
            print(f"  Date: {result.get('date')}")
            print(f"  Time: {result.get('time')}")
            print(f"  Timezone: {result.get('timezone')}")
        else:
            print(f"✗ Error: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 4: eSIM bundles
        print("\n4. Testing get_esim_bundles (Qatar)...")
        print("   Note: This test scrapes esimradar.com and may take a few seconds")
        result = await UtilitiesAgentClient.call_tool(
            "get_esim_bundles",
            country="Qatar"
        )
        if not result.get("error"):
            bundles = result.get("bundles", [])
            print(f"✓ Successfully retrieved eSIM bundles")
            print(f"  Country: {result.get('country')}")
            print(f"  Bundles found: {result.get('count')}")
            if bundles:
                # Show first bundle
                first_bundle = bundles[0]
                print(f"  First bundle:")
                print(f"    Provider: {first_bundle.get('provider')}")
                print(f"    Plan: {first_bundle.get('plan')}")
                print(f"    Price: {first_bundle.get('price')}")
                print(f"    Validity: {first_bundle.get('validity')}")
        else:
            print(f"✗ Error: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 5: Holidays (if API key is configured)
        print("\n5. Testing get_holidays (USA, 2024)...")
        result = await UtilitiesAgentClient.call_tool(
            "get_holidays",
            country="USA",
            year=2024
        )
        if not result.get("error"):
            holidays = result.get("holidays", [])
            print(f"✓ Successfully retrieved holidays")
            print(f"  Country: {result.get('country')} ({result.get('country_code')})")
            print(f"  Year: {result.get('year')}")
            print(f"  Holidays found: {result.get('count')}")
            if holidays:
                # Show first few holidays
                print(f"  Sample holidays:")
                for i, holiday in enumerate(holidays[:5], 1):
                    print(f"    {i}. {holiday.get('name')} - {holiday.get('date')}")
        else:
            error_code = result.get('error_code')
            if error_code == "API_KEY_MISSING":
                print(f"⚠ Skipped: {result.get('error_message')}")
                print(f"  Suggestion: {result.get('suggestion')}")
            else:
                print(f"✗ Error: {result.get('error_message')}")
                print(f"  Error code: {error_code}")
        
        # Test 6: Holidays with month filter
        print("\n6. Testing get_holidays (Qatar, December 2024)...")
        result = await UtilitiesAgentClient.call_tool(
            "get_holidays",
            country="Qatar",
            year=2024,
            month=12
        )
        if not result.get("error"):
            holidays = result.get("holidays", [])
            print(f"✓ Successfully retrieved holidays for December")
            print(f"  Holidays found: {result.get('count')}")
            if holidays:
                for holiday in holidays:
                    print(f"    • {holiday.get('name')} - {holiday.get('date')}")
        else:
            error_code = result.get('error_code')
            if error_code == "API_KEY_MISSING":
                print(f"⚠ Skipped: {result.get('error_message')}")
            else:
                print(f"✗ Error: {result.get('error_message')}")
        
        # Test error handling
        print("\n" + "=" * 60)
        print("Testing Error Handling")
        print("=" * 60)
        
        # Test 7: Invalid currency code
        print("\n7. Testing validation error (invalid currency code)...")
        result = await UtilitiesAgentClient.call_tool(
            "convert_currencies",
            from_currency="INVALID",
            to_currency="EUR",
            amount=100
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 8: Invalid country for eSIM
        print("\n8. Testing validation error (invalid country for eSIM)...")
        result = await UtilitiesAgentClient.call_tool(
            "get_esim_bundles",
            country="InvalidCountry123"
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 9: Invalid year for holidays
        print("\n9. Testing validation error (invalid year for holidays)...")
        result = await UtilitiesAgentClient.call_tool(
            "get_holidays",
            country="USA",
            year=1999  # Too old
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"⚠ Note: API may accept this, but validation should catch it")
        
        # Test 10: Test permission enforcement (try to call hotel tool)
        print("\n10. Testing permission enforcement (try to call unauthorized tool)...")
        try:
            result = await UtilitiesAgentClient.call_tool(
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
        print(f"\n✗ Error testing Utilities Agent: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        await UtilitiesAgentClient.close()
    
    print("\n" + "=" * 60)
    print("Utilities Agent Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_utilities_agent())

