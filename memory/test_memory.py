"""Simple script to test the memory system."""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from memory.memory_store import MemoryStore
from memory.memory_extraction import analyze_for_memory

def test_memory_system():
    """Test the memory system."""
    print("=" * 60)
    print("Testing Memory System")
    print("=" * 60)
    
    # Test user email
    test_email = "test@example.com"
    test_message = "I'm allergic to peanuts and prefer vegetarian restaurants"
    
    print(f"\n1. Testing memory extraction for message:")
    print(f"   '{test_message}'")
    print("-" * 60)
    
    try:
        # Test memory extraction
        analysis = analyze_for_memory(test_message)
        print(f"   Should write memory: {analysis['should_write_memory']}")
        print(f"   Memory text: {analysis['memory_to_write']}")
        print(f"   Importance: {analysis['importance']}")
        
        if not analysis['should_write_memory']:
            print("\n   [WARNING] Memory extraction didn't flag this as important.")
            print("   This might be normal - the LLM decides what's worth saving.")
            return
        
    except Exception as e:
        print(f"   [ERROR] Error in memory extraction: {e}")
        return
    
    print(f"\n2. Testing memory storage...")
    print("-" * 60)
    
    try:
        # Test memory store
        memory_store = MemoryStore()
        
        # Store memory
        memory_store.store_memory(
            user_email=test_email,
            fact_text=analysis['memory_to_write'],
            importance=analysis['importance']
        )
        print(f"   [OK] Memory stored successfully")
        
    except Exception as e:
        print(f"   [ERROR] Error storing memory: {e}")
        print(f"   Make sure Qdrant is running: docker-compose up -d qdrant")
        return
    
    print(f"\n3. Testing memory retrieval...")
    print("-" * 60)
    
    try:
        # Test retrieval
        query = "Find restaurants in Paris"
        memories = memory_store.get_relevant_memory(
            user_email=test_email,
            query=query,
            top_k=5
        )
        
        if memories:
            print(f"   [OK] Found {len(memories)} relevant memories:")
            for i, mem in enumerate(memories, 1):
                print(f"   {i}. {mem}")
        else:
            print(f"   [WARNING] No memories found (this might be normal if similarity is low)")
        
    except Exception as e:
        print(f"   [ERROR] Error retrieving memory: {e}")
        return
    
    print(f"\n4. Testing search with different query...")
    print("-" * 60)
    
    try:
        # Test with more relevant query
        query = "I need restaurant recommendations"
        memories = memory_store.get_relevant_memory(
            user_email=test_email,
            query=query,
            top_k=5
        )
        
        if memories:
            print(f"   [OK] Found {len(memories)} relevant memories:")
            for i, mem in enumerate(memories, 1):
                print(f"   {i}. {mem}")
        else:
            print(f"   [WARNING] No memories found")
        
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        return
    
    print("\n" + "=" * 60)
    print("[OK] Memory system test completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Start your Flask app: cd frontend && python app.py")
    print("2. Login and send a message with personal preferences")
    print("3. Check the logs for '[OK] Stored memory for...'")
    print("4. Send a related query and see if the agent remembers your preferences")


if __name__ == "__main__":
    test_memory_system()

