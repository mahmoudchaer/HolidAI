"""PII Redaction node for LangGraph orchestration."""

import sys
import os
import json
import httpx
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import AgentState

# Load environment variables from .env file in main directory
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Get PII LLM endpoint from environment
PII_IP_ADDRESS = os.getenv("PII_IP_ADDRESS", "20.164.1.192:11434")
PII_BASE_URL = f"http://{PII_IP_ADDRESS}/api/chat"


def get_pii_redaction_prompt() -> str:
    """Get the system prompt for PII redaction."""
    
    prompt = """You are a data-sanitization layer for an AI travel agent.

Your job is to remove ONLY confidential personal information and replace it with placeholders, while keeping all travel-relevant details intact.

YOU MUST REMOVE (replace with placeholders):

Full names, first names, last names

Email addresses

Phone numbers

Exact street addresses, building numbers, apartment numbers

Passport numbers, national IDs, account numbers, booking IDs, receipt IDs

Credit card numbers, financial details

API keys or tokens

Any unique personal identifier

Use placeholders like:

<NAME_1>, <EMAIL_1>, <PHONE_1>, <ADDRESS_1>, <ID_1>

YOU MUST KEEP (never remove):

These are required for the travel agent to work correctly:

Countries

Cities

Airports

Airlines

Hotel names

Dates and times

Durations

Budgets

Nationalities (needed for visa/flight rules)

Number of travelers

Travel preferences

Activities, interests, trip types

RULES

Do NOT remove or hide any geographic or travel info.

Do NOT invent new details.

Do NOT rewrite meaning. Only sanitize the personal parts.

Final output must maintain readable, natural text without losing context.

OUTPUT

Return the same message as is, but with confidential data replaced by placeholders."""
    
    return prompt


async def pii_redaction_node(state: AgentState) -> AgentState:
    """PII Redaction node that sanitizes user messages.
    
    This node:
    1. Takes the original user_message from state
    2. Sends it to the local PII redaction LLM endpoint
    3. Replaces user_message with the sanitized version
    4. Routes to memory_agent
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with sanitized user_message
    """
    start_time = datetime.now()
    print(f"[{start_time.strftime('%H:%M:%S.%f')[:-3]}] 🔒 PII REDACTION STARTED")
    
    user_message = state.get("user_message", "")
    
    if not user_message:
        print("[PII] No user_message in state, skipping redaction")
        updated_state = state.copy()
        updated_state["route"] = "memory_agent"
        return updated_state
    
    try:
        # Prepare the request to local LLM
        system_prompt = get_pii_redaction_prompt()
        
        payload = {
            "model": "phi3:mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "stream": False
        }
        
        print(f"[PII] Sending request to {PII_BASE_URL}")
        print(f"[PII] Original message length: {len(user_message)} characters")
        
        # Make async HTTP request to local LLM
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                PII_BASE_URL,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            result = response.json()
        
        # Extract sanitized message from response
        # Standard chat-completions format: {"choices": [{"message": {"content": "..."}}]}
        # Or Ollama format: {"message": {"content": "..."}}
        sanitized_message = None
        
        if "choices" in result and len(result["choices"]) > 0:
            # OpenAI-style format
            choice = result["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                sanitized_message = choice["message"]["content"].strip()
        elif "message" in result and "content" in result["message"]:
            # Ollama-style format
            sanitized_message = result["message"]["content"].strip()
        elif "content" in result:
            # Direct content field
            sanitized_message = result["content"].strip()
        
        # Fallback to original if parsing failed
        if not sanitized_message:
            print("[PII] WARNING: Could not extract sanitized message from response")
            print(f"[PII] Response structure: {json.dumps(result, indent=2)[:500]}")
            sanitized_message = user_message
        
        print(f"[PII] Sanitized message length: {len(sanitized_message)} characters")
        
        # Update state with sanitized message
        updated_state = state.copy()
        updated_state["user_message"] = sanitized_message
        updated_state["route"] = "memory_agent"
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"[{end_time.strftime('%H:%M:%S.%f')[:-3]}] 🔒 PII REDACTION COMPLETED ({duration:.2f}s)")
        print(f"[PII] Routing to: memory_agent")
        
        return updated_state
        
    except httpx.TimeoutException:
        print("[PII] ERROR: Request to PII LLM timed out, using original message")
        updated_state = state.copy()
        updated_state["route"] = "memory_agent"
        return updated_state
    except httpx.HTTPStatusError as e:
        print(f"[PII] ERROR: HTTP error from PII LLM: {e.response.status_code} - {e.response.text}")
        print("[PII] Using original message as fallback")
        updated_state = state.copy()
        updated_state["route"] = "memory_agent"
        return updated_state
    except Exception as e:
        print(f"[PII] ERROR: Failed to redact PII: {e}")
        import traceback
        traceback.print_exc()
        print("[PII] Using original message as fallback")
        updated_state = state.copy()
        updated_state["route"] = "memory_agent"
        return updated_state

