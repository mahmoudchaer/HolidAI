"""Agent logging system for LangGraph nodes, interactions, and LLM calls to Azure Blob Storage."""

import os
import json
import time
import uuid
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
from dotenv import load_dotenv

# Load environment variables from .env file in main directory
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Azure Blob Storage configuration
AZURE_BLOB_CONNECTION_STRING = os.getenv("AZURE_BLOB_CONNECTION_STRING")
AZURE_BLOB_ACCOUNT_NAME = os.getenv("AZURE_BLOB_ACCOUNT_NAME", "holidailogs")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "holidai-logs")

# Shared BlobServiceClient instance (lazy initialization)
_blob_service_client = None
_blob_client_lock = threading.Lock()

# Fallback log directory
FALLBACK_LOG_DIR = Path(__file__).parent.parent / "logs" / "failed_blob_logs"
FALLBACK_LOG_DIR.mkdir(parents=True, exist_ok=True)


def _get_blob_service_client():
    """Get or create shared BlobServiceClient instance."""
    global _blob_service_client
    
    if _blob_service_client is None:
        with _blob_client_lock:
            if _blob_service_client is None:
                try:
                    from azure.storage.blob import BlobServiceClient, ContentSettings
                    if not AZURE_BLOB_CONNECTION_STRING:
                        print("[AGENT_LOGGER] Warning: AZURE_BLOB_CONNECTION_STRING not set, logging will use fallback")
                        return None
                    _blob_service_client = BlobServiceClient.from_connection_string(
                        AZURE_BLOB_CONNECTION_STRING
                    )
                except ImportError:
                    print("[AGENT_LOGGER] Warning: azure-storage-blob not installed, logging will use fallback")
                    return None
                except Exception as e:
                    print(f"[AGENT_LOGGER] Warning: Failed to initialize BlobServiceClient: {e}, using fallback")
                    return None
    
    return _blob_service_client


def _write_fallback_log(log_data: Dict):
    """Write log to local fallback directory."""
    try:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        log_file = FALLBACK_LOG_DIR / f"agent_log_{timestamp}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[AGENT_LOGGER] Error writing fallback log: {e}")


def _upload_to_blob(log_data: Dict, blob_path: str) -> bool:
    """Upload log to Azure Blob Storage with retry logic."""
    client = _get_blob_service_client()
    if not client:
        return False
    
    # Retry once if it fails
    for attempt in range(2):
        try:
            from azure.storage.blob import ContentSettings
            
            blob_client = client.get_blob_client(
                container=AZURE_BLOB_CONTAINER,
                blob=blob_path
            )
            
            log_json = json.dumps(log_data, indent=2, ensure_ascii=False)
            content_settings = ContentSettings(content_type="application/json")
            blob_client.upload_blob(
                log_json,
                overwrite=True,
                content_settings=content_settings
            )
            return True
        except Exception as e:
            if attempt == 0:
                print(f"[AGENT_LOGGER] Upload attempt {attempt + 1} failed: {e}, retrying...")
            else:
                print(f"[AGENT_LOGGER] Upload attempt {attempt + 1} failed: {e}, using fallback")
                return False
    
    return False


def log_node_enter(session_id: str, user_email: Optional[str], node_name: str):
    """Log when a LangGraph node starts."""
    try:
        timestamp = datetime.utcnow().isoformat() + "Z"
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        
        log_entry = {
            "type": "node_enter",
            "session_id": session_id,
            "user_email": user_email,
            "node_name": node_name,
            "timestamp": timestamp
        }
        
        blob_path = f"agent/nodes/{node_name}/{date_str}/enter_{timestamp_str}.json"
        
        def upload_async():
            try:
                if not _upload_to_blob(log_entry, blob_path):
                    _write_fallback_log(log_entry)
            except Exception as e:
                print(f"[AGENT_LOGGER] Error in async upload: {e}")
                _write_fallback_log(log_entry)
        
        thread = threading.Thread(target=upload_async, daemon=True)
        thread.start()
    except Exception as e:
        print(f"[AGENT_LOGGER] Error logging node enter: {e}")


def log_node_exit(session_id: str, user_email: Optional[str], node_name: str, latency_ms: float):
    """Log when a LangGraph node finishes."""
    try:
        timestamp = datetime.utcnow().isoformat() + "Z"
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        
        log_entry = {
            "type": "node_exit",
            "session_id": session_id,
            "user_email": user_email,
            "node_name": node_name,
            "latency_ms": latency_ms,
            "timestamp": timestamp
        }
        
        blob_path = f"agent/nodes/{node_name}/{date_str}/exit_{timestamp_str}.json"
        
        def upload_async():
            try:
                if not _upload_to_blob(log_entry, blob_path):
                    _write_fallback_log(log_entry)
            except Exception as e:
                print(f"[AGENT_LOGGER] Error in async upload: {e}")
                _write_fallback_log(log_entry)
        
        thread = threading.Thread(target=upload_async, daemon=True)
        thread.start()
    except Exception as e:
        print(f"[AGENT_LOGGER] Error logging node exit: {e}")


def log_interaction(
    session_id: str,
    user_email: Optional[str],
    user_message: str,
    agent_response: str,
    latency_ms: float,
    token_usage: Optional[Dict] = None
):
    """Log user interaction (final user message and agent response)."""
    try:
        timestamp = datetime.utcnow().isoformat() + "Z"
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        
        log_entry = {
            "type": "interaction",
            "session_id": session_id,
            "user_email": user_email,
            "user_message": user_message,
            "agent_response": agent_response,
            "latency_ms": latency_ms,
            "token_usage": token_usage,
            "timestamp": timestamp
        }
        
        blob_path = f"agent/interactions/{date_str}/session_{session_id}/log_{timestamp_str}.json"
        
        def upload_async():
            try:
                if not _upload_to_blob(log_entry, blob_path):
                    _write_fallback_log(log_entry)
            except Exception as e:
                print(f"[AGENT_LOGGER] Error in async upload: {e}")
                _write_fallback_log(log_entry)
        
        thread = threading.Thread(target=upload_async, daemon=True)
        thread.start()
    except Exception as e:
        print(f"[AGENT_LOGGER] Error logging interaction: {e}")


def log_feedback_failure(
    session_id: str,
    user_email: Optional[str],
    feedback_node: str,
    reason: str
):
    """Log when a feedback/validation node fails."""
    try:
        timestamp = datetime.utcnow().isoformat() + "Z"
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        
        log_entry = {
            "type": "feedback_failure",
            "session_id": session_id,
            "user_email": user_email,
            "feedback_node": feedback_node,
            "reason": reason,
            "timestamp": timestamp
        }
        
        blob_path = f"agent/feedback_failures/{date_str}/log_{timestamp_str}.json"
        
        def upload_async():
            try:
                if not _upload_to_blob(log_entry, blob_path):
                    _write_fallback_log(log_entry)
            except Exception as e:
                print(f"[AGENT_LOGGER] Error in async upload: {e}")
                _write_fallback_log(log_entry)
        
        thread = threading.Thread(target=upload_async, daemon=True)
        thread.start()
    except Exception as e:
        print(f"[AGENT_LOGGER] Error logging feedback failure: {e}")


def log_llm_call(
    session_id: str,
    user_email: Optional[str],
    agent_name: str,
    model: str,
    prompt_preview: str,
    response_preview: str,
    token_usage: Optional[Dict] = None,
    latency_ms: Optional[float] = None
):
    """Log every internal LLM call in agents."""
    try:
        timestamp = datetime.utcnow().isoformat() + "Z"
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        
        log_entry = {
            "type": "llm_call",
            "session_id": session_id,
            "user_email": user_email,
            "agent_name": agent_name,
            "model": model,
            "prompt_preview": prompt_preview[:500] if prompt_preview else "",  # Limit to 500 chars
            "response_preview": response_preview[:500] if response_preview else "",  # Limit to 500 chars
            "token_usage": token_usage,
            "latency_ms": latency_ms,
            "timestamp": timestamp
        }
        
        blob_path = f"agent/llm_calls/{agent_name}/{date_str}/log_{timestamp_str}.json"
        
        def upload_async():
            try:
                if not _upload_to_blob(log_entry, blob_path):
                    _write_fallback_log(log_entry)
            except Exception as e:
                print(f"[AGENT_LOGGER] Error in async upload: {e}")
                _write_fallback_log(log_entry)
        
        thread = threading.Thread(target=upload_async, daemon=True)
        thread.start()
    except Exception as e:
        print(f"[AGENT_LOGGER] Error logging LLM call: {e}")

