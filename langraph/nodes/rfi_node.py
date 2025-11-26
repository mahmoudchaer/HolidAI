"""Request For Information (RFI) node - validates logical field completeness before Main Agent."""

import sys
import os
import json
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from state import AgentState

# Import STM module
try:
    from stm.short_term_memory import get_stm, get_summary
except ImportError:
    print("[WARNING] STM module not found, STM features will be unavailable")
    get_stm = None
    get_summary = None

# Load environment variables
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_safety_scope_prompt() -> str:
    """Get the system prompt for Safety and Scope Validation."""
    return """You are a Safety and Scope Validator for a Travel Assistant system. Your role is to:
1. Check if the user's query is SAFE (no malicious, inappropriate, or harmful content)
2. Check if the query is within the system's SCOPE (travel-related only)
3. Extract ONLY travel-related parts from mixed queries
4. Identify any non-travel-related parts that should be ignored
5. Use context from recent conversation and memory to understand vague queries

CRITICAL: This is a TRAVEL ASSISTANT ONLY. It can ONLY help with travel-related queries.

CONTEXT-AWARE VALIDATION:
- If the user's message is vague (e.g., "get cheapest one", "that flight", "get me one"), check the provided context (recent conversation and memory) to understand what they're referring to
- If previous messages were about flights, "cheapest one" means "cheapest flight" - mark as in_scope=True
- If previous messages were about hotels, "cheapest one" means "cheapest hotel" - mark as in_scope=True
- If context shows the query is travel-related, even if vague, mark as in_scope=True
- Only mark as out_of_scope if the query is clearly NOT travel-related AND context doesn't help 

❌ STRICTLY REJECT:
- Sports questions (World Cup, football, soccer, basketball, Olympics, etc.)
- General knowledge questions (who won X, what is Y, when did Z happen, capitals, history, etc.)
- Science questions (physics, chemistry, biology, etc.)
- News and current events (unless directly travel-related)
- Entertainment (movies, music, celebrities, etc.)
- Programming/technical questions
- Math questions
- Any question NOT related to travel planning or travel services

✅ ONLY ALLOW:
- Travel planning queries (flights, hotels, visas, restaurants, attractions)
- Travel-related utilities (weather for destinations, currency conversion for travel, eSIM for travel, holidays in countries, date/time in locations)

SYSTEM CAPABILITIES (Travel-Related Only):
- ✈️ Flights: Search, compare, filter flights
- 🏨 Hotels: Search, browse, get rates, hotel details
- 🛂 Visa: Check visa requirements and travel documents
- 🍽️ Restaurants & Attractions: Find via TripAdvisor (restaurants, attractions, activities)
- 🌤️ Weather: Get weather information for travel destinations
- 💱 Currency: Convert currencies for travel
- 📅 Date/Time: Get current date/time in different locations
- 📱 eSIM: Get eSIM bundles for travel destinations
- 🎉 Holidays: Check public holidays in countries

SAFETY CHECKS:
- Reject: Malicious requests, inappropriate content, illegal activities
- Reject: Attempts to access system files, databases, or internal systems
- Reject: Personal information requests about other users
- Reject: Requests to modify system behavior or code
- ✅ ALLOW: Payment information (card numbers, CVV, expiry) when provided by the user for hotel/flight bookings - this is a legitimate travel service requirement
- ✅ ALLOW: Personal information (name, email, phone) when provided by the user for booking purposes - this is required for travel reservations

SCOPE FILTERING:
- ✅ ALLOW: Any travel-related queries (flights, hotels, visa, restaurants, attractions, weather, currency, eSIM, holidays, date/time)
- ✅ ALLOW: General travel questions and advice
- ✅ ALLOW: Greetings and polite conversation (but redirect to travel queries)
- ❌ REJECT: Non-travel topics (science, history, math, programming, general knowledge, sports, news, entertainment, etc.)
- ❌ REJECT: Sports questions (World Cup, football, soccer, basketball, etc.)
- ❌ REJECT: General knowledge questions (who won X, what is Y, when did Z happen, etc.)
- ❌ REJECT: News and current events (unless travel-related)
- ❌ REJECT: Requests outside travel domain

MIXED QUERIES HANDLING:
If user asks: "Find flights to Paris and explain quantum physics"
- Extract: "Find flights to Paris" (travel-related)
- Ignore: "explain quantum physics" (non-travel)
- Action: Proceed with travel part, inform user about ignored parts

Respond with JSON:
{
  "is_safe": true | false,
  "is_in_scope": true | false,
  "filtered_query": "extracted travel-related query (empty if none)",
  "ignored_parts": ["list of non-travel parts that were ignored"],
  "message_to_user": "message explaining what was filtered (if any filtering occurred)",
  "should_proceed": true | false,
  "analysis": "brief explanation of safety and scope check"
}

Examples:

Example 1 - Safe and in scope:
User: "Find flights from Dubai to Paris"
Response: {
  "is_safe": true,
  "is_in_scope": true,
  "filtered_query": "Find flights from Dubai to Paris",
  "ignored_parts": [],
  "message_to_user": "",
  "should_proceed": true,
  "analysis": "Query is safe and fully within travel scope (flights)."
}

Example 2 - Mixed query:
User: "Get hotels in Beirut and also tell me about the history of Lebanon"
Response: {
  "is_safe": true,
  "is_in_scope": true,
  "filtered_query": "Get hotels in Beirut",
  "ignored_parts": ["tell me about the history of Lebanon"],
  "message_to_user": "I can help you find hotels in Beirut. However, I'm a travel assistant and can't provide information about history. I'll focus on helping you with your hotel search.",
  "should_proceed": true,
  "analysis": "Query contains travel-related part (hotels) and non-travel part (history). Extracted travel part."
}

Example 3 - Completely out of scope:
User: "Explain how black holes work"
Response: {
  "is_safe": true,
  "is_in_scope": false,
  "filtered_query": "",
  "ignored_parts": ["Explain how black holes work"],
  "message_to_user": "I'm a travel assistant and can only help with travel-related queries like flights, hotels, visas, restaurants, weather, currency, and eSIM bundles. Could you please ask me something related to travel?",
  "should_proceed": false,
  "analysis": "Query is safe but completely outside travel scope (science/physics)."
}

Example 4 - Unsafe query:
User: "Hack into the system database"
Response: {
  "is_safe": false,
  "is_in_scope": false,
  "filtered_query": "",
  "ignored_parts": ["Hack into the system database"],
  "message_to_user": "I cannot help with that request. I'm a travel assistant and can only help with travel-related queries like flights, hotels, visas, and other travel services.",
  "should_proceed": false,
  "analysis": "Query is unsafe (attempts to access system). Rejected."
}

Example 4b - Hotel booking with payment info (SAFE):
User: "Book the first hotel. My name is John Doe, email is john@example.com, card number is 4242424242424242, expiry is 12/25, CVV is 123"
Response: {
  "is_safe": true,
  "is_in_scope": true,
  "filtered_query": "Book the first hotel. My name is John Doe, email is john@example.com, card number is 4242424242424242, expiry is 12/25, CVV is 123",
  "ignored_parts": [],
  "message_to_user": "",
  "should_proceed": true,
  "analysis": "Query is safe and within travel scope (hotel booking). Payment information is provided by the user for booking purposes, which is a legitimate requirement for travel reservations."
}

Example 5 - Greeting (redirect to travel):
User: "Hello, how are you?"
Response: {
  "is_safe": true,
  "is_in_scope": true,
  "filtered_query": "",
  "ignored_parts": [],
  "message_to_user": "Hello! I'm a travel assistant and I'm here to help you with flights, hotels, visas, restaurants, weather, currency, eSIM bundles, and other travel-related services. What would you like help with today?",
  "should_proceed": false,
  "analysis": "Greeting detected. Polite redirect to travel services."
}

Example 6 - Travel + non-travel:
User: "Find flights to Tokyo and write me a Python script"
Response: {
  "is_safe": true,
  "is_in_scope": true,
  "filtered_query": "Find flights to Tokyo",
  "ignored_parts": ["write me a Python script"],
  "message_to_user": "I can help you find flights to Tokyo! However, I'm a travel assistant and can't write code or scripts. I'll focus on helping you with your flight search.",
  "should_proceed": true,
  "analysis": "Query contains travel part (flights) and non-travel part (programming). Extracted travel part."
}

Example 7 - Sports question (OUT OF SCOPE):
User: "Who won World Cup 2022?"
Response: {
  "is_safe": true,
  "is_in_scope": false,
  "filtered_query": "",
  "ignored_parts": ["Who won World Cup 2022?"],
  "message_to_user": "I'm a travel assistant and can only help with travel-related queries like flights, hotels, visas, restaurants, weather, currency, and eSIM bundles. I can't answer questions about sports or general knowledge. Could you please ask me something related to travel?",
  "should_proceed": false,
  "analysis": "Query is about sports (World Cup/football), which is completely outside travel scope. Rejected."
}

Example 8 - General knowledge (OUT OF SCOPE):
User: "What is the capital of France?"
Response: {
  "is_safe": true,
  "is_in_scope": false,
  "filtered_query": "",
  "ignored_parts": ["What is the capital of France?"],
  "message_to_user": "I'm a travel assistant and can only help with travel-related queries. For general knowledge questions, I'd recommend using a general-purpose assistant. How can I help you with your travel plans?",
  "should_proceed": false,
  "analysis": "Query is a general knowledge question, not travel-related. Rejected."
}"""


def get_rfi_prompt() -> str:
    """Get the system prompt for the RFI Validator."""
    return """You are a Request For Information (RFI) Validator that checks if the user provided minimum LOGICAL information to understand their travel request.

Your role:
- Check if user provided enough basic information to understand their intent
- You do NOT know about specific tools or technical requirements
- You only check LOGICAL requirements (what a human would need to know)
- If critical information is missing, check the SHORT-TERM MEMORY CONTEXT provided - it may contain relevant information from previous messages
- Use information from short-term memory to fill in missing details (e.g., if user previously mentioned a destination or date, use it)
- If information is available in short-term memory context, mark the request as "complete" even if the current message alone is incomplete

WHAT YOU CHECK (Logical Requirements Only):

1. **Flights:**
   - Need: Origin city/airport AND destination city/airport
   - Need: Travel dates (departure date minimum, return date if round-trip)
   - Examples of INCOMPLETE: "Find me flights" (no origin/destination/dates)
   - Examples of COMPLETE: "Flights from Dubai to Paris on January 15"

2. **Hotels:**
   - Need: Location (city or specific area)
   - Dates are OPTIONAL for general browsing, REQUIRED for booking/prices
   - Examples of INCOMPLETE: "Find hotels" (no location)
   - Examples of COMPLETE: "Hotels in Paris" or "Hotels in Paris for Jan 15-20"

3. **Visa:**
   - Need: Nationality/citizenship AND destination country
   - Examples of INCOMPLETE: "Do I need a visa?" (no nationality or destination)
   - Examples of COMPLETE: "UAE citizen traveling to Lebanon, need visa?"
   - **If STM context contains nationality/citizenship or destination, USE IT**

4. **Restaurants/Attractions (TripAdvisor):**
   - Need: Location (city/area)
   - Examples of INCOMPLETE: "Find good restaurants" (no location)
   - Examples of COMPLETE: "Best restaurants in Beirut"

5. **Utilities (weather, currency, etc):**
   - Weather: Need location (can be multiple: "weather in Paris and London")
   - **If user asks about weather using pronouns like "there", "that place", "the destination", check STM context for the location**
   - Currency: Need from/to currencies
   - eSIM: Need country/countries (can be multiple: "eSIM for Lebanon and UAE" is COMPLETE)
   - Holidays: Need country

IMPORTANT RULES:
- User must provide LOGICAL minimum to understand intent
- Don't ask for tool-specific details (passenger counts, room numbers, etc) - that comes later
- If user request is clear enough for a human to understand, it's good enough
- Multiple requests can be in one message (e.g., "flights and hotels in Paris")
- Multiple countries/locations are acceptable (e.g., "eSIM for Lebanon and UAE" is COMPLETE - don't ask which one)
- Check EACH request type separately
- If user mentions multiple countries/locations, they want ALL of them - don't ask for clarification
- **CRITICAL: If SHORT-TERM MEMORY CONTEXT is provided, you MUST use it to fill in missing information for ALL request types**
  - **ALWAYS assume information from STM context applies to the current request if it's relevant**
  - **For FLIGHTS**: If STM has destination/date, use them
    * Example: Previous "holidays in Qatar on December 24, 2025" + current "find flights from Lebanon" → enriched: "find flights from Lebanon to Qatar on December 24, 2025"
  - **For HOTELS**: If STM has location/date, use them
  - **For VISA**: If STM has nationality/citizenship or destination, USE THEM
    * Example: Previous "UAE citizen" or "traveling to Lebanon" + current "visa requirements" → enriched: "visa requirements for UAE citizen traveling to Lebanon"
  - **For TRIPADVISOR**: If STM has location, use it
  - **For UTILITIES**: If STM has location/country, use it
    * Example: Previous "flights to Qatar on December 24, 2025" + current "how will the weather be like there?" → enriched: "weather in Qatar on December 24, 2025"
  - **If user uses pronouns like "there", "that place", "the destination", "it", check STM for the location**
  - Extract locations, dates, nationality/citizenship, preferences, and other relevant details from the context
  - **If all required information can be found in context + current message, mark as "complete" and provide enriched_message**
  - **The enriched_message should be the complete request with all information filled in**

MISSING INFO HANDLING:
- **FIRST**: ALWAYS check if missing information is available in SHORT-TERM MEMORY CONTEXT
- **For ANY missing field (origin, destination, date, nationality, location, etc.), check STM context FIRST**
- **If information is in context, you MUST use it, mark as "complete", and provide enriched_message with all details filled in**
- **Do NOT ask the user for information that is available in STM context - use the context instead**
- **This applies to ALL request types: flights, hotels, visa, tripadvisor, utilities**
- If critical info is still missing after checking context: ask ONLY for that specific missing piece
- Be natural and conversational
- Don't overwhelm user with all possible details
- Ask for ONE thing at a time if multiple things missing

ENRICHED MESSAGE REQUIREMENT:
- **If you use STM context to fill in missing information, you MUST provide an enriched_message**
- The enriched_message should be a complete, natural request with all information filled in
- Example: If current message is "find flights from Lebanon" and STM has "Qatar" and "December 24, 2025", enriched_message should be: "find flights from Lebanon to Qatar on December 24, 2025"
- If no enrichment is needed (all info in current message), enriched_message should be the same as the original user message

Respond with JSON:
{
  "status": "complete" | "missing_info",
  "missing_fields": ["list of what's missing"],
  "question_to_user": "natural question to ask user (if missing_info)",
  "analysis": "brief explanation of what you checked",
  "enriched_message": "if status is complete and you used STM context, provide the enriched user message with extracted information (e.g., 'find flights from Lebanon to Qatar on December 24, 2025'). If no enrichment needed, use the original user message."
}

Examples:

Example 1 - Complete request:
User: "I'm a UAE citizen going to Beirut. Find flights and hotels for January 15-20."
Response: {
  "status": "complete",
  "missing_fields": [],
  "question_to_user": "",
  "analysis": "User provided: origin (UAE), destination (Beirut), dates (Jan 15-20), nationality (UAE). All logical requirements met for flights, hotels, and potential visa check."
}

Example 2 - Missing origin:
User: "Find flights to Paris"
Response: {
  "status": "missing_info",
  "missing_fields": ["origin_city", "travel_dates"],
  "question_to_user": "I'd be happy to help you find flights to Paris! Where will you be flying from, and what are your travel dates?",
  "analysis": "Destination (Paris) provided but missing origin city and travel dates.",
  "enriched_message": "Find flights to Paris"
}

Example 2b - Using STM context to complete request:
User: "can u find me flights from Lebanon ?"
STM Context: 
  USER: "what are the public holidays in Qatar on december 24 2025"
  AGENT: [response about holidays]
Response: {
  "status": "complete",
  "missing_fields": [],
  "question_to_user": "",
  "analysis": "Origin (Lebanon) provided in current message. Destination (Qatar) and date (December 24, 2025) found in STM context from previous message about holidays in Qatar. All required information available.",
  "enriched_message": "find flights from Lebanon to Qatar on December 24, 2025"
}

Example 3 - Hotels OK without dates:
User: "Show me hotels in Dubai"
Response: {
  "status": "complete",
  "missing_fields": [],
  "question_to_user": "",
  "analysis": "Location (Dubai) provided. For general hotel browsing, this is sufficient. Dates can be asked later if user wants pricing."
}

Example 4 - Visa missing nationality:
User: "Do I need a visa for France?"
Response: {
  "status": "missing_info",
  "missing_fields": ["nationality"],
  "question_to_user": "To check visa requirements for France, I need to know your nationality. What country are you a citizen of?",
  "analysis": "Destination (France) provided but nationality missing for visa check."
}

Example 5 - Multiple requests, partial info:
User: "Find me flights, hotels, and check visa requirements"
Response: {
  "status": "missing_info",
  "missing_fields": ["origin", "destination", "dates", "nationality"],
  "question_to_user": "I'd love to help you plan your trip! To get started, could you tell me: Where are you traveling from and to? What are your travel dates? And what is your nationality?",
  "analysis": "User wants flights, hotels, and visa info but didn't provide any specific details. Need all basic info."
}

Example 6 - eSIM with multiple countries (COMPLETE):
User: "get me esim bundles for Lebanon and UAE"
Response: {
  "status": "complete",
  "missing_fields": [],
  "question_to_user": "",
  "analysis": "User provided both countries (Lebanon and UAE) for eSIM bundles. This is complete - the system can fetch bundles for both countries."
}

Example 7 - eSIM with single country (COMPLETE):
User: "eSIM bundles for Japan"
Response: {
  "status": "complete",
  "missing_fields": [],
  "question_to_user": "",
  "analysis": "User provided country (Japan) for eSIM bundles. This is sufficient.",
  "enriched_message": "eSIM bundles for Japan"
}

Example 8 - Weather using STM context (pronoun reference):
User: "how will the weather be like there?"
STM Context: Previous messages mention "Qatar" and "December 24, 2025"
Response: {
  "status": "complete",
  "missing_fields": [],
  "question_to_user": "",
  "analysis": "User asked about weather using pronoun 'there'. Location (Qatar) and date (December 24, 2025) found in STM context from previous messages. All required information available.",
  "enriched_message": "weather in Qatar on December 24, 2025"
}"""


async def rfi_node(state: AgentState) -> AgentState:
    """RFI node that validates safety, scope, and logical field completeness.
    
    This node performs three validation steps:
    1. Safety check: Ensures query is safe and not malicious
    2. Scope check: Filters to travel-related queries only
    3. RFI check: Validates if user provided minimum logical information
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with routing decision
    """
    user_message = state.get("user_message", "")
    rfi_context = state.get("rfi_context", "")  # For follow-up questions - contains original request
    rfi_status = state.get("rfi_status", "")
    needs_user_input = state.get("needs_user_input", False)
    filtered_message_to_store = None  # Store filtered message from safety check
    
    print(f"\n=== RFI Validator ===")
    print(f"User message: {user_message}")
    print(f"RFI context (original request): {rfi_context}")
    print(f"RFI status: {rfi_status}, needs_user_input: {needs_user_input}")
    
    # If this is a follow-up response after asking for missing info, combine original request with new response
    if rfi_status == "missing_info" and needs_user_input and rfi_context:
        print(f"[RFI] Follow-up detected: Original request was '{rfi_context}', user now says '{user_message}'")
        # Combine original request with the new information provided
        combined_message = f"{rfi_context}. Additional information: {user_message}"
        user_message = combined_message
        print(f"[RFI] Combined message: '{user_message}'")
    
    # STEP 1: Safety and Scope Validation (only on first check, not follow-ups)
    if not rfi_context:
        print("\n--- Step 1: Safety & Scope Check ---")
        
        # Get relevant memories and STM context for Safety & Scope Check too
        relevant_memories = state.get("relevant_memories", [])
        safety_memory_context = ""
        if relevant_memories:
            safety_memory_context = f"\n\nLONG-TERM AND SHORT-TERM MEMORY CONTEXT:\n{chr(10).join(f'- {mem}' for mem in relevant_memories)}\n"
        
        # Get STM context for safety check
        safety_stm_context = ""
        session_id = state.get("session_id")
        if session_id and get_stm:
            try:
                stm_data = get_stm(session_id)
                if stm_data:
                    last_messages = stm_data.get("last_messages", [])
                    if last_messages:
                        recent_messages_text = "\n".join([
                            f"{msg['role'].upper()}: {msg['text']}"
                            for msg in last_messages[-5:]  # Last 5 messages for context
                        ])
                        safety_stm_context = f"\n\nRECENT CONVERSATION CONTEXT (from short-term memory):\n{recent_messages_text}\n\nIMPORTANT: If the user's message is vague (e.g., 'get cheapest one', 'that flight', 'get me one'), check the recent conversation context to understand what they're referring to. If previous messages were about flights, 'cheapest one' means 'cheapest flight'. If previous messages were about hotels, 'cheapest one' means 'cheapest hotel'."
            except Exception as e:
                print(f"[WARNING] Could not retrieve STM for safety check: {e}")
        
        try:
            safety_messages = [
                {"role": "system", "content": get_safety_scope_prompt()},
                {"role": "user", "content": f"User message: {user_message}{safety_memory_context}{safety_stm_context}\n\nCheck if this message is safe and within the travel assistant's scope. If the message is vague but the context shows it's travel-related (e.g., 'get cheapest one' after flight search), mark it as in_scope=True."}
            ]
            
            safety_response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=safety_messages,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            safety_result = json.loads(safety_response.choices[0].message.content)
            is_safe = safety_result.get("is_safe", True)
            is_in_scope = safety_result.get("is_in_scope", True)
            filtered_query = safety_result.get("filtered_query", "")
            ignored_parts = safety_result.get("ignored_parts", [])
            message_to_user = safety_result.get("message_to_user", "")
            should_proceed = safety_result.get("should_proceed", True)
            analysis = safety_result.get("analysis", "")
            
            print(f"Safety: is_safe={is_safe}, is_in_scope={is_in_scope}")
            print(f"Analysis: {analysis}")
            
            # Handle unsafe queries
            if not is_safe:
                print("RFI: Query is UNSAFE - rejecting")
                return {
                    "route": "conversational_agent",
                    "rfi_status": "unsafe",
                    "last_response": message_to_user or "I cannot help with that request. I'm a travel assistant and can only help with travel-related queries.",
                    "needs_user_input": True
                }
            
            # Handle completely out-of-scope queries
            if not is_in_scope or not should_proceed:
                print("RFI: Query is OUT OF SCOPE - redirecting")
                return {
                    "route": "conversational_agent",
                    "rfi_status": "out_of_scope",
                    "last_response": message_to_user or "I'm a travel assistant and can only help with travel-related queries like flights, hotels, visas, restaurants, weather, currency, and eSIM bundles. What would you like help with?",
                    "needs_user_input": True
                }
            
            # Handle filtered queries (mixed travel + non-travel)
            filtered_message_to_store = None
            if ignored_parts and filtered_query:
                print(f"RFI: Filtered query - extracted travel part: '{filtered_query}'")
                print(f"RFI: Ignored non-travel parts: {ignored_parts}")
                # Update user_message to the filtered query for further processing
                user_message = filtered_query
                # Store message to inform user about filtering
                filtered_message_to_store = message_to_user
            
            # If query was filtered but no travel part remains
            if not filtered_query and ignored_parts:
                print("RFI: Query filtered but no travel-related content remains")
                return {
                    "route": "conversational_agent",
                    "rfi_status": "out_of_scope",
                    "last_response": message_to_user or "I'm a travel assistant and can only help with travel-related queries. Could you please ask me something related to travel?",
                    "needs_user_input": True
                }
            
            print("RFI: Safety and scope check passed")
            
        except Exception as e:
            print(f"RFI: Safety/scope check error - {e}, proceeding with original query")
            # On error, proceed with original query (fail open for safety)
    
    # STEP 2: RFI Validation (logical completeness check)
    print("\n--- Step 2: RFI Completeness Check ---")
    
    # Get relevant memories from state (long-term + short-term from memory agent)
    relevant_memories = state.get("relevant_memories", [])
    memory_context = ""
    if relevant_memories:
        memory_context = f"""LONG-TERM AND SHORT-TERM MEMORY CONTEXT (from memory agent):

{chr(10).join(f"- {mem}" for mem in relevant_memories)}

CRITICAL: Use these memories to understand user preferences, previous requests, and context.
If the user says "cheapest one", "that flight", "the hotel", etc., check these memories and STM context to understand what they're referring to.
"""
        print(f"[RFI] Using {len(relevant_memories)} memories from memory agent")
    
    # Retrieve STM context if available
    stm_context = ""
    stm_data = None
    session_id = state.get("session_id")
    if session_id and get_stm:
        try:
            stm_data = get_stm(session_id)
            if stm_data:
                last_messages = stm_data.get("last_messages", [])
                summary = stm_data.get("summary", "")
                
                if last_messages:
                    # Format recent messages for context
                    recent_messages_text = "\n".join([
                        f"{msg['role'].upper()}: {msg['text']}"
                        for msg in last_messages[-10:]  # Last 10 messages
                    ])
                    
                    # Extract key information from STM for easier reference
                    import re
                    extracted_info = []
                    locations_found = set()
                    dates_found = set()
                    nationalities_found = set()
                    
                    for msg in last_messages[-10:]:
                        text = msg['text']
                        text_lower = text.lower()
                        
                        # Extract countries/locations (more comprehensive list)
                        countries = {
                            "qatar": "Qatar", "doha": "Qatar",
                            "uae": "UAE", "united arab emirates": "UAE", "dubai": "UAE", "abu dhabi": "UAE",
                            "lebanon": "Lebanon", "beirut": "Lebanon",
                            "paris": "France", "france": "France",
                            "london": "UK", "uk": "UK", "united kingdom": "UK",
                            "tokyo": "Japan", "japan": "Japan",
                            "new york": "USA", "usa": "USA", "united states": "USA"
                        }
                        
                        for keyword, country_name in countries.items():
                            if keyword in text_lower and country_name not in locations_found:
                                locations_found.add(country_name)
                                extracted_info.append(f"Location: {country_name}")
                        
                        # Extract dates (more patterns)
                        date_patterns = [
                            (r'december\s+24[,\s]+2025', "December 24, 2025"),
                            (r'dec\s+24[,\s]+2025', "December 24, 2025"),
                            (r'24[-\s/]+12[-\s/]+2025', "December 24, 2025"),
                            (r'(\w+\s+\d{1,2}[,\s]+\d{4})', None),  # General date pattern
                        ]
                        for pattern, default_date in date_patterns:
                            matches = re.findall(pattern, text_lower)
                            if matches:
                                date_str = default_date if default_date else (matches[0] if isinstance(matches[0], str) else str(matches[0]))
                                if date_str not in dates_found:
                                    dates_found.add(date_str)
                                    extracted_info.append(f"Date: {date_str}")
                                    break  # Only add one date per message
                        
                        # Extract nationality/citizenship
                        if "citizen" in text_lower or "nationality" in text_lower:
                            for keyword, country_name in countries.items():
                                if keyword in text_lower and country_name not in nationalities_found:
                                    nationalities_found.add(country_name)
                                    extracted_info.append(f"Nationality: {country_name}")
                    
                    extracted_info_text = "\n".join(extracted_info) if extracted_info else "No specific locations, dates, or nationality found in recent messages."
                    print(f"[RFI] Extracted from STM: {extracted_info_text}")
                    
                    if summary:
                        stm_context = f"""SHORT-TERM MEMORY CONTEXT (from previous messages in this conversation):

Summary of conversation so far:
{summary}

Recent messages:
{recent_messages_text}

EXTRACTED INFORMATION FROM STM (use these if missing in current request):
{extracted_info_text}

CRITICAL INSTRUCTIONS - YOU MUST FOLLOW THESE FOR ALL REQUEST TYPES:
1. **ALWAYS check STM context FIRST for ANY missing information** (destination, origin, date, nationality, location, etc.)
2. **USE THE EXTRACTED INFORMATION SECTION ABOVE** - If "Location:" is shown, use it as destination/location. If "Date:" is shown, use it as travel date. If "Nationality:" is shown, use it for visa requests.
3. **For FLIGHTS**: If missing destination/date, check EXTRACTED INFORMATION and STM - use location/destination and date from context
4. **For HOTELS**: If missing location/date, check EXTRACTED INFORMATION and STM - use location and date from context
5. **For VISA**: If missing nationality/citizenship OR destination, check EXTRACTED INFORMATION and STM - use nationality and destination from context
6. **For TRIPADVISOR**: If missing location, check EXTRACTED INFORMATION and STM - use location from context
7. **For UTILITIES**: If missing location/country, check EXTRACTED INFORMATION and STM - use location/country from context
8. **If user uses pronouns like "there", "that place", "the destination", "it" when asking about weather/location, check STM for the location**
9. If STM context mentions a location/destination (e.g., "Qatar", "Beirut", "Paris", "Lebanon", "UAE"), USE IT for the current request
9. If STM context mentions a date (e.g., "December 24, 2025", "January 15"), USE IT for the current request
10. If STM context mentions nationality/citizenship (e.g., "UAE citizen", "Lebanese", "from UAE"), USE IT for visa requests
11. DO NOT ask the user for information that is clearly available in the STM context above or in the EXTRACTED INFORMATION section
12. If all required information can be found (current message + STM context + extracted information), mark status as "complete" and provide enriched_message with all details filled in

Examples:
- Flights: Current "find flights from Lebanon" + STM "Qatar on December 24, 2025" → enriched: "find flights from Lebanon to Qatar on December 24, 2025"
- Visa: Current "visa requirements" + STM "UAE citizen" and "Lebanon" → enriched: "visa requirements for UAE citizen traveling to Lebanon"
"""
                    else:
                        stm_context = f"""SHORT-TERM MEMORY CONTEXT (from previous messages in this conversation):

Recent messages:
{recent_messages_text}

EXTRACTED INFORMATION FROM STM (use these if missing in current request):
{extracted_info_text}

CRITICAL INSTRUCTIONS - YOU MUST FOLLOW THESE FOR ALL REQUEST TYPES:
1. **ALWAYS check STM context FIRST for ANY missing information** (destination, origin, date, nationality, location, etc.)
2. **USE THE EXTRACTED INFORMATION SECTION ABOVE** - If "Location:" is shown, use it as destination/location. If "Date:" is shown, use it as travel date. If "Nationality:" is shown, use it for visa requests.
3. **For FLIGHTS**: If missing destination/date, check EXTRACTED INFORMATION and STM - use location/destination and date from context
4. **For HOTELS**: If missing location/date, check EXTRACTED INFORMATION and STM - use location and date from context
5. **For VISA**: If missing nationality/citizenship OR destination, check EXTRACTED INFORMATION and STM - use nationality and destination from context
6. **For TRIPADVISOR**: If missing location, check EXTRACTED INFORMATION and STM - use location from context
7. **For UTILITIES**: If missing location/country, check EXTRACTED INFORMATION and STM - use location/country from context
8. **If user uses pronouns like "there", "that place", "the destination", "it" when asking about weather/location, check STM for the location**
9. If STM context mentions a location/destination (e.g., "Qatar", "Beirut", "Paris", "Lebanon", "UAE"), USE IT for the current request
9. If STM context mentions a date (e.g., "December 24, 2025", "January 15"), USE IT for the current request
10. If STM context mentions nationality/citizenship (e.g., "UAE citizen", "Lebanese", "from UAE"), USE IT for visa requests
11. DO NOT ask the user for information that is clearly available in the STM context above or in the EXTRACTED INFORMATION section
12. If all required information can be found (current message + STM context + extracted information), mark status as "complete" and provide enriched_message with all details filled in

Examples:
- Flights: Current "find flights from Lebanon" + STM "Qatar on December 24, 2025" → enriched: "find flights from Lebanon to Qatar on December 24, 2025"
- Visa: Current "visa requirements" + STM "UAE citizen" and "Lebanon" → enriched: "visa requirements for UAE citizen traveling to Lebanon"
"""
                    print(f"[RFI] Retrieved STM context: {len(last_messages)} messages, summary: {'yes' if summary else 'no'}")
        except Exception as e:
            print(f"[WARNING] Could not retrieve STM context: {e}")
    
    # Build the validation message
    if rfi_status == "missing_info" and needs_user_input and rfi_context:
        # This is a follow-up after asking user for missing info
        # user_message already contains the combined request + new info
        validation_message = f"""This is a follow-up response. The user previously asked: "{rfi_context}"
The user has now provided additional information: "{state.get('user_message', '')}"

Combined request: {user_message}

{memory_context}

{stm_context}

Check if the user now provided ALL the missing information. If yes, mark as "complete" and provide enriched_message with the complete request. If still missing info, mark as "missing_info"."""
    else:
        # First time checking (may have been filtered)
        validation_message = f"""User message: {user_message}

{memory_context}

{stm_context}

Check if this message contains enough logical information to understand the travel request. 

CRITICAL: Before marking as "missing_info", you MUST check:
1. **Long-term and short-term memory context** (above) for user preferences and previous requests
2. **Short-term memory context** (STM) for missing information from recent conversation

CONTEXT UNDERSTANDING:
- If user says "cheapest one", "that flight", "the hotel", "get me one", etc., check STM and memory context to understand what they're referring to
- If previous messages mention flights, "cheapest one" likely means "cheapest flight"
- If previous messages mention hotels, "cheapest one" likely means "cheapest hotel"
- Use pronouns and references to infer meaning from context

MISSING INFORMATION CHECK:
- Missing destinations/locations (for flights, hotels, visa, tripadvisor, utilities)
  **If user uses pronouns like "there", "that place", "the destination", "it", check STM and memory for the location**
- Missing dates (for flights, hotels)
- Missing nationality/citizenship (for visa)
- Missing origins (for flights)

If any missing information is found in the memory context, STM context, or EXTRACTED INFORMATION section, use it, mark as "complete", and provide enriched_message with all details filled in.

Examples:
- User asks "how will the weather be like there?" and STM has "Qatar" → enriched: "weather in Qatar"
- User asks "get me cheapest one" and previous message was about flights → enriched: "get me cheapest flight"
- User asks "get me cheapest one" and previous message was about hotels → enriched: "get me cheapest hotel"."""
    
    # Call LLM for validation
    messages = [
        {"role": "system", "content": get_rfi_prompt()},
        {"role": "user", "content": validation_message}
    ]
    
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        validation_result = json.loads(response.choices[0].message.content)
        status = validation_result.get("status", "complete")
        missing_fields = validation_result.get("missing_fields", [])
        question = validation_result.get("question_to_user", "")
        analysis = validation_result.get("analysis", "")
        enriched_message = validation_result.get("enriched_message", user_message)  # LLM-provided enriched message
        
        print(f"RFI: Status = {status}")
        print(f"RFI: {analysis}")
        if enriched_message != user_message:
            print(f"RFI: Message enriched with STM context: '{enriched_message}'")
        
        # Get filtered message (from safety check or state for follow-ups)
        final_filtered_message = filtered_message_to_store or state.get("rfi_filtered_message", "")
        
        # If we have a filtered message, prepend it to the question
        if final_filtered_message and question:
            question = f"{final_filtered_message}\n\n{question}"
        elif final_filtered_message:
            question = final_filtered_message
        
        # Check for planner intent before routing
        user_msg_lower = user_message.lower()
        planner_keywords = [
            "save", "select", "choose", "want", "like", "add to plan", "add to my plan",
            "remove", "delete", "cancel", "update", "change", "modify",
            "show my plan", "what's in my plan", "my plan", "travel plan", "option"
        ]
        has_planner_intent = any(keyword in user_msg_lower for keyword in planner_keywords)
        
        # Route based on validation status
        if status == "complete":
            # Check if this is a planner request first
            if has_planner_intent:
                print("RFI: Information complete, but planner intent detected, routing to Planner Agent")
                result = {
                    "route": "planner_agent",
                    "rfi_status": "complete",
                    "rfi_context": "",  # Clear context
                    "needs_user_input": False,  # Clear flag
                    "rfi_missing_fields": None,  # Clear missing fields
                    "rfi_question": None  # Clear question
                }
            else:
                # User provided enough info, proceed to main agent
                print("RFI: Information complete, routing to Main Agent")
                result = {
                    "route": "main_agent",
                    "rfi_status": "complete",
                    "rfi_context": "",  # Clear context
                    "needs_user_input": False,  # Clear flag
                    "rfi_missing_fields": None,  # Clear missing fields
                    "rfi_question": None  # Clear question
                }
            
            # Include filtered message if any
            if final_filtered_message:
                result["rfi_filtered_message"] = final_filtered_message
            
            # IMPORTANT: Update user_message in state with filtered/enriched query
            # This ensures Main Agent receives the complete context
            original_message = state.get("user_message", "")
            
            # For follow-ups, use enriched_message if provided, otherwise use the combined message
            if rfi_status == "missing_info" and needs_user_input:
                # This was a follow-up - use enriched_message which should contain the complete request
                if enriched_message and enriched_message != original_message:
                    result["user_message"] = enriched_message
                    print(f"RFI: Using enriched_message from follow-up: '{enriched_message}'")
                else:
                    # Fallback to combined message
                    result["user_message"] = user_message
                    print(f"RFI: Using combined message from follow-up: '{user_message}'")
            else:
                # Regular flow - update if message was filtered or enriched
                if enriched_message != original_message:
                    result["user_message"] = enriched_message
                    if user_message != original_message:
                        print(f"RFI: Updated user_message in state from '{original_message}' to filtered query: '{user_message}'")
                    if enriched_message != user_message:
                        print(f"RFI: Enriched user_message with STM context: '{enriched_message}'")
                elif user_message != original_message:
                    # Only filtered, not enriched
                    result["user_message"] = user_message
                    print(f"RFI: Updated user_message in state from '{original_message}' to filtered query: '{user_message}'")
            
            return result
            
        elif status == "missing_info":
            # Check if this is a planner request (planner can work with incomplete info if results exist)
            if has_planner_intent:
                print("RFI: Missing info but planner intent detected, routing to Planner Agent")
                result = {
                    "route": "planner_agent",
                    "rfi_status": "missing_info",
                    "rfi_context": enriched_message if enriched_message != user_message else user_message,
                    "rfi_missing_fields": missing_fields,
                    "rfi_question": question,
                    "last_response": question,
                    "needs_user_input": True
                }
                if final_filtered_message:
                    result["rfi_filtered_message"] = final_filtered_message
                return result
            
            # Critical info missing, ask user through conversational agent (via memory node)
            print(f"RFI: Missing info - {missing_fields}")
            print(f"RFI: Asking user: {question}")
            # Store the original request in rfi_context so we can combine it with the follow-up response
            original_request = enriched_message if enriched_message != user_message else user_message
            result = {
                "route": "conversational_agent",
                "rfi_status": "missing_info",
                "rfi_context": original_request,  # Store original request for follow-up
                "rfi_missing_fields": missing_fields,
                "rfi_question": question,
                "last_response": question,  # Set the question as response
                "needs_user_input": True  # Flag that we're waiting for user
            }
            # Include filtered message if any
            if final_filtered_message:
                result["rfi_filtered_message"] = final_filtered_message
            return result
        
        else:
            # Unknown status, proceed with caution
            print(f"RFI: Unknown status '{status}', proceeding to Main Agent")
            result = {
                "route": "main_agent",
                "rfi_status": "complete"
            }
            if final_filtered_message:
                result["rfi_filtered_message"] = final_filtered_message
            return result
            
    except Exception as e:
        print(f"RFI: Validation error - {e}, proceeding to Main Agent")
        # On error, proceed to avoid blocking
        result = {
            "route": "main_agent",
            "rfi_status": "error"
        }
        error_filtered_message = filtered_message_to_store or state.get("rfi_filtered_message", "")
        if error_filtered_message:
            result["rfi_filtered_message"] = error_filtered_message
        return result

