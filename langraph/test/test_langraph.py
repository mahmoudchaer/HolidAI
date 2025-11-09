"""Test script for LangGraph orchestration."""

import asyncio
import io
import os
import sys

# Fix encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph import run  # noqa: E402


async def test_langraph():
    """Test LangGraph orchestration."""
    print("=" * 60)
    print("Testing LangGraph Orchestration")
    print("=" * 60)
    
    try:
        # Test 1: Hotel search delegation
        print("\n1. Testing hotel search delegation...")
        result = await run("Search for hotels in Paris, France from 2025-12-10 to 2025-12-17 for 2 adults")
        print(f"✓ Route: {result.get('route')}")
        print(f"✓ Response: {result.get('last_response', 'N/A')[:200]}")
        
        # Test 2: General query (no delegation)
        print("\n2. Testing general query (no delegation)...")
        result = await run("Hello, what can you help me with?")
        print(f"✓ Route: {result.get('route')}")
        print(f"✓ Response: {result.get('last_response', 'N/A')[:200]}")
        
        # Test 3: Hotel search with specific location
        print("\n3. Testing hotel search with IATA code...")
        result = await run("Find hotels near JFK airport from 2025-12-01 to 2025-12-03 for 1 adult")
        print(f"✓ Route: {result.get('route')}")
        print(f"✓ Response: {result.get('last_response', 'N/A')[:200]}")
        
    except Exception as e:
        print(f"\n✗ Error testing LangGraph: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("LangGraph Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_langraph())

