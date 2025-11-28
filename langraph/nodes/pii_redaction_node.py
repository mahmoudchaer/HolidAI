"""PII Redaction node for LangGraph orchestration."""

import sys
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from state import AgentState

# Load environment variables from .env file in main directory
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize Presidio engines (singleton pattern for efficiency)
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()


def redact_pii(text: str) -> str:
    """Redact PII from text using Presidio.
    
    Args:
        text: Input text containing potentially sensitive information
        
    Returns:
        Text with PII replaced by placeholders
    """
    if not text:
        return text
    
    # Detect PII entities
    results = analyzer.analyze(
        text=text,
        entities=[
            "PERSON",
            "PHONE_NUMBER",
            "EMAIL_ADDRESS",
            "CREDIT_CARD",
            "IBAN_CODE",
            "LOCATION",
            "NRP"
        ],
        language="en"
    )
    
    # Configure anonymization operators with placeholders
    operators = {
        "PERSON": OperatorConfig("replace", {"new_value": "<NAME>"}),
        "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "<EMAIL>"}),
        "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "<PHONE>"}),
        "LOCATION": OperatorConfig("replace", {"new_value": "<ADDRESS>"}),
        "CREDIT_CARD": OperatorConfig("replace", {"new_value": "<FINANCIAL>"}),
        "IBAN_CODE": OperatorConfig("replace", {"new_value": "<FINANCIAL>"}),
        "NRP": OperatorConfig("replace", {"new_value": "<ID>"}),
    }
    
    # Apply anonymization
    anonymized = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators=operators
    )
    
    return anonymized.text


async def pii_redaction_node(state: AgentState) -> AgentState:
    """PII Redaction node that sanitizes user messages.
    
    This node:
    1. Takes the original user_message from state
    2. Uses Presidio to detect and redact PII entities
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
        print(f"[PII] Original message length: {len(user_message)} characters")
        
        # Use Presidio to redact PII
        sanitized_message = redact_pii(user_message)
        
        print(f"[PII] Sanitized message length: {len(sanitized_message)} characters")
        
        # Update state with sanitized message
        updated_state = state.copy()
        updated_state["user_message"] = sanitized_message
        updated_state["route"] = "memory_agent"
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"[{end_time.strftime('%H:%M:%S.%f')[:-3]}] 🔒 PII REDACTION COMPLETED ({duration:.2f}s)")
        print("[PII] Routing to: memory_agent")
        
        return updated_state
        
    except Exception as e:
        print(f"[PII] ERROR: Failed to redact PII: {e}")
        import traceback
        traceback.print_exc()
        print("[PII] Using original message as fallback")
        updated_state = state.copy()
        updated_state["route"] = "memory_agent"
        return updated_state

