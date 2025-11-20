"""LLM-based memory extraction."""
from openai import OpenAI
import os
import json
from dotenv import load_dotenv

load_dotenv()

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


def analyze_for_memory(message: str) -> dict:
    """
    Analyze user message to determine if it should be saved to memory.
    
    Args:
        message: User's message text
        
    Returns:
        {
            "should_write_memory": true/false,
            "memory_to_write": "cleaned memory text",
            "importance": int(1-5)
        }
    """
    try:
        client = get_openai_client()
        
        prompt = """You are a memory extraction module. 
Analyze the user's message and determine if it should be saved to long-term memory, or if it updates/removes an existing memory.

Return ONLY valid JSON:
{
  "should_write_memory": true/false,
  "memory_to_write": "condensed factual memory",
  "importance": integer 1-5,
  "is_update": true/false,
  "is_deletion": true/false,
  "old_memory_text": "text of memory being updated/deleted (if applicable)"
}

Importance meaning:
1-2 = ignore (not useful)
3   = useful but low priority
4   = important
5   = extremely important, should always be saved

Memory operations:
- is_update: true if user is updating/changing a preference (e.g., "I no longer prefer X" or "I changed my preference from X to Y")
- is_deletion: true if user is explicitly removing a preference (e.g., "I don't prefer X anymore" or "Forget that I like X")
- old_memory_text: The text of the memory being updated/deleted (e.g., "User prefers morning flights" if user says "I no longer prefer morning flights")

Only save factual information about the user's preferences, constraints, or important details.
Do NOT save:
- Greetings or casual conversation
- Questions without personal context
- Temporary information
- Generic travel queries

User message: """ + message
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using gpt-4o-mini for cost efficiency
            messages=[
                {"role": "system", "content": "You are a memory extraction module. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        result_text = response.choices[0].message.content
        result = json.loads(result_text)
        
        # Validate and ensure correct types
        return {
            "should_write_memory": bool(result.get("should_write_memory", False)),
            "memory_to_write": str(result.get("memory_to_write", "")).strip(),
            "importance": int(result.get("importance", 1)),
            "is_update": bool(result.get("is_update", False)),
            "is_deletion": bool(result.get("is_deletion", False)),
            "old_memory_text": str(result.get("old_memory_text", "")).strip()
        }
        
    except Exception as e:
        print(f"[ERROR] Error in memory extraction: {e}")
        # Return default: don't save
        return {
            "should_write_memory": False,
            "memory_to_write": "",
            "importance": 1,
            "is_update": False,
            "is_deletion": False,
            "old_memory_text": ""
        }

