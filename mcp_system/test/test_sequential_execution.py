"""Test script to demonstrate sequential execution of agents."""

import asyncio
import sys
import os
import io

# Fix encoding for Windows console
if __name__ == "__main__":
    try:
        if hasattr(sys.stdout, 'buffer') and sys.stdout.buffer is not None:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except (AttributeError, ValueError, OSError):
        pass

# Add project root and langraph to path (go up 2 levels from mcp_system/test/ to project root)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
langraph_path = os.path.join(project_root, "langraph")
sys.path.insert(0, langraph_path)  # Add langraph first so relative imports work
sys.path.insert(0, project_root)   # Also add project root for other imports

from graph import run


async def test_simple_parallel():
    """Test case: Simple query where all agents can run in parallel."""
    print("\n" + "="*80)
    print("TEST 1: Simple parallel execution")
    print("="*80)
    print("Query: 'Find me flights and hotels to Paris'")
    print("Expected: 1 step with both agents running in parallel\n")
    
    result = await run("Find me flights and hotels to Paris")
    print("\n✅ Test 1 completed\n")


async def test_sequential_dependency():
    """Test case: Query requiring sequential execution."""
    print("\n" + "="*80)
    print("TEST 2: Sequential execution with dependencies")
    print("="*80)
    print("Query: 'What's the weather in Paris? Then find me hotels there.'")
    print("Expected: Step 1: utilities_agent (weather), Step 2: hotel_agent\n")
    
    result = await run("What's the weather in Paris? Then find me hotels there.")
    print("\n✅ Test 2 completed\n")


async def test_complex_multi_step():
    """Test case: Complex query with multiple sequential steps."""
    print("\n" + "="*80)
    print("TEST 3: Complex multi-step execution")
    print("="*80)
    print("Query: 'Find attractions in Rome, then search flights there, then find nearby hotels'")
    print("Expected: Multiple steps with dependencies\n")
    
    result = await run("Find attractions in Rome, then search flights there, then find nearby hotels")
    print("\n✅ Test 3 completed\n")


async def main():
    """Run all tests."""
    print("\n🚀 Starting Sequential Execution Tests")
    print("This will demonstrate the new multi-step execution system\n")
    
    # Test 1: Simple parallel execution
    await test_simple_parallel()
    
    # Test 2: Sequential dependency
    await test_sequential_dependency()
    
    # Test 3: Complex multi-step
    await test_complex_multi_step()
    
    print("\n" + "="*80)
    print("✅ All tests completed successfully!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())

