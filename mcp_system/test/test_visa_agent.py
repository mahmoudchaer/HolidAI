"""Test script for Visa Agent Client."""

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

from clients.visa_agent_client import VisaAgentClient


async def test_visa_agent():
    """Test Visa Agent Client."""
    print("=" * 60)
    print("Testing Visa Agent Client")
    print("=" * 60)
    
    try:
        # List tools
        visa_tools = await VisaAgentClient.list_tools()
        print(f"\n✓ Available tools: {[t['name'] for t in visa_tools]}")
        
        # Display tool descriptions
        print("\n📋 Tool Descriptions:")
        print("-" * 60)
        for tool in visa_tools:
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
        
        # Test 1: Basic visa requirement check
        print("\n1. Testing get_traveldoc_requirement (Lebanon to Qatar)...")
        print("   Note: This test uses browser automation and may take 30-60 seconds")
        result = await VisaAgentClient.call_tool(
            "get_traveldoc_requirement_tool",
            nationality="Lebanon",
            leaving_from="Lebanon",
            going_to="Qatar"
        )
        if not result.get("error"):
            visa_result = result.get("result", "")
            print(f"✓ Successfully retrieved visa requirements")
            print(f"  Nationality: {result.get('nationality')}")
            print(f"  Leaving from: {result.get('leaving_from')}")
            print(f"  Going to: {result.get('going_to')}")
            if visa_result:
                # Show first 300 characters of result
                preview = visa_result[:300] + "..." if len(visa_result) > 300 else visa_result
                print(f"  Result preview: {preview}")
        else:
            print(f"✗ Error: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 2: US to France
        print("\n2. Testing get_traveldoc_requirement (United States to France)...")
        print("   Note: This test uses browser automation and may take 30-60 seconds")
        result = await VisaAgentClient.call_tool(
            "get_traveldoc_requirement_tool",
            nationality="United States",
            leaving_from="United States",
            going_to="France"
        )
        if not result.get("error"):
            print(f"✓ Successfully retrieved visa requirements")
            print(f"  Nationality: {result.get('nationality')}")
            print(f"  Leaving from: {result.get('leaving_from')}")
            print(f"  Going to: {result.get('going_to')}")
            visa_result = result.get("result", "")
            if visa_result:
                preview = visa_result[:200] + "..." if len(visa_result) > 200 else visa_result
                print(f"  Result preview: {preview}")
        else:
            print(f"✗ Error: {result.get('error_message')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test error handling
        print("\n" + "=" * 60)
        print("Testing Error Handling")
        print("=" * 60)
        
        # Test 3: Validation error - missing nationality
        print("\n3. Testing validation error (missing nationality)...")
        result = await VisaAgentClient.call_tool(
            "get_traveldoc_requirement_tool",
            nationality="",
            leaving_from="Lebanon",
            going_to="Qatar"
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 4: Validation error - missing leaving_from
        print("\n4. Testing validation error (missing leaving_from)...")
        result = await VisaAgentClient.call_tool(
            "get_traveldoc_requirement_tool",
            nationality="Lebanon",
            leaving_from="",
            going_to="Qatar"
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 5: Validation error - missing going_to
        print("\n5. Testing validation error (missing going_to)...")
        result = await VisaAgentClient.call_tool(
            "get_traveldoc_requirement_tool",
            nationality="Lebanon",
            leaving_from="Lebanon",
            going_to=""
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 6: Test permission enforcement (try to call hotel tool)
        print("\n6. Testing permission enforcement (try to call unauthorized tool)...")
        try:
            result = await VisaAgentClient.call_tool(
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
        print(f"\n✗ Error testing Visa Agent: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        await VisaAgentClient.close()
    
    print("\n" + "=" * 60)
    print("Visa Agent Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_visa_agent())

