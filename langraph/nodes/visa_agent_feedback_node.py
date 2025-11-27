"""Feedback validation node for Visa Agent."""

import sys
import os
import json
import time
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from agent_logger import log_llm_call, log_feedback_failure

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import AgentState

# Load environment variables
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MAX_FEEDBACK_RETRIES = 2


def get_visa_agent_feedback_prompt() -> str:
    """Get the system prompt for the Visa Agent Feedback Validator."""
    return """You are a Visa Agent Feedback Validator. Your ONLY job is to catch ACTUAL ERRORS, not judge formatting or structure.

**YOUR ROLE**: Catch major failures only - you are NOT a grumpy judge!

**WHAT TO FLAG (only these 3 things)**:
1. ❌ **Empty result**: No visa information at all, no error message
2. ❌ **Vague answer**: Says "visa may be required" or "check requirements" without clear answer
3. ❌ **Wrong countries**: User asked about France, result talks about Germany

**WHAT TO IGNORE (pass these)**:
- ✅ "Doesn't specify source/destination explicitly" - if the answer is there, it's fine!
- ✅ "Missing passport validity details" - core visa answer is what matters
- ✅ "No country tags" - the conversational agent can read it!
- ✅ Any formatting or structure complaints - data is there? Good!
- ✅ "Other info missing" (flights, hotels, etc.) - this is ONLY about visa, ignore other requests!

**KEY RULES**:
- ✅ "No visa required" = PASS
- ✅ "Visa required" with details = PASS
- ✅ "Visa on arrival" = PASS
- ✅ "Visa may be obtained on arrival" = PASS
- ❌ "Visa may be required, please check" = RETRY (truly vague)

Respond with JSON:
{
  "validation_status": "pass" | "need_retry",
  "feedback_message": "brief explanation"
}

Examples:

Example 1 - Clear answer, no visa needed (PASS):
User: "UAE citizen to France, need visa?"
Result: {"error": false, "result": "No visa required. Maximum stay of 90 days."}
Response: {"validation_status": "pass", "feedback_message": "Clear visa answer provided"}

Example 2 - Clear answer even if countries not "explicitly mentioned" (PASS):
User: "UAE to France visa?"
Result: {"result": "Visa is not required for France. Maximum stay of 90 days."}
Response: {"validation_status": "pass", "feedback_message": "Visa requirement clearly stated"}

Example 3 - Visa required with details (PASS):
User: "India to USA visa?"
Result: {"result": "Indian citizens require a visa to enter USA..."}
Response: {"validation_status": "pass", "feedback_message": "Visa requirement provided"}

Example 4 - Empty result (RETRY):
User: "Need visa for France?"
Result: {"error": false, "result": ""}
Response: {"validation_status": "need_retry", "feedback_message": "No visa information returned"}

Example 5 - Visa on arrival (PASS):
User: "UK to Dubai visa?"
Result: {"result": "Visa may be obtained on arrival"}
Response: {"validation_status": "pass", "feedback_message": "Visa on arrival policy clearly stated"}

Example 6 - Visa on arrival with details (PASS):
User: "UK to UAE visa?"
Result: {"result": "UK citizens can obtain visa on arrival. Fee applies."}
Response: {"validation_status": "pass", "feedback_message": "Visa on arrival information provided"}

Example 7 - Truly vague answer (RETRY):
User: "UAE to France visa?"
Result: {"result": "Visa may be required, please check"}
Response: {"validation_status": "need_retry", "feedback_message": "Answer too vague - doesn't say if visa is actually required or not"}

Example 8 - Error (PASS):
User: "Visa for invalid-country?"
Result: {"error": true, "error_message": "Country not found"}
Response: {"validation_status": "pass", "feedback_message": "Error handled"}"""


async def visa_agent_feedback_node(state: AgentState) -> AgentState:
    """Visa Agent feedback node that validates visa requirement results.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with validation results and routing decision
    """
    user_message = state.get("user_message", "")
    visa_result = state.get("visa_result", {})
    visa_feedback_retry_count = state.get("visa_feedback_retry_count", 0)
    
    print(f"\n=== Visa Agent Feedback Validator ===")
    
    # Check for infinite loops
    if visa_feedback_retry_count >= MAX_FEEDBACK_RETRIES:
        print(f"Visa Feedback: Max retries ({MAX_FEEDBACK_RETRIES}) reached, accepting results")
        return {
            "visa_feedback_retry_count": visa_feedback_retry_count + 1
        }
    
    # If no result, nothing to validate
    if not visa_result:
        print("Visa Feedback: No result to validate")
        return {}
    
    # Prepare validation context
    result_text = visa_result.get("result", visa_result.get("data", ""))
    
    # If result_text is missing but no error, accept it (might be in parallel execution)
    if not result_text and not visa_result.get("error"):
        print("Visa Feedback: Empty result but no error - accepting")
        return {
            "visa_feedback_message": None,
            "visa_feedback_retry_count": 0
        }
    
    # Truncate if too long (keep first 500 chars for validation)
    if isinstance(result_text, str) and len(result_text) > 500:
        result_text_sample = result_text[:500] + "..."
    else:
        result_text_sample = result_text
    
    validation_context = {
        "user_request": user_message,
        "result_summary": {
            "has_error": visa_result.get("error", False),
            "error_message": visa_result.get("error_message", ""),
            "has_result": bool(result_text),
            "result_preview": result_text_sample,
            "source_country": visa_result.get("source_country", ""),
            "destination_country": visa_result.get("destination_country", "")
        }
    }
    
    # Call LLM for validation
    messages = [
        {"role": "system", "content": get_visa_agent_feedback_prompt()},
        {"role": "user", "content": f"Validate these visa requirement results:\n\n{json.dumps(validation_context, indent=2)}"}
    ]
    
    try:
        session_id = state.get("session_id", "unknown")
        user_email = state.get("user_email")
        llm_start_time = time.time()
        
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        llm_latency_ms = (time.time() - llm_start_time) * 1000
        
        # Log LLM call
        prompt_preview = str(messages[-1].get("content", "")) if messages else ""
        response_preview = response.choices[0].message.content if response.choices[0].message.content else ""
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens if hasattr(response, 'usage') and response.usage else None,
            "completion_tokens": response.usage.completion_tokens if hasattr(response, 'usage') and response.usage else None,
            "total_tokens": response.usage.total_tokens if hasattr(response, 'usage') and response.usage else None
        } if hasattr(response, 'usage') and response.usage else None
        
        log_llm_call(
            session_id=session_id,
            user_email=user_email,
            agent_name="visa_agent_feedback",
            model="gpt-4.1",
            prompt_preview=prompt_preview,
            response_preview=response_preview,
            token_usage=token_usage,
            latency_ms=llm_latency_ms
        )
        
        validation_result = json.loads(response.choices[0].message.content)
        status = validation_result.get("validation_status", "pass")
        feedback_msg = validation_result.get("feedback_message", "")
        suggested_action = validation_result.get("suggested_action", "")
        
        print(f"Visa Feedback: Status = {status}")
        print(f"Visa Feedback: {feedback_msg}")
        
        # Log feedback failure if status indicates failure
        if status != "pass":
            log_feedback_failure(
                session_id=session_id,
                user_email=user_email,
                feedback_node="visa_agent_feedback",
                reason=f"Status: {status}, Message: {feedback_msg}"
            )
        
        # Route based on validation status
        if status == "pass":
            # Results are valid, continue
            return {
                "visa_feedback_message": None,
                "visa_feedback_retry_count": 0
            }
            
        elif status == "need_retry":
            # Results are inadequate, retry visa check
            print(f"Visa Feedback: Requesting retry of visa check")
            full_feedback = f"{feedback_msg}\n\n{suggested_action}" if suggested_action else feedback_msg
            
            return {
                "visa_result": None,
                "visa_feedback_message": full_feedback,
                "visa_feedback_retry_count": visa_feedback_retry_count + 1
                # Note: Don't decrement current_step - retry routes directly to agent, not through plan_executor
            }
        
        else:
            # Unknown status, accept results
            print(f"Visa Feedback: Unknown status '{status}', accepting results")
            return {
                "visa_feedback_message": None,
                "visa_feedback_retry_count": visa_feedback_retry_count + 1
            }
            
    except Exception as e:
        print(f"Visa Feedback: Validation error - {e}, accepting results")
        return {
            "visa_feedback_message": None,
            "visa_feedback_retry_count": visa_feedback_retry_count + 1
        }

