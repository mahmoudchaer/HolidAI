"""Generic helper function to lookup error codes from centralized error files."""

import json
import os
from typing import Dict, Optional


def get_error_info(error_code: str, error_file: str, error_dir: Optional[str] = None) -> Dict[str, str]:
    """Get error information for a given error code from a centralized error file.
    
    Args:
        error_code: The error code (e.g., "FLERSEA022", "HOTELERR001")
        error_file: The name of the error file (e.g., "flight_search_error") or full path
        error_dir: Optional directory name where error files are stored. 
                   Defaults to "error_handling" directory relative to project root.
    
    Returns:
        Dictionary with 'description' and 'method' keys. If error code not found,
        returns a default structure indicating unknown error.
    
    Example:
        >>> get_error_info("HOTELERR001", "hotel_search_error")
        {'description': 'Invalid check-in date', 'method': 'Hotel API'}
    """
    try:
        # Determine the path to the error file
        if os.path.isabs(error_file) or os.path.exists(error_file):
            # If it's an absolute path or exists as-is, use it directly
            error_file_path = error_file
        else:
            # Otherwise, look in the error_handling directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if error_dir:
                error_file_path = os.path.join(current_dir, "..", error_dir, error_file)
            else:
                error_file_path = os.path.join(current_dir, "..", "error_handling", error_file)
        
        # Load the error file
        with open(error_file_path, "r", encoding="utf-8") as f:
            errors = json.load(f)
        
        # Look up the error code
        error_info = errors.get(error_code)
        
        if error_info:
            return {
                "description": error_info.get("description", f"Unknown error: {error_code}"),
                "method": error_info.get("method", "Unknown")
            }
        else:
            # Error code not found in the lookup
            return {
                "description": f"Unknown error code: {error_code}. Please contact support if this persists.",
                "method": "Unknown"
            }
    
    except FileNotFoundError:
        return {
            "description": f"Error lookup file not found: {error_file}. Error code: {error_code}",
            "method": "System"
        }
    except json.JSONDecodeError as e:
        return {
            "description": f"Error parsing error lookup file '{error_file}': {str(e)}. Error code: {error_code}",
            "method": "System"
        }
    except Exception as e:
        return {
            "description": f"Error loading error lookup file '{error_file}': {str(e)}. Error code: {error_code}",
            "method": "System"
        }

