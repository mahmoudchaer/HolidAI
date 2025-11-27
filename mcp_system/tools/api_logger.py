"""API logging system for external API calls to Azure Blob Storage."""

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
project_root = Path(__file__).parent.parent.parent
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
FALLBACK_LOG_DIR = Path(__file__).parent.parent.parent / "logs" / "failed_blob_logs"
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
                        print("[API_LOGGER] Warning: AZURE_BLOB_CONNECTION_STRING not set, logging will use fallback")
                        return None
                    _blob_service_client = BlobServiceClient.from_connection_string(
                        AZURE_BLOB_CONNECTION_STRING
                    )
                except ImportError:
                    print("[API_LOGGER] Warning: azure-storage-blob not installed, logging will use fallback")
                    return None
                except Exception as e:
                    print(f"[API_LOGGER] Warning: Failed to initialize BlobServiceClient: {e}, using fallback")
                    return None
    
    return _blob_service_client


def _redact_sensitive_fields(data: Any) -> Any:
    """Recursively redact sensitive fields from data."""
    if isinstance(data, dict):
        redacted = {}
        sensitive_keys = [
            "api_key", "apikey", "apiKey", "API_KEY",
            "password", "pwd", "passwd",
            "token", "access_token", "refresh_token",
            "secret", "secret_key", "secretKey",
            "authorization", "auth",
            "card_number", "cardNumber", "credit_card", "creditCard",
            "cvv", "cvc", "security_code",
            "ssn", "social_security",
            "email"  # Redact email for privacy
        ]
        
        for key, value in data.items():
            key_lower = key.lower()
            # Check if key contains any sensitive keyword
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_sensitive_fields(value)
        return redacted
    elif isinstance(data, list):
        return [_redact_sensitive_fields(item) for item in data]
    else:
        return data


def _write_fallback_log(log_data: Dict):
    """Write log to local fallback directory."""
    try:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        log_file = FALLBACK_LOG_DIR / f"log_{timestamp}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[API_LOGGER] Error writing fallback log: {e}")


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
                print(f"[API_LOGGER] Upload attempt {attempt + 1} failed: {e}, retrying...")
            else:
                print(f"[API_LOGGER] Upload attempt {attempt + 1} failed: {e}, using fallback")
                return False
    
    return False


def log_api_call(
    service: str,
    endpoint: str,
    method: str,
    request_payload: Optional[Dict] = None,
    response_status: Optional[int] = None,
    response_time_ms: Optional[float] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Log an external API call to Azure Blob Storage.
    
    This function is non-blocking and will not raise exceptions.
    
    Args:
        service: Service name ("flights", "hotels", "activities", "visa")
        endpoint: API endpoint path (e.g., "/search")
        method: HTTP method ("GET", "POST", etc.)
        request_payload: Request payload/parameters (will be redacted)
        response_status: HTTP response status code
        response_time_ms: Response time in milliseconds
        success: Whether the call was successful
        error_message: Error message if call failed
        user_id: Optional user identifier
        session_id: Optional session identifier
    """
    try:
        # Generate trace ID
        trace_id = str(uuid.uuid4())
        
        # Get current timestamp in ISO UTC format
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        # Redact sensitive fields from request payload
        redacted_payload = _redact_sensitive_fields(request_payload) if request_payload else None
        
        # Build log entry
        log_entry = {
            "timestamp": timestamp,
            "service": service,
            "endpoint": endpoint,
            "method": method,
            "request_payload": redacted_payload,
            "response_status": response_status,
            "response_time_ms": response_time_ms,
            "success": success,
            "error_message": error_message,
            "user_id": user_id,
            "session_id": session_id,
            "trace_id": trace_id
        }
        
        # Build blob path: api/{service_name}/{YYYY-MM-DD}/log_{timestamp}.json
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        blob_path = f"api/{service}/{date_str}/log_{timestamp_str}.json"
        
        # Upload to blob storage in a separate thread (non-blocking)
        def upload_async():
            try:
                if not _upload_to_blob(log_entry, blob_path):
                    # If upload fails, write to fallback log
                    _write_fallback_log(log_entry)
            except Exception as e:
                print(f"[API_LOGGER] Error in async upload: {e}")
                _write_fallback_log(log_entry)
        
        # Start upload in background thread
        thread = threading.Thread(target=upload_async, daemon=True)
        thread.start()
        
    except Exception as e:
        # Silently handle any errors to avoid breaking the main flow
        print(f"[API_LOGGER] Error logging API call: {e}")

