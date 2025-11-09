"""Run all tests for MCP agents."""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test.test_hotel_agent import test_hotel_agent
from test.test_permissions import test_permissions
from test.test_tripadvisor_agent import test_tripadvisor_agent
from test.test_visa_agent import test_visa_agent
from test.test_flight_agent import test_flight_agent


async def run_all_tests():
    """Run all test suites."""
    print("\n" + "=" * 60)
    print("Running All MCP Agent Tests")
    print("=" * 60)
    
    # Run Hotel Agent tests
    await test_hotel_agent()
    
    print("\n\n")
    
    # Run Permission tests
    await test_permissions()
    
    print("\n\n")
    
    # Run TripAdvisor Agent tests
    await test_tripadvisor_agent()
    
    print("\n\n")
    
    # Run Visa Agent tests
    await test_visa_agent()
    
    print("\n\n")
    
    # Run Flight Agent tests
    await test_flight_agent()
    
    print("\n" + "=" * 60)
    print("All Tests Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())

