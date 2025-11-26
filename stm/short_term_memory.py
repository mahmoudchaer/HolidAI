"""Short-Term Memory (STM) module using Redis."""

import json
import os
import redis
from datetime import datetime
from typing import Optional, Dict, List
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize Redis client
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Initialize OpenAI client
_openai_client = None

def get_openai_client():
    """Get or create OpenAI client."""
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client


def get_stm_key(session_id: str) -> str:
    """Get Redis key for STM data."""
    return f"STM:{session_id}"


def get_stm(session_id: str) -> Optional[Dict]:
    """
    Retrieve STM data from Redis.
    
    Args:
        session_id: Session identifier
        
    Returns:
        STM dictionary or None if not found
    """
    try:
        key = get_stm_key(session_id)
        data = redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        print(f"[ERROR] Error retrieving STM: {e}")
        return None


def clear_stm(session_id: str) -> bool:
    """
    Clear STM data from Redis.
    
    Args:
        session_id: Session identifier
        
    Returns:
        True if successful, False otherwise
    """
    try:
        key = get_stm_key(session_id)
        redis_client.delete(key)
        print(f"[STM] Cleared STM for session {session_id}")
        return True
    except Exception as e:
        print(f"[ERROR] Error clearing STM: {e}")
        return False


def get_summary(session_id: str) -> Optional[str]:
    """
    Get the summary from STM.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Summary string or None if not found
    """
    stm_data = get_stm(session_id)
    if stm_data:
        return stm_data.get("summary", "")
    return None


def _generate_summary(messages: List[Dict]) -> str:
    """
    Generate a summary of messages using LLM.
    
    Args:
        messages: List of message dictionaries
        
    Returns:
        Summary string
    """
    try:
        client = get_openai_client()
        
        # Format messages for the prompt
        messages_text = "\n".join([
            f"{msg['role'].upper()}: {msg['text']}"
            for msg in messages
        ])
        
        prompt = f"""Summarize the following conversation messages in 3-4 lines, keeping the important context and key information:

{messages_text}

Provide a concise summary that captures the main topics, user preferences, and important details:"""
        
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": "You are a summarization assistant. Provide concise, informative summaries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=200
        )
        
        summary = response.choices[0].message.content.strip()
        return summary
    except Exception as e:
        print(f"[ERROR] Error generating summary: {e}")
        return "Summary unavailable"


def add_message(session_id: str, user_email: str, role: str, text: str) -> bool:
    """
    Add a message to STM and update summary if needed.
    
    Args:
        session_id: Session identifier
        user_email: User's email address
        role: "user" or "agent"
        text: Message text
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Validate role
        if role not in ["user", "agent"]:
            print(f"[ERROR] Invalid role: {role}. Must be 'user' or 'agent'")
            return False
        
        # Get existing STM data or create new
        stm_data = get_stm(session_id)
        
        if not stm_data:
            # Create new STM entry
            stm_data = {
                "session_id": session_id,
                "user_email": user_email,
                "last_messages": [],
                "summary": "",
                "updated_at": datetime.utcnow().isoformat()
            }
        else:
            # Update user_email if it changed (shouldn't happen, but safety check)
            stm_data["user_email"] = user_email
        
        # Add new message
        new_message = {
            "role": role,
            "text": text,
            "timestamp": datetime.utcnow().isoformat()
        }
        stm_data["last_messages"].append(new_message)
        
        # Sort all messages by timestamp to maintain chronological order
        stm_data["last_messages"].sort(key=lambda x: x["timestamp"])
        
        total_messages = len(stm_data["last_messages"])
        
        # Keep last 10 messages total (not 10 of each type)
        # Always keep the most recent 10 messages
        if total_messages > 10:
            # Get messages to summarize (all except the last 10)
            messages_to_summarize = stm_data["last_messages"][:-10]
            # Keep only the last 10 messages
            stm_data["last_messages"] = stm_data["last_messages"][-10:]
            
            # Generate summary from all messages that are beyond the last 10
            # This summary represents the conversation history before the last 10 messages
            if messages_to_summarize:
                print(f"[STM] Generating summary for {len(messages_to_summarize)} older messages (keeping last 10 messages as-is)")
                # Generate summary from all old messages
                stm_data["summary"] = _generate_summary(messages_to_summarize)
        else:
            # Less than or equal to 10 messages, no summary needed yet
            print(f"[STM] Not generating summary yet ({total_messages} messages, need >10)")
            # Clear summary if we're at or under 10 messages (all messages are in last_messages)
            stm_data["summary"] = ""
        
        # Update timestamp
        stm_data["updated_at"] = datetime.utcnow().isoformat()
        
        # Save back to Redis
        key = get_stm_key(session_id)
        redis_client.set(key, json.dumps(stm_data))
        
        print(f"[STM] Added {role} message to session {session_id} (total: {total_messages} messages)")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error adding message to STM: {e}")
        import traceback
        traceback.print_exc()
        return False


def store_last_results(session_id: str, results: Dict) -> bool:
    """
    Store the last search results (flights, hotels, etc.) in STM for later retrieval.
    
    Args:
        session_id: Session identifier
        results: Dictionary containing flight_result, hotel_result, etc.
        
    Returns:
        True if successful, False otherwise
    """
    try:
        stm_data = get_stm(session_id)
        
        if not stm_data:
            # Create new STM entry
            stm_data = {
                "session_id": session_id,
                "last_messages": [],
                "summary": "",
                "last_results": {},
                "updated_at": datetime.utcnow().isoformat()
            }
        
        # Store results (only non-empty results)
        if "last_results" not in stm_data:
            stm_data["last_results"] = {}
        
        # Update with new results (merge, don't replace entirely)
        # Convert results to JSON-serializable format
        def make_serializable(obj):
            """Recursively convert objects to JSON-serializable format."""
            if isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [make_serializable(item) for item in obj]
            elif isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            else:
                # For other types, convert to string
                return str(obj)
        
        for key, value in results.items():
            if value:  # Only store non-empty results
                stm_data["last_results"][key] = make_serializable(value)
        
        stm_data["updated_at"] = datetime.utcnow().isoformat()
        
        # Save back to Redis
        key = get_stm_key(session_id)
        redis_client.set(key, json.dumps(stm_data, default=str, ensure_ascii=False))
        
        print(f"[STM] Stored last results for session {session_id}: {list(results.keys())}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error storing last results: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_last_results(session_id: str) -> Optional[Dict]:
    """
    Retrieve the last search results from STM.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Dictionary with last results (flight_result, hotel_result, etc.) or None
    """
    try:
        stm_data = get_stm(session_id)
        if stm_data:
            return stm_data.get("last_results", {})
        return {}
    except Exception as e:
        print(f"[ERROR] Error retrieving last results: {e}")
        return {}

