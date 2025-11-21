"""Memory Agent node for LangGraph orchestration."""

import sys
import os
import json
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "mcp_system"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import AgentState
from clients.memory_agent_client import MemoryAgentClient

# Load environment variables from .env file in main directory
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_memory_agent_prompt() -> str:
    """Get the system prompt for the Memory Agent."""
    
    base_prompt = """You are the Memory Agent, a specialized agent that manages long-term memory for users.

CRITICAL: You MUST use the available tools to analyze, store, update, delete, and retrieve memories. Do NOT respond without calling tools.

Your role:
1. Analyze the user's message to determine if it should be stored in long-term memory, or if it updates/deletes an existing memory
2. Store new memories if important (importance >= 3)
3. Update existing memories if the user is changing a preference
4. Delete memories if the user explicitly removes a preference
5. Retrieve relevant memories for the current query to pass to other agents

Available tools:
- agent_analyze_memory_tool: Analyze a user message to determine if it should be stored/updated/deleted
- agent_store_memory_tool: Store a new memory in the database
- agent_update_memory_tool: Update an existing memory
- agent_delete_memory_tool: Delete a memory
- agent_get_relevant_memories_tool: Retrieve relevant memories for a query

IMPORTANT WORKFLOW:
1. ALWAYS start by calling agent_analyze_memory_tool with the user message
2. If should_write_memory is true:
   - If is_deletion is true: Call agent_delete_memory_tool
   - If is_update is true: Call agent_update_memory_tool
   - Otherwise: Call agent_store_memory_tool
3. ALWAYS call agent_get_relevant_memories_tool to retrieve relevant memories for the query
4. The retrieved memories will be passed to other agents (RFI, main agent, etc.)

You must complete ALL steps: analyze, store/update/delete if needed, and retrieve relevant memories."""
    
    return base_prompt


async def memory_agent_node(state: AgentState) -> AgentState:
    """Memory Agent node that handles memory operations.
    
    This agent:
    1. Analyzes the user message for memory extraction
    2. Stores/updates/deletes memories if needed
    3. Retrieves relevant memories for the current query
    4. Passes memories to RFI and other agents
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with relevant_memories populated
    """
    from datetime import datetime
    start_time = datetime.now()
    print(f"[{start_time.strftime('%H:%M:%S.%f')[:-3]}] 🧠 MEMORY AGENT STARTED")
    
    user_message = state.get("user_message", "")
    user_email = state.get("user_email")
    
    # Initialize relevant_memories as empty list
    relevant_memories = []
    
    # If no user email, skip memory operations
    if not user_email:
        print("[MEMORY] No user_email in state, skipping memory operations")
        updated_state = state.copy()
        updated_state["relevant_memories"] = []
        updated_state["route"] = "rfi_node"  # Route to RFI after memory
        return updated_state
    
    try:
        # Get tools available to memory agent
        tools = await MemoryAgentClient.list_tools()
        
        # Prepare messages for LLM
        prompt = get_memory_agent_prompt()
        
        agent_message = f"""User message: {user_message}

User email: {user_email}

Please:
1. Analyze this message for memory extraction
2. Store/update/delete memory if needed
3. Retrieve relevant memories for this query

Remember: You MUST call the tools to complete these tasks."""
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": agent_message}
        ]
        
        # Build function calling schema for memory tools
        functions = []
        def _sanitize_schema(schema: dict) -> dict:
            """Ensure arrays have 'items' and sanitize nested schemas."""
            if not isinstance(schema, dict):
                return schema
            sanitized = dict(schema)
            schema_type = sanitized.get("type")
            if schema_type == "array" and "items" not in sanitized:
                sanitized["items"] = {"type": "object"}
            if schema_type == "object":
                props = sanitized.get("properties", {})
                for key, val in list(props.items()):
                    props[key] = _sanitize_schema(val)
                sanitized["properties"] = props
            if "items" in sanitized and isinstance(sanitized["items"], dict):
                sanitized["items"] = _sanitize_schema(sanitized["items"])
            return sanitized

        for tool in tools:
            if tool["name"] in [
                "agent_analyze_memory_tool",
                "agent_store_memory_tool",
                "agent_update_memory_tool",
                "agent_delete_memory_tool",
                "agent_get_relevant_memories_tool"
            ]:
                input_schema = tool.get("inputSchema", {})
                input_schema = _sanitize_schema(input_schema)
                functions.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", f"Memory operation tool"),
                        "parameters": input_schema
                    }
                })
        
        # Step 1: Always analyze the message first
        memory_analysis = None
        try:
            analysis_result = await MemoryAgentClient.invoke(
                "agent_analyze_memory_tool",
                message=user_message
            )
            memory_analysis = analysis_result
            print(f"[MEMORY] Analysis result: should_write={analysis_result.get('should_write_memory')}, importance={analysis_result.get('importance')}")
        except Exception as e:
            print(f"[WARNING] Error analyzing memory: {e}")
            memory_analysis = {
                "should_write_memory": False,
                "memory_to_write": "",
                "importance": 1,
                "is_update": False,
                "is_deletion": False,
                "old_memory_text": ""
            }
        
        # Step 2: Store/update/delete memory if needed
        if memory_analysis and memory_analysis.get("should_write_memory") and memory_analysis.get("memory_to_write"):
            try:
                is_deletion = memory_analysis.get("is_deletion", False)
                is_update = memory_analysis.get("is_update", False)
                old_memory_text = memory_analysis.get("old_memory_text", "")
                memory_to_write = memory_analysis.get("memory_to_write", "")
                importance = memory_analysis.get("importance", 3)
                
                if is_deletion and old_memory_text:
                    # Delete memory
                    delete_result = await MemoryAgentClient.invoke(
                        "agent_delete_memory_tool",
                        user_email=user_email,
                        fact_text=old_memory_text
                    )
                    print(f"[MEMORY] Delete result: {delete_result.get('success')} - {delete_result.get('message', '')}")
                
                elif is_update and old_memory_text:
                    # Update memory
                    update_result = await MemoryAgentClient.invoke(
                        "agent_update_memory_tool",
                        user_email=user_email,
                        old_fact_text=old_memory_text,
                        new_fact_text=memory_to_write,
                        new_importance=importance
                    )
                    print(f"[MEMORY] Update result: {update_result.get('success')} - {update_result.get('message', '')}")
                
                else:
                    # Store new memory
                    store_result = await MemoryAgentClient.invoke(
                        "agent_store_memory_tool",
                        user_email=user_email,
                        fact_text=memory_to_write,
                        importance=importance
                    )
                    print(f"[MEMORY] Store result: {store_result.get('success')} - {store_result.get('message', '')}")
            except Exception as e:
                print(f"[WARNING] Error storing/updating/deleting memory: {e}")
        
        # Step 3: Always retrieve relevant memories
        try:
            result = await MemoryAgentClient.invoke(
                "agent_get_relevant_memories_tool",
                user_email=user_email,
                query=user_message,
                top_k=5
            )
            relevant_memories = result.get("memories", [])
            print(f"[MEMORY] Retrieved {len(relevant_memories)} relevant memories")
            if relevant_memories:
                for i, mem in enumerate(relevant_memories, 1):
                    print(f"  {i}. {mem[:80]}...")
        except Exception as e:
            print(f"[WARNING] Could not retrieve memories: {e}")
            relevant_memories = []
        
        updated_state = state.copy()
    
    except Exception as mem_init_error:
        print(f"[WARNING] Memory agent initialization failed: {mem_init_error}")
        print("  Continuing without memory features...")
        relevant_memories = []
    
    # Update state with relevant memories
    updated_state = state.copy()
    updated_state["relevant_memories"] = relevant_memories
    updated_state["route"] = "rfi_node"  # Always route to RFI after memory
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"[{end_time.strftime('%H:%M:%S.%f')[:-3]}] 🧠 MEMORY AGENT COMPLETED ({duration:.2f}s) - {len(relevant_memories)} memories retrieved")
    print(f"[MEMORY] Routing to: rfi_node")
    
    return updated_state

