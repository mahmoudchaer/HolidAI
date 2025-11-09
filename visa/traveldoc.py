import re
from playwright.sync_api import sync_playwright

def get_traveldoc_requirement(nationality: str, leaving_from: str, going_to: str):
    """
    Automates traveldoc.aero visa requirement lookup and returns
    a clean, readable structured summary of the results.
    """

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, slow_mo=300)
        context = browser.new_context()
        page = context.new_page()

        print("🌍 Opening TravelDoc...")
        page.goto("https://www.traveldoc.aero/", timeout=120000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Accept cookies if visible
        try:
            page.get_by_role("button", name="Allow all").click(timeout=3000)
            print("✅ Accepted cookies")
        except:
            print("ℹ️ No cookie banner found")

        # Select Passport
        page.locator("#DocumentType").select_option("Passport")
        print("✅ Selected: Passport")
        page.wait_for_timeout(1000)

        # NATIONALITY
        print("➡️ Selecting nationality:", nationality)
        page.locator("#Nationality + span.select2.select2-container span.select2-selection").click()
        page.wait_for_selector("input.select2-search__field", state="visible", timeout=5000)
        page.fill("input.select2-search__field", nationality)
        page.keyboard.press("Enter")
        page.wait_for_timeout(1000)

        # LEAVING FROM
        print("➡️ Selecting leaving from:", leaving_from)
        page.locator("#leavingFrom + span.select2.select2-container span.select2-selection").click()
        page.wait_for_selector("input.select2-search__field", state="visible", timeout=5000)
        page.fill("input.select2-search__field", leaving_from)
        page.keyboard.press("Enter")
        page.wait_for_timeout(1000)

        # GOING TO
        print("➡️ Selecting destination:", going_to)
        page.locator("#goingTo + span.select2.select2-container span.select2-selection").click()
        page.wait_for_selector("input.select2-search__field", state="visible", timeout=5000)
        page.fill("input.select2-search__field", going_to)
        page.keyboard.press("Enter")
        page.wait_for_timeout(1000)

        # Click “Check requirements”
        print("🔎 Checking requirements...")
        page.get_by_role("button", name="Check requirements").click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(4000)

        # Extract visa info
        print("📄 Extracting visa result...")
        try:
            raw_text = page.locator("#destinationMessage").inner_text().strip()
        except:
            raw_text = page.text_content("body") or "No visa info found."

        browser.close()

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


if __name__ == "__main__":
    result = get_traveldoc_requirement("Lebanon", "Lebanon", "Qatar")
    print("\n==========================")
    print(result)
