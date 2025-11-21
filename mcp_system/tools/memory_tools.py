"""Memory-related tools for the MCP server."""

import sys
import os
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".."))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

from memory.memory_store import MemoryStore
from memory.memory_extraction import analyze_for_memory


def register_memory_tools(mcp):
    """Register all memory-related tools with the MCP server."""
    
    @mcp.tool(description="Analyze a user message to determine if it should be stored in long-term memory, or if it updates/deletes an existing memory.")
    def agent_analyze_memory_tool(message: str) -> Dict:
        """Analyze a user message for memory extraction.
        
        This tool analyzes the user's message to determine if it contains
        information that should be stored in long-term memory, or if it
        updates/deletes an existing memory.
        
        Args:
            message: The user's message text to analyze
        
        Returns:
            Dictionary with:
            - should_write_memory: bool - whether to store/update/delete memory
            - memory_to_write: str - the memory text to store (if applicable)
            - importance: int (1-5) - importance score
            - is_update: bool - whether this is an update to existing memory
            - is_deletion: bool - whether this is a deletion request
            - old_memory_text: str - text of memory being updated/deleted (if applicable)
        """
        try:
            result = analyze_for_memory(message)
            return {
                "should_write_memory": result.get("should_write_memory", False),
                "memory_to_write": result.get("memory_to_write", ""),
                "importance": result.get("importance", 1),
                "is_update": result.get("is_update", False),
                "is_deletion": result.get("is_deletion", False),
                "old_memory_text": result.get("old_memory_text", "")
            }
        except Exception as e:
            print(f"[ERROR] Error in analyze_memory_tool: {e}")
            return {
                "should_write_memory": False,
                "memory_to_write": "",
                "importance": 1,
                "is_update": False,
                "is_deletion": False,
                "old_memory_text": ""
            }
    
    @mcp.tool(description="Store a new memory in the long-term memory database.")
    def agent_store_memory_tool(user_email: str, fact_text: str, importance: int) -> Dict:
        """Store a new memory in Qdrant.
        
        Args:
            user_email: User's email address
            fact_text: The factual memory text to store
            importance: Importance score (1-5)
        
        Returns:
            Dictionary with success status and message
        """
        try:
            memory_store = MemoryStore()
            memory_store.store_memory(user_email, fact_text, importance)
            return {
                "success": True,
                "message": f"Successfully stored memory: {fact_text[:50]}..."
            }
        except Exception as e:
            print(f"[ERROR] Error storing memory: {e}")
            return {
                "success": False,
                "message": f"Error storing memory: {str(e)}"
            }
    
    @mcp.tool(description="Update an existing memory in the long-term memory database.")
    def agent_update_memory_tool(user_email: str, old_fact_text: str, new_fact_text: str, new_importance: Optional[int] = None) -> Dict:
        """Update an existing memory.
        
        Args:
            user_email: User's email address
            old_fact_text: The old fact text to find and replace
            new_fact_text: The new fact text
            new_importance: Optional new importance score (if None, keeps old importance)
        
        Returns:
            Dictionary with success status and message
        """
        try:
            memory_store = MemoryStore()
            success = memory_store.update_memory(user_email, old_fact_text, new_fact_text, new_importance)
            if success:
                return {
                    "success": True,
                    "message": f"Successfully updated memory: '{old_fact_text[:50]}...' -> '{new_fact_text[:50]}...'"
                }
            else:
                return {
                    "success": False,
                    "message": f"Could not find similar memory to update: {old_fact_text[:50]}..."
                }
        except Exception as e:
            print(f"[ERROR] Error updating memory: {e}")
            return {
                "success": False,
                "message": f"Error updating memory: {str(e)}"
            }
    
    @mcp.tool(description="Delete a memory from the long-term memory database.")
    def agent_delete_memory_tool(user_email: str, fact_text: str) -> Dict:
        """Delete a memory by finding similar memories and deleting the most similar one.
        
        Args:
            user_email: User's email address
            fact_text: The fact text of the memory to delete
        
        Returns:
            Dictionary with success status and message
        """
        try:
            memory_store = MemoryStore()
            # Find similar memories
            similar_memories = memory_store.find_similar_memories(user_email, fact_text, similarity_threshold=0.7)
            
            if not similar_memories:
                return {
                    "success": False,
                    "message": f"No similar memory found to delete: {fact_text[:50]}..."
                }
            
            # Delete the most similar memory
            memory_id = similar_memories[0]["id"]
            success = memory_store.delete_memory(user_email, memory_id)
            
            if success:
                return {
                    "success": True,
                    "message": f"Successfully deleted memory: {fact_text[:50]}..."
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to delete memory: {fact_text[:50]}..."
                }
        except Exception as e:
            print(f"[ERROR] Error deleting memory: {e}")
            return {
                "success": False,
                "message": f"Error deleting memory: {str(e)}"
            }
    
    @mcp.tool(description="Retrieve relevant memories for a user based on a query.")
    def agent_get_relevant_memories_tool(user_email: str, query: str, top_k: int = 5) -> Dict:
        """Get relevant memories for a user based on a query.
        
        This tool searches the user's memories and returns the most relevant ones
        based on semantic similarity and importance scoring.
        
        Args:
            user_email: User's email address
            query: Search query text
            top_k: Number of relevant memories to return (default: 5)
        
        Returns:
            Dictionary with:
            - memories: List[str] - list of relevant memory texts
            - count: int - number of memories returned
        """
        try:
            memory_store = MemoryStore()
            memories = memory_store.get_relevant_memory(user_email, query, top_k=top_k)
            return {
                "memories": memories,
                "count": len(memories)
            }
        except Exception as e:
            print(f"[ERROR] Error retrieving memories: {e}")
            return {
                "memories": [],
                "count": 0
            }

