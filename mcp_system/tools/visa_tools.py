"""Visa-related tools for the MCP server."""

import sys
import os
from pathlib import Path
from typing import Dict, Optional, Tuple
from dotenv import load_dotenv
from tools.doc_loader import get_doc

# Add visa folder to path to import traveldoc
project_root = Path(__file__).parent.parent.parent
visa_path = project_root / "visa"
sys.path.insert(0, str(visa_path))

try:
    from traveldoc import get_traveldoc_requirement
except ImportError:
    # Fallback if import fails
    def get_traveldoc_requirement(nationality: str, leaving_from: str, going_to: str):
        raise ImportError("Could not import traveldoc module. Please ensure visa/traveldoc.py exists.")


def _validate_visa_inputs(
    nationality: str,
    leaving_from: str,
    going_to: str
) -> Tuple[bool, Optional[str]]:
    """Validate visa requirement lookup inputs and return (is_valid, error_message).
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if not nationality or not isinstance(nationality, str) or not nationality.strip():
        return False, "Nationality is required and must be a non-empty string (e.g., 'Lebanon', 'United States')."
    
    if not leaving_from or not isinstance(leaving_from, str) or not leaving_from.strip():
        return False, "Leaving from (origin country) is required and must be a non-empty string (e.g., 'Lebanon', 'United States')."
    
    if not going_to or not isinstance(going_to, str) or not going_to.strip():
        return False, "Going to (destination country) is required and must be a non-empty string (e.g., 'Qatar', 'France')."
    
    return True, None


def register_visa_tools(mcp):
    """Register all visa-related tools with the MCP server."""
    
    @mcp.tool(description=get_doc("get_traveldoc_requirement", "visa"))
    def get_traveldoc_requirement_tool(
        nationality: str,
        leaving_from: str,
        going_to: str
    ) -> Dict:
        """Get visa requirements using TravelDoc.aero.
        
        This tool automates the visa requirement lookup on traveldoc.aero
        and returns structured information about visa requirements, passport
        requirements, and other travel conditions.
        
        Args:
            nationality: The traveler's nationality/passport country (e.g., "Lebanon", "United States")
            leaving_from: The origin country (e.g., "Lebanon", "United States")
            going_to: The destination country (e.g., "Qatar", "France")
        
        Returns:
            Dictionary with visa requirement information:
            {
                "error": False,
                "result": "Formatted visa requirement text",
                "nationality": nationality,
                "leaving_from": leaving_from,
                "going_to": going_to
            }
        """
        # Validate inputs first
        is_valid, validation_error = _validate_visa_inputs(
            nationality, leaving_from, going_to
        )
        if not is_valid:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "error_message": validation_error,
                "result": None,
                "suggestion": "Please provide valid country names for nationality, leaving_from, and going_to."
            }
        
        try:
            # Call the traveldoc function
            result = get_traveldoc_requirement(
                nationality.strip(),
                leaving_from.strip(),
                going_to.strip()
            )
            
            return {
                "error": False,
                "result": result,
                "nationality": nationality.strip(),
                "leaving_from": leaving_from.strip(),
                "going_to": going_to.strip()
            }
            
        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e)
            
            # Provide helpful error messages
            if "timeout" in error_message.lower() or "Timeout" in error_type:
                return {
                    "error": True,
                    "error_code": "TIMEOUT",
                    "error_message": "The visa requirement lookup took too long to complete. The TravelDoc website may be slow or unavailable.",
                    "result": None,
                    "suggestion": "Please try again in a few moments. If the problem persists, the TravelDoc service may be temporarily unavailable."
                }
            elif "browser" in error_message.lower() or "playwright" in error_message.lower():
                return {
                    "error": True,
                    "error_code": "BROWSER_ERROR",
                    "error_message": f"Browser automation error: {error_message}. Please ensure Playwright is properly installed.",
                    "result": None,
                    "suggestion": "Please run 'playwright install' to set up the browser automation. See visa/readme.md for instructions."
                }
            else:
                return {
                    "error": True,
                    "error_code": "UNEXPECTED_ERROR",
                    "error_message": f"An unexpected error occurred while checking visa requirements: {error_message}",
                    "result": None,
                    "suggestion": "Please verify the country names are correct and try again. If the problem persists, contact support."
                }

