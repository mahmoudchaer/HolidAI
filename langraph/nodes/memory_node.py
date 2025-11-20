"""Memory node for LangGraph - handles both memory retrieval and storage."""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".."))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import AgentState

# Load environment variables from .env file in main directory
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)


async def memory_node(state: AgentState) -> AgentState:
    """Memory node that handles both memory retrieval and storage.
    
    This node:
    1. Analyzes the user message to determine if it should be stored
    2. Stores new memories if important
    3. Retrieves relevant memories for the current query
    4. Updates state with relevant_memories
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with relevant_memories populated
    """
    from datetime import datetime
    start_time = datetime.now()
    print(f"[{start_time.strftime('%H:%M:%S.%f')[:-3]}] [MEMORY] MEMORY NODE STARTED")
    print(f"[MEMORY] State keys: {list(state.keys())}")
    print(f"[MEMORY] user_email: {state.get('user_email')}")
    print(f"[MEMORY] rfi_next_route: {state.get('rfi_next_route')}")
    
    user_message = state.get("user_message", "")
    user_email = state.get("user_email")
    
    # Initialize relevant_memories as empty list
    relevant_memories = []
    
    # If no user email, skip memory operations
    if not user_email:
        print("[MEMORY] No user_email in state, skipping memory operations")
        updated_state = state.copy()
        updated_state["relevant_memories"] = []
        return updated_state
    
    try:
        from memory.memory_store import MemoryStore
        from memory.memory_extraction import analyze_for_memory
        
        memory_store = MemoryStore()
        
        # Step 1: Analyze message for memory extraction
        try:
            print(f"[MEMORY] Analyzing message for memory extraction: {user_message[:80]}...")
            memory_analysis = analyze_for_memory(user_message)
            
            # Step 2: Handle memory operations (store/update/delete)
            if memory_analysis.get("should_write_memory") and memory_analysis.get("memory_to_write"):
                try:
                    is_deletion = memory_analysis.get("is_deletion", False)
                    is_update = memory_analysis.get("is_update", False)
                    old_memory_text = memory_analysis.get("old_memory_text", "")
                    
                    if is_deletion and old_memory_text:
                        # Delete the old memory
                        print(f"[MEMORY] Deleting memory: {old_memory_text[:70]}...")
                        similar_memories = memory_store.find_similar_memories(user_email, old_memory_text, similarity_threshold=0.7)
                        if similar_memories:
                            # Delete the most similar memory
                            deleted = memory_store.delete_memory(user_email, similar_memories[0]["id"])
                            if deleted:
                                print(f"[MEMORY] Successfully deleted memory")
                            else:
                                print(f"[MEMORY] Failed to delete memory")
                        else:
                            print(f"[MEMORY] No similar memory found to delete")
                    
                    elif is_update and old_memory_text:
                        # Update the old memory with new one
                        print(f"[MEMORY] Updating memory: '{old_memory_text[:50]}...' -> '{memory_analysis['memory_to_write'][:50]}...'")
                        updated = memory_store.update_memory(
                            user_email=user_email,
                            old_fact_text=old_memory_text,
                            new_fact_text=memory_analysis["memory_to_write"],
                            new_importance=memory_analysis.get("importance")
                        )
                        if updated:
                            print(f"[MEMORY] Successfully updated memory")
                        else:
                            # If update failed, store as new memory
                            print(f"[MEMORY] Update failed, storing as new memory")
                            memory_store.store_memory(
                                user_email=user_email,
                                fact_text=memory_analysis["memory_to_write"],
                                importance=memory_analysis["importance"]
                            )
                    else:
                        # Store new memory (check for conflicts first)
                        new_memory_text = memory_analysis["memory_to_write"]
                        print(f"[MEMORY] Checking for conflicting memories before storing: {new_memory_text[:70]}...")
                        similar_memories = memory_store.find_similar_memories(user_email, new_memory_text, similarity_threshold=0.8)
                        
                        if similar_memories:
                            # Similar memory exists - update it instead of creating duplicate
                            print(f"[MEMORY] Found similar memory (similarity: {similar_memories[0]['similarity']:.2f}), updating instead of creating duplicate")
                            memory_store.update_memory(
                                user_email=user_email,
                                old_fact_text=similar_memories[0]["fact_text"],
                                new_fact_text=new_memory_text,
                                new_importance=memory_analysis["importance"]
                            )
                        else:
                            # No conflict, store new memory
                            print(f"[MEMORY] Storing new memory (importance: {memory_analysis.get('importance')}): {new_memory_text[:70]}...")
                            memory_store.store_memory(
                                user_email=user_email,
                                fact_text=new_memory_text,
                                importance=memory_analysis["importance"]
                            )
                            print(f"[MEMORY] Successfully stored memory")
                except Exception as mem_store_error:
                    print(f"[WARNING] Could not store/update/delete memory: {mem_store_error}")
                    # Continue without storing memory
            else:
                print(f"[MEMORY] Message does not need to be stored (should_write_memory: {memory_analysis.get('should_write_memory')})")
            
            # Step 3: Retrieve relevant memories
            try:
                print(f"[MEMORY] Retrieving relevant memories for query: {user_message[:80]}...")
                relevant_memories = memory_store.get_relevant_memory(
                    user_email=user_email,
                    query=user_message,
                    top_k=5
                )
                if relevant_memories:
                    print(f"[MEMORY] Retrieved {len(relevant_memories)} relevant memories:")
                    for i, mem in enumerate(relevant_memories, 1):
                        print(f"  {i}. {mem[:80]}...")
                else:
                    print(f"[MEMORY] No relevant memories found for query")
            except Exception as mem_retrieve_error:
                print(f"[WARNING] Could not retrieve memories: {mem_retrieve_error}")
                relevant_memories = []
                
        except Exception as mem_analysis_error:
            print(f"[WARNING] Memory analysis failed: {mem_analysis_error}")
            relevant_memories = []
            # Continue without memory analysis
            
    except Exception as mem_init_error:
        print(f"[WARNING] Memory system initialization failed: {mem_init_error}")
        print("  Continuing without memory features...")
        relevant_memories = []
        # Continue without memory system
    
    # Update state with relevant memories
    # IMPORTANT: Preserve rfi_next_route and route for proper routing
    updated_state = state.copy()
    updated_state["relevant_memories"] = relevant_memories
    
    # Determine where to route after memory
    rfi_next_route = state.get("rfi_next_route")
    rfi_status = state.get("rfi_status")
    
    if rfi_next_route:
        # Use rfi_next_route if available
        updated_state["route"] = rfi_next_route
        print(f"[MEMORY] Routing to: {rfi_next_route} (from rfi_next_route)")
    elif rfi_status == "missing_info":
        # RFI determined info is missing, route to conversational agent
        updated_state["route"] = "conversational_agent"
        print(f"[MEMORY] Routing to: conversational_agent (from rfi_status: missing_info)")
    elif rfi_status in ["complete", "error"]:
        # RFI determined info is complete, route to main agent
        updated_state["route"] = "main_agent"
        print(f"[MEMORY] Routing to: main_agent (from rfi_status: {rfi_status})")
    elif not updated_state.get("route") or updated_state.get("route") == "memory_node":
        # Final fallback: default to main_agent
        updated_state["route"] = "main_agent"
        print(f"[MEMORY] No routing info found, defaulting to main_agent")
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"[{end_time.strftime('%H:%M:%S.%f')[:-3]}] [MEMORY] MEMORY NODE COMPLETED ({duration:.2f}s) - {len(relevant_memories)} memories retrieved")
    print(f"[MEMORY] Final route after memory: {updated_state.get('route')}")
    
    return updated_state

