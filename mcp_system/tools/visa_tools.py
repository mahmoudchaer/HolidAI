"""Visa-related tools for the MCP server."""

import re
from typing import Dict, Optional, Tuple
from playwright.async_api import async_playwright
from tools.doc_loader import get_doc


async def get_traveldoc_requirement(nationality: str, leaving_from: str, going_to: str):
    """
    Automates traveldoc.aero visa requirement lookup and returns
    a clean, readable structured summary of the results.
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, slow_mo=300)
        context = await browser.new_context()
        page = await context.new_page()

        print("🌍 Opening TravelDoc...")
        await page.goto("https://www.traveldoc.aero/", timeout=120000, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # Accept cookies if visible
        try:
            await page.get_by_role("button", name="Allow all").click(timeout=3000)
            print("✅ Accepted cookies")
        except:
            print("ℹ️ No cookie banner found")

        # Select Passport
        await page.locator("#DocumentType").select_option("Passport")
        print("✅ Selected: Passport")
        await page.wait_for_timeout(1000)

        # NATIONALITY
        print("➡️ Selecting nationality:", nationality)
        await page.locator("#Nationality + span.select2.select2-container span.select2-selection").click()
        await page.wait_for_selector("input.select2-search__field", state="visible", timeout=5000)
        await page.fill("input.select2-search__field", nationality)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(1000)

        # LEAVING FROM
        print("➡️ Selecting leaving from:", leaving_from)
        await page.locator("#leavingFrom + span.select2.select2-container span.select2-selection").click()
        await page.wait_for_selector("input.select2-search__field", state="visible", timeout=5000)
        await page.fill("input.select2-search__field", leaving_from)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(1000)

        # GOING TO
        print("➡️ Selecting destination:", going_to)
        await page.locator("#goingTo + span.select2.select2-container span.select2-selection").click()
        await page.wait_for_selector("input.select2-search__field", state="visible", timeout=5000)
        await page.fill("input.select2-search__field", going_to)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(1000)

        # Click "Check requirements"
        print("🔎 Checking requirements...")
        await page.get_by_role("button", name="Check requirements").click()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(4000)

        # Extract visa info
        print("📄 Extracting visa result...")
        try:
            raw_text = await page.locator("#destinationMessage").inner_text()
            raw_text = raw_text.strip()
        except:
            raw_text = await page.text_content("body") or "No visa info found."

        await browser.close()

        # Clean and structure the result
        return format_visa_info(raw_text)


def format_visa_info(text: str):
    """
    Clean and structure the extracted visa info into readable sections.
    """
    # Replace extra newlines and spaces
    clean = re.sub(r"\n{2,}", "\n", text).strip()

    # Define potential sections to split by
    sections = {
        "summary": "",
        "visa_requirements": "",
        "passport_requirements": "",
        "other_conditions": ""
    }

    # Split logically
    parts = re.split(r"(Visa requirements|Passport Requirements|Conditions apply|Extra checks required|Document requirements)", clean)
    current = "summary"

    for part in parts:
        p = part.strip()
        if not p:
            continue
        lower = p.lower()

        if "visa requirement" in lower:
            current = "visa_requirements"
        elif "passport requirement" in lower:
            current = "passport_requirements"
        elif "condition" in lower or "extra" in lower or "document" in lower:
            current = "other_conditions"
        elif "can you travel" in lower:
            sections["summary"] += p + "\n"
        else:
            sections[current] += p + "\n"

    # Format output nicely
    formatted = (
        "🧳 **Travel Summary**\n"
        + sections["summary"].strip()
        + "\n\n🌐 **Visa Requirements**\n"
        + sections["visa_requirements"].strip()
        + "\n\n📘 **Passport Requirements**\n"
        + sections["passport_requirements"].strip()
        + "\n\n⚙️ **Other Conditions / Documents**\n"
        + sections["other_conditions"].strip()
    )

    return formatted


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
    async def get_traveldoc_requirement_tool(
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
            result = await get_traveldoc_requirement(
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

