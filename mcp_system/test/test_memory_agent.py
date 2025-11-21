"""Test script for Memory Agent Client."""

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

from clients.memory_agent_client import MemoryAgentClient


async def test_memory_agent():
    """Test Memory Agent Client."""
    print("=" * 60)
    print("Testing Memory Agent Client")
    print("=" * 60)
    
    # Test user email (for testing purposes)
    test_user_email = "test@example.com"
    
    try:
        # List tools
        memory_tools = await MemoryAgentClient.list_tools()
        print(f"\n✓ Available tools: {[t['name'] for t in memory_tools]}")
        
        # Display tool descriptions
        print("\n📋 Tool Descriptions:")
        print("-" * 60)
        for tool in memory_tools:
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
        
        # Test 1: Analyze message for memory extraction (should store)
        print("\n1. Testing agent_analyze_memory_tool (message with preference)...")
        result = await MemoryAgentClient.call_tool(
            "agent_analyze_memory_tool",
            message="I prefer morning flights when traveling"
        )
        if result:
            should_write = result.get("should_write_memory", False)
            importance = result.get("importance", 1)
            memory_text = result.get("memory_to_write", "")
            print(f"✓ Analysis result:")
            print(f"  Should write memory: {should_write}")
            print(f"  Importance: {importance}")
            if memory_text:
                print(f"  Memory text: {memory_text[:60]}...")
            if should_write:
                print(f"  → This message should be stored in memory")
            else:
                print(f"  → This message should NOT be stored")
        else:
            print(f"✗ Error: No result returned")
        
        # Test 2: Analyze message that should NOT be stored
        print("\n2. Testing agent_analyze_memory_tool (casual greeting - should not store)...")
        result = await MemoryAgentClient.call_tool(
            "agent_analyze_memory_tool",
            message="Hello, how are you?"
        )
        if result:
            should_write = result.get("should_write_memory", False)
            print(f"✓ Analysis result:")
            print(f"  Should write memory: {should_write}")
            if not should_write:
                print(f"  → Correctly identified as non-memory message")
            else:
                print(f"  → WARNING: Should not be stored but analysis says it should")
        else:
            print(f"✗ Error: No result returned")
        
        # Test 3: Analyze message for update
        print("\n3. Testing agent_analyze_memory_tool (update preference)...")
        result = await MemoryAgentClient.call_tool(
            "agent_analyze_memory_tool",
            message="I no longer prefer morning flights, I now prefer evening flights"
        )
        if result:
            should_write = result.get("should_write_memory", False)
            is_update = result.get("is_update", False)
            old_memory = result.get("old_memory_text", "")
            new_memory = result.get("memory_to_write", "")
            print(f"✓ Analysis result:")
            print(f"  Should write memory: {should_write}")
            print(f"  Is update: {is_update}")
            if old_memory:
                print(f"  Old memory: {old_memory[:60]}...")
            if new_memory:
                print(f"  New memory: {new_memory[:60]}...")
            if is_update:
                print(f"  → Correctly identified as memory update")
        else:
            print(f"✗ Error: No result returned")
        
        # Test 4: Analyze message for deletion
        print("\n4. Testing agent_analyze_memory_tool (delete preference)...")
        result = await MemoryAgentClient.call_tool(
            "agent_analyze_memory_tool",
            message="Forget that I prefer morning flights"
        )
        if result:
            should_write = result.get("should_write_memory", False)
            is_deletion = result.get("is_deletion", False)
            old_memory = result.get("old_memory_text", "")
            print(f"✓ Analysis result:")
            print(f"  Should write memory: {should_write}")
            print(f"  Is deletion: {is_deletion}")
            if old_memory:
                print(f"  Memory to delete: {old_memory[:60]}...")
            if is_deletion:
                print(f"  → Correctly identified as memory deletion")
        else:
            print(f"✗ Error: No result returned")
        
        # Test 5: Store a new memory
        print("\n5. Testing agent_store_memory_tool (store new memory)...")
        result = await MemoryAgentClient.call_tool(
            "agent_store_memory_tool",
            user_email=test_user_email,
            fact_text="User prefers vegetarian restaurants",
            importance=4
        )
        if result:
            success = result.get("success", False)
            message = result.get("message", "")
            print(f"✓ Store result:")
            print(f"  Success: {success}")
            print(f"  Message: {message}")
            if success:
                print(f"  → Memory stored successfully")
            else:
                print(f"  → Failed to store memory")
        else:
            print(f"✗ Error: No result returned")
        
        # Test 6: Store another memory
        print("\n6. Testing agent_store_memory_tool (store another memory)...")
        result = await MemoryAgentClient.call_tool(
            "agent_store_memory_tool",
            user_email=test_user_email,
            fact_text="User prefers morning flights",
            importance=5
        )
        if result:
            success = result.get("success", False)
            print(f"✓ Store result: Success = {success}")
        else:
            print(f"✗ Error: No result returned")
        
        # Test 7: Retrieve relevant memories
        print("\n7. Testing agent_get_relevant_memories_tool (retrieve memories for flight query)...")
        result = await MemoryAgentClient.call_tool(
            "agent_get_relevant_memories_tool",
            user_email=test_user_email,
            query="I need to book a flight",
            top_k=5
        )
        if result:
            memories = result.get("memories", [])
            count = result.get("count", 0)
            print(f"✓ Retrieve result:")
            print(f"  Memories found: {count}")
            if memories:
                print(f"  Retrieved memories:")
                for i, mem in enumerate(memories, 1):
                    print(f"    {i}. {mem[:60]}...")
            else:
                print(f"  → No relevant memories found")
        else:
            print(f"✗ Error: No result returned")
        
        # Test 8: Update an existing memory
        print("\n8. Testing agent_update_memory_tool (update existing memory)...")
        result = await MemoryAgentClient.call_tool(
            "agent_update_memory_tool",
            user_email=test_user_email,
            old_fact_text="User prefers morning flights",
            new_fact_text="User prefers evening flights",
            new_importance=5
        )
        if result:
            success = result.get("success", False)
            message = result.get("message", "")
            print(f"✓ Update result:")
            print(f"  Success: {success}")
            print(f"  Message: {message}")
            if success:
                print(f"  → Memory updated successfully")
            else:
                print(f"  → Failed to update memory (might not exist)")
        else:
            print(f"✗ Error: No result returned")
        
        # Test 9: Retrieve memories again to verify update
        print("\n9. Testing agent_get_relevant_memories_tool (verify update)...")
        result = await MemoryAgentClient.call_tool(
            "agent_get_relevant_memories_tool",
            user_email=test_user_email,
            query="flight preferences",
            top_k=5
        )
        if result:
            memories = result.get("memories", [])
            print(f"✓ Retrieve result: {len(memories)} memories found")
            if memories:
                print(f"  Updated memory should be in results:")
                for i, mem in enumerate(memories, 1):
                    print(f"    {i}. {mem[:60]}...")
                    if "evening" in mem.lower():
                        print(f"      → Found updated memory (evening flights)")
        else:
            print(f"✗ Error: No result returned")
        
        # Test 10: Delete a memory
        print("\n10. Testing agent_delete_memory_tool (delete memory)...")
        result = await MemoryAgentClient.call_tool(
            "agent_delete_memory_tool",
            user_email=test_user_email,
            fact_text="User prefers vegetarian restaurants"
        )
        if result:
            success = result.get("success", False)
            message = result.get("message", "")
            print(f"✓ Delete result:")
            print(f"  Success: {success}")
            print(f"  Message: {message}")
            if success:
                print(f"  → Memory deleted successfully")
            else:
                print(f"  → Failed to delete memory (might not exist)")
        else:
            print(f"✗ Error: No result returned")
        
        # Test 11: Verify deletion
        print("\n11. Testing agent_get_relevant_memories_tool (verify deletion)...")
        result = await MemoryAgentClient.call_tool(
            "agent_get_relevant_memories_tool",
            user_email=test_user_email,
            query="restaurant preferences",
            top_k=5
        )
        if result:
            memories = result.get("memories", [])
            print(f"✓ Retrieve result: {len(memories)} memories found")
            vegetarian_found = any("vegetarian" in mem.lower() for mem in memories)
            if not vegetarian_found:
                print(f"  → Deleted memory not found (deletion successful)")
            else:
                print(f"  → WARNING: Deleted memory still appears in results")
        else:
            print(f"✗ Error: No result returned")
        
        # Test error handling
        print("\n" + "=" * 60)
        print("Testing Error Handling")
        print("=" * 60)
        
        # Test 12: Store memory with invalid importance (should still work, but test edge cases)
        print("\n12. Testing agent_store_memory_tool (with importance=1 - low priority)...")
        result = await MemoryAgentClient.call_tool(
            "agent_store_memory_tool",
            user_email=test_user_email,
            fact_text="User likes coffee",
            importance=1
        )
        if result:
            success = result.get("success", False)
            print(f"✓ Store result: Success = {success} (low importance memory)")
        else:
            print(f"✗ Error: No result returned")
        
        # Test 13: Retrieve memories for different user (should return empty)
        print("\n13. Testing agent_get_relevant_memories_tool (different user - should be empty)...")
        result = await MemoryAgentClient.call_tool(
            "agent_get_relevant_memories_tool",
            user_email="different@example.com",
            query="flight preferences",
            top_k=5
        )
        if result:
            memories = result.get("memories", [])
            print(f"✓ Retrieve result: {len(memories)} memories found")
            if len(memories) == 0:
                print(f"  → Correctly returned empty for different user")
            else:
                print(f"  → WARNING: Found memories for different user (privacy issue!)")
        else:
            print(f"✗ Error: No result returned")
        
        # Test 14: Update non-existent memory
        print("\n14. Testing agent_update_memory_tool (non-existent memory)...")
        result = await MemoryAgentClient.call_tool(
            "agent_update_memory_tool",
            user_email=test_user_email,
            old_fact_text="This memory does not exist",
            new_fact_text="New memory text",
            new_importance=3
        )
        if result:
            success = result.get("success", False)
            print(f"✓ Update result: Success = {success}")
            if not success:
                print(f"  → Correctly failed to update non-existent memory")
            else:
                print(f"  → WARNING: Updated non-existent memory (unexpected)")
        else:
            print(f"✗ Error: No result returned")
        
        # Test 15: Delete non-existent memory
        print("\n15. Testing agent_delete_memory_tool (non-existent memory)...")
        result = await MemoryAgentClient.call_tool(
            "agent_delete_memory_tool",
            user_email=test_user_email,
            fact_text="This memory does not exist"
        )
        if result:
            success = result.get("success", False)
            print(f"✓ Delete result: Success = {success}")
            if not success:
                print(f"  → Correctly failed to delete non-existent memory")
            else:
                print(f"  → WARNING: Deleted non-existent memory (unexpected)")
        else:
            print(f"✗ Error: No result returned")
        
        # Test 16: Test permission enforcement (try to call flight tool)
        print("\n16. Testing permission enforcement (try to call unauthorized tool)...")
        try:
            result = await MemoryAgentClient.call_tool(
                "agent_get_flights_tool",
                trip_type="one-way",
                departure="JFK",
                arrival="LAX",
                departure_date="2025-12-10"
            )
            print(f"✗ Expected PermissionError but got: {result}")
        except PermissionError as e:
            print(f"✓ Permission error caught: {str(e)}")
        except Exception as e:
            # Might also get an error from the server
            print(f"✓ Error caught (expected): {type(e).__name__}: {str(e)}")
        
        # Test 17: Retrieve memories with empty query
        print("\n17. Testing agent_get_relevant_memories_tool (empty query)...")
        result = await MemoryAgentClient.call_tool(
            "agent_get_relevant_memories_tool",
            user_email=test_user_email,
            query="",
            top_k=5
        )
        if result:
            memories = result.get("memories", [])
            print(f"✓ Retrieve result: {len(memories)} memories found (empty query)")
        else:
            print(f"✗ Error: No result returned")
        
        # Test 18: Retrieve memories with very high top_k
        print("\n18. Testing agent_get_relevant_memories_tool (top_k=20)...")
        result = await MemoryAgentClient.call_tool(
            "agent_get_relevant_memories_tool",
            user_email=test_user_email,
            query="preferences",
            top_k=20
        )
        if result:
            memories = result.get("memories", [])
            print(f"✓ Retrieve result: {len(memories)} memories found (requested top 20)")
        else:
            print(f"✗ Error: No result returned")
        
    except Exception as e:
        print(f"\n✗ Error testing Memory Agent: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        await MemoryAgentClient.close()
    
    print("\n" + "=" * 60)
    print("Memory Agent Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_memory_agent())

