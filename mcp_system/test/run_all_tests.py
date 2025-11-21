"""Run all tests for MCP agents."""

import asyncio
import sys
import os
import io
from contextlib import redirect_stdout, redirect_stderr

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test.test_hotel_agent import test_hotel_agent
from test.test_permissions import test_permissions
from test.test_tripadvisor_agent import test_tripadvisor_agent
from test.test_visa_agent import test_visa_agent
from test.test_flight_agent import test_flight_agent
from test.test_utilities_agent import test_utilities_agent
from test.test_memory_agent import test_memory_agent


async def run_test_with_capture(test_func, test_name):
    """Run a test function and capture its output."""
    output = io.StringIO()
    error_output = io.StringIO()
    success = False
    error_message = None
    
    try:
        with redirect_stdout(output), redirect_stderr(error_output):
            await test_func()
        success = True
    except Exception as e:
        error_message = str(e)
        import traceback
        error_output.write(traceback.format_exc())
    
    captured_output = output.getvalue()
    captured_errors = error_output.getvalue()
    
    return {
        'name': test_name,
        'success': success,
        'output': captured_output,
        'error': error_message,
        'error_output': captured_errors
    }


async def run_all_tests():
    """Run all test suites with clean summary output."""
    print("\n" + "=" * 70)
    print("MCP Agent Test Suite")
    print("=" * 70)
    print()
    
    # Define all tests
    tests = [
        (test_hotel_agent, "Hotel Agent"),
        (test_permissions, "Permissions"),
        (test_tripadvisor_agent, "TripAdvisor Agent"),
        (test_visa_agent, "Visa Agent"),
        (test_flight_agent, "Flight Agent"),
        (test_utilities_agent, "Utilities Agent"),
        (test_memory_agent, "Memory Agent"),
    ]
    
    results = []
    
    # Run all tests
    for test_func, test_name in tests:
        print(f"Running {test_name}...", end=" ", flush=True)
        result = await run_test_with_capture(test_func, test_name)
        results.append(result)
        
        if result['success']:
            print("✓ PASSED")
        else:
            print("✗ FAILED")
    
    # Print summary
    passed = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    if failed:
        print("\n" + "=" * 70)
        print("✗ FAILED:")
        for result in failed:
            print(f"  • {result['name']}")
            if result['error']:
                print(f"    Error: {result['error']}")
    
    print("\n" + "=" * 70)
    print(f"Total: {len(results)} | Passed: {len(passed)} | Failed: {len(failed)}")
    print("=" * 70)
    
    # Show details for failed tests
    if failed:
        print("\n" + "=" * 70)
        print("Failed Test Details")
        print("=" * 70)
        print()
        for result in failed:
            print(f"\n{result['name']}:")
            print("-" * 70)
            if result['error_output']:
                # Show only the last 50 lines of error output to avoid clutter
                error_lines = result['error_output'].split('\n')
                if len(error_lines) > 50:
                    print("... (showing last 50 lines) ...")
                    error_lines = error_lines[-50:]
                print('\n'.join(error_lines))
            elif result['error']:
                print(result['error'])
            else:
                print("Test failed but no error details available.")
    
    # Return exit code
    return 0 if len(failed) == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)

