"""Conversational Agent node for LangGraph orchestration - generates final user response."""

import sys
import os
import time
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from agent_logger import log_llm_call

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import AgentState

# Load environment variables from .env file in main directory
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _parse_price(price):
    """Parse price from flight data."""
    if isinstance(price, (int, float)):
        return float(price)
    if isinstance(price, str):
        # Remove currency symbols and commas
        cleaned = price.replace("$", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except:
            return float('inf')
    return float('inf')


def _filter_flights_intelligently(user_message: str, outbound_flights: list, return_flights: list, state: dict = None) -> tuple:
    """
    Intelligently filter flights based on user's message intent.
    PRIMARY: Uses LLM semantic understanding to determine filter criteria.
    FALLBACK: Uses rule-based filtering only if LLM fails.
    
    Returns:
        (filtered_outbound, filtered_return) - filtered flight lists
    """
    if not outbound_flights and not return_flights:
        return outbound_flights, return_flights
    
    # PRIMARY METHOD: Use LLM semantic understanding to determine filter criteria
    try:
        import json
        
        filter_prompt = f"""Analyze the user's message and determine what filtering they want for flight results.

User message: "{user_message}"

Understand the user's SEMANTIC intent (not just keywords):
- "cheapest one" / "cheapest" / "lowest price" → They want the cheapest flight(s)
- "first one" / "first option" → They want the FIRST flight in the list
- "last one" / "last option" → They want the LAST flight in the list  
- "more than 31 in legroom" / "legroom over 31" / "legroom greater than 31" → Filter flights where legroom > 31 inches
- "at least 32 in legroom" / "32 inches or more legroom" → Filter flights where legroom >= 32 inches
- "direct flights" / "non-stop" / "no layovers" → Filter flights with no layovers
- "morning flights" / "early departure" → Filter flights departing 00:00-11:59
- "afternoon flights" → Filter flights departing 12:00-16:59
- "evening flights" → Filter flights departing 17:00-23:59
- "under $300" / "less than $300" → Filter flights with price < 300
- "Emirates only" / "only Emirates" → Filter flights with Emirates airline
- "shortest duration" / "fastest" → Find flights with minimum total_duration
- "show me only X" → Filter to ONLY show X (e.g., "show me only flights with more than 31 in legroom")

Return JSON:
{{
  "needs_filtering": true/false,
  "reasoning": "explanation of what user wants",
  "filter_type": "cheapest" | "first" | "last" | "direct_only" | "morning" | "afternoon" | "evening" | "airline" | "max_price" | "shortest_duration" | "legroom_min" | "custom" | "none",
  "filter_value": "value if needed (e.g., airline name, max price number, min legroom number)",
  "apply_to": "both" | "outbound" | "return",
  "keep_count": number of results to keep (e.g., 1 for "cheapest one", all for filters)
}}

Examples:
- "cheapest one" → {{"needs_filtering": true, "filter_type": "cheapest", "keep_count": 1}}
- "more than 31 in legroom" → {{"needs_filtering": true, "filter_type": "legroom_min", "filter_value": 31}}
- "first one" → {{"needs_filtering": true, "filter_type": "first", "keep_count": 1}}
- "show me all flights" → {{"needs_filtering": false, "filter_type": "none"}}"""

        session_id = state.get("session_id", "unknown") if state else "unknown"
        user_email = state.get("user_email") if state else None
        llm_start_time = time.time()
        
        filter_messages = [
            {"role": "system", "content": "You are an intelligent assistant that analyzes user intent for filtering flight results. Use semantic understanding, not keyword matching. Respond only with valid JSON."},
            {"role": "user", "content": filter_prompt}
        ]
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=filter_messages,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        llm_latency_ms = (time.time() - llm_start_time) * 1000
        
        # Log LLM call
        prompt_preview = str(filter_messages[-1].get("content", "")) if filter_messages else ""
        response_preview = response.choices[0].message.content if response.choices[0].message.content else ""
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens if hasattr(response, 'usage') and response.usage else None,
            "completion_tokens": response.usage.completion_tokens if hasattr(response, 'usage') and response.usage else None,
            "total_tokens": response.usage.total_tokens if hasattr(response, 'usage') and response.usage else None
        } if hasattr(response, 'usage') and response.usage else None
        
        log_llm_call(
            session_id=session_id,
            user_email=user_email,
            agent_name="conversational_agent",
            model="gpt-4o",
            prompt_preview=prompt_preview,
            response_preview=response_preview,
            token_usage=token_usage,
            latency_ms=llm_latency_ms
        )
        
        filter_decision = response.choices[0].message.content
        filter_criteria = json.loads(filter_decision)
        
        needs_filtering = filter_criteria.get("needs_filtering", False)
        reasoning = filter_criteria.get("reasoning", "")
        filter_type = filter_criteria.get("filter_type", "none")
        filter_value = filter_criteria.get("filter_value")
        apply_to = filter_criteria.get("apply_to", "both")
        keep_count = filter_criteria.get("keep_count", 1)
        
        print(f"[FILTER] LLM semantic filtering - needs_filtering: {needs_filtering}, filter_type: {filter_type}, reasoning: {reasoning}")
        
        if not needs_filtering or filter_type == "none":
            print(f"[FILTER] LLM selected all flights (no filtering needed)")
            return outbound_flights, return_flights
        
        filtered_outbound = outbound_flights.copy() if outbound_flights else []
        filtered_return = return_flights.copy() if return_flights else []
        
        # Apply filters based on LLM's semantic understanding
        if apply_to in ["both", "outbound"] and filtered_outbound:
            if filter_type == "cheapest":
                filtered_outbound.sort(key=lambda f: _parse_price(f.get("price", float('inf'))))
                filtered_outbound = filtered_outbound[:keep_count]
            elif filter_type == "first":
                filtered_outbound = filtered_outbound[:keep_count]
            elif filter_type == "last":
                filtered_outbound = filtered_outbound[-keep_count:] if keep_count > 0 else []
            elif filter_type == "direct_only":
                filtered_outbound = [f for f in filtered_outbound if not f.get("layovers") or len(f.get("layovers", [])) == 0]
            elif filter_type == "shortest_duration":
                filtered_outbound.sort(key=lambda f: f.get("total_duration", float('inf')))
                filtered_outbound = filtered_outbound[:keep_count]
            elif filter_type == "max_price":
                max_price = float(filter_value) if filter_value else float('inf')
                filtered_outbound = [f for f in filtered_outbound if _parse_price(f.get("price", float('inf'))) <= max_price]
            elif filter_type == "airline":
                airline_name = (filter_value or "").lower()
                filtered_outbound = [f for f in filtered_outbound if any(
                    segment.get("airline", "").lower() == airline_name 
                    for segment in f.get("flights", [])
                )]
            elif filter_type == "legroom_min":
                min_legroom = float(filter_value) if filter_value else 0
                def _meets_legroom_requirement(flight, min_val):
                    """Check if ALL flight segments have legroom > min_val."""
                    for segment in flight.get("flights", []):
                        legroom_str = segment.get("legroom", "")
                        if legroom_str and " in" in legroom_str:
                            try:
                                legroom_val = float(legroom_str.replace(" in", "").strip())
                                if legroom_val <= min_val:
                                    return False  # At least one segment doesn't meet requirement
                            except:
                                pass
                        else:
                            # If legroom info is missing, we can't verify - exclude to be safe
                            return False
                    return True  # All segments meet requirement
                filtered_outbound = [f for f in filtered_outbound if _meets_legroom_requirement(f, min_legroom)]
            elif filter_type in ["morning", "afternoon", "evening"]:
                hour_ranges = {
                    "morning": (0, 12),
                    "afternoon": (12, 17),
                    "evening": (17, 24)
                }
                start_hour, end_hour = hour_ranges.get(filter_type, (0, 24))
                def _get_departure_hour(flight):
                    try:
                        first_segment = flight.get("flights", [{}])[0]
                        time_str = first_segment.get("departure_airport", {}).get("time", "")
                        if " " in time_str:
                            time_str = time_str.split(" ")[-1]
                        return int(time_str.split(":")[0])
                    except:
                        return 0
                filtered_outbound = [f for f in filtered_outbound if start_hour <= _get_departure_hour(f) < end_hour]
        
        # Apply filters to return flights
        if apply_to in ["both", "return"] and filtered_return:
            if filter_type == "cheapest":
                filtered_return.sort(key=lambda f: _parse_price(f.get("price", float('inf'))))
                filtered_return = filtered_return[:keep_count]
            elif filter_type == "first":
                filtered_return = filtered_return[:keep_count]
            elif filter_type == "last":
                filtered_return = filtered_return[-keep_count:] if keep_count > 0 else []
            elif filter_type == "direct_only":
                filtered_return = [f for f in filtered_return if not f.get("layovers") or len(f.get("layovers", [])) == 0]
            elif filter_type == "shortest_duration":
                filtered_return.sort(key=lambda f: f.get("total_duration", float('inf')))
                filtered_return = filtered_return[:keep_count]
            elif filter_type == "max_price":
                max_price = float(filter_value) if filter_value else float('inf')
                filtered_return = [f for f in filtered_return if _parse_price(f.get("price", float('inf'))) <= max_price]
            elif filter_type == "airline":
                airline_name = (filter_value or "").lower()
                filtered_return = [f for f in filtered_return if any(
                    segment.get("airline", "").lower() == airline_name 
                    for segment in f.get("flights", [])
                )]
            elif filter_type == "legroom_min":
                min_legroom = float(filter_value) if filter_value else 0
                def _meets_legroom_requirement(flight, min_val):
                    """Check if ALL flight segments have legroom > min_val."""
                    for segment in flight.get("flights", []):
                        legroom_str = segment.get("legroom", "")
                        if legroom_str and " in" in legroom_str:
                            try:
                                legroom_val = float(legroom_str.replace(" in", "").strip())
                                if legroom_val <= min_val:
                                    return False  # At least one segment doesn't meet requirement
                            except:
                                pass
                        else:
                            # If legroom info is missing, we can't verify - exclude to be safe
                            return False
                    return True  # All segments meet requirement
                filtered_return = [f for f in filtered_return if _meets_legroom_requirement(f, min_legroom)]
            elif filter_type in ["morning", "afternoon", "evening"]:
                hour_ranges = {
                    "morning": (0, 12),
                    "afternoon": (12, 17),
                    "evening": (17, 24)
                }
                start_hour, end_hour = hour_ranges.get(filter_type, (0, 24))
                def _get_departure_hour(flight):
                    try:
                        first_segment = flight.get("flights", [{}])[0]
                        time_str = first_segment.get("departure_airport", {}).get("time", "")
                        if " " in time_str:
                            time_str = time_str.split(" ")[-1]
                        return int(time_str.split(":")[0])
                    except:
                        return 0
                filtered_return = [f for f in filtered_return if start_hour <= _get_departure_hour(f) < end_hour]
        
        print(f"[FILTER] LLM filtered results: {len(filtered_outbound)} outbound, {len(filtered_return)} return")
        return filtered_outbound, filtered_return
        
    except Exception as e:
        print(f"[FILTER] Error in LLM semantic filtering: {e}")
        import traceback
        traceback.print_exc()
        # FALLBACK: Use rule-based filtering if LLM fails
        print(f"[FILTER] Falling back to rule-based filtering")
        return _filter_flights_rule_based_fallback(user_message, outbound_flights, return_flights)


def _filter_flights_rule_based_fallback(user_message: str, outbound_flights: list, return_flights: list) -> tuple:
    """
    FALLBACK: Rule-based filtering (only used if LLM semantic filtering fails).
    This is a backup method, not the primary approach.
    """
    if not outbound_flights and not return_flights:
        return outbound_flights, return_flights
    
    try:
        user_lower = user_message.lower()
        filtered_outbound = outbound_flights.copy() if outbound_flights else []
        filtered_return = return_flights.copy() if return_flights else []
        
        # Rule-based keyword matching (FALLBACK ONLY)
        if "cheapest" in user_lower or "lowest price" in user_lower:
            filtered_outbound.sort(key=lambda f: _parse_price(f.get("price", float('inf'))))
            filtered_outbound = filtered_outbound[:1]
            if filtered_return:
                filtered_return.sort(key=lambda f: _parse_price(f.get("price", float('inf'))))
                filtered_return = filtered_return[:1]
        elif "direct" in user_lower or "non-stop" in user_lower:
            filtered_outbound = [f for f in filtered_outbound if not f.get("layovers") or len(f.get("layovers", [])) == 0]
            filtered_return = [f for f in filtered_return if not f.get("layovers") or len(f.get("layovers", [])) == 0]
        elif "morning" in user_lower:
            def _get_departure_hour(flight):
                try:
                    first_segment = flight.get("flights", [{}])[0]
                    time_str = first_segment.get("departure_airport", {}).get("time", "")
                    if " " in time_str:
                        time_str = time_str.split(" ")[-1]
                    return int(time_str.split(":")[0])
                except:
                    return 0
            filtered_outbound = [f for f in filtered_outbound if 0 <= _get_departure_hour(f) < 12]
            filtered_return = [f for f in filtered_return if 0 <= _get_departure_hour(f) < 12]
        # Add more rule-based patterns as fallback only
        
        print(f"[FILTER] Rule-based fallback filtered results: {len(filtered_outbound)} outbound, {len(filtered_return)} return")
        return filtered_outbound, filtered_return
        
    except Exception as e:
        print(f"[FILTER] Error in rule-based fallback: {e}")
        # Return original if even fallback fails
        return outbound_flights, return_flights


def remove_urls_from_flights(flight_result: dict) -> tuple:
    """Remove URLs from flight data and replace with simple IDs.
    
    Args:
        flight_result: Flight result dictionary with URLs
        
    Returns:
        tuple: (flight_result_without_urls, url_mapping)
        - flight_result_without_urls: Flight data with IDs instead of URLs
        - url_mapping: Dict mapping flight_id -> {booking_link, google_flights_url}
    """
    import copy
    if not flight_result or not isinstance(flight_result, dict):
        return flight_result, {}
    
    cleaned = copy.deepcopy(flight_result)
    url_mapping = {}
    flight_counter = 1
    
    # Process outbound flights
    if "outbound" in cleaned and isinstance(cleaned["outbound"], list):
        for flight in cleaned["outbound"]:
            flight_id = f"F{flight_counter}"
            flight_counter += 1
            
            # ALWAYS store in mapping (even if no URLs, so we can track the flight)
            booking_link = flight.get("booking_link")
            google_flights_url = flight.get("google_flights_url")
            
            # CRITICAL: If flight has no Google Flights URL, generate one from flight data
            if not google_flights_url:
                # Try to extract route info from flight segments
                flights_segments = flight.get("flights", [])
                if flights_segments:
                    first_segment = flights_segments[0]
                    last_segment = flights_segments[-1]
                    dep_airport = first_segment.get("departure_airport", {})
                    arr_airport = last_segment.get("arrival_airport", {})
                    dep_code = dep_airport.get("id") if isinstance(dep_airport, dict) else None
                    arr_code = arr_airport.get("id") if isinstance(arr_airport, dict) else None
                    dep_time = dep_airport.get("time") if isinstance(dep_airport, dict) else None
                    
                    if dep_code and arr_code:
                        # Extract date from departure time (format: "2026-01-09 22:45")
                        date_str = None
                        if dep_time and isinstance(dep_time, str):
                            date_str = dep_time.split()[0] if " " in dep_time else None
                        
                        # Generate Google Flights URL
                        from urllib.parse import quote
                        if date_str:
                            query = f"Flights from {dep_code} to {arr_code} on {date_str}"
                            google_flights_url = (
                                f"https://www.google.com/travel/flights"
                                f"?q={quote(query)}"
                                f"&hl=en&gl=us&curr=USD"
                            )
                        else:
                            query = f"Flights from {dep_code} to {arr_code}"
                            google_flights_url = (
                                f"https://www.google.com/travel/flights"
                                f"?q={quote(query)}"
                                f"&hl=en&gl=us&curr=USD"
                            )
                        print(f"[CONVERSATIONAL] Generated fallback Google Flights URL for {flight_id}: {dep_code}→{arr_code}")
            
            url_mapping[flight_id] = {
                "booking_link": booking_link,
                "google_flights_url": google_flights_url,
                "book_with": flight.get("book_with")
            }
            # Debug: Log URL status
            if booking_link or google_flights_url:
                print(f"[CONVERSATIONAL] Flight {flight_id} URLs - booking: {bool(booking_link)}, google: {bool(google_flights_url)}")
            else:
                print(f"[CONVERSATIONAL] WARNING: Flight {flight_id} has NO URLs at all!")
            
            # Replace URLs with ID
            flight["flight_id"] = flight_id
            if "booking_link" in flight:
                del flight["booking_link"]
            if "google_flights_url" in flight:
                del flight["google_flights_url"]
            # Keep book_with for display, but remove if it's just for booking_link
    
    # Process return flights
    if "return" in cleaned and isinstance(cleaned["return"], list):
        for flight in cleaned["return"]:
            flight_id = f"F{flight_counter}"
            flight_counter += 1
            
            # ALWAYS store in mapping (even if no URLs, so we can track the flight)
            booking_link = flight.get("booking_link")
            google_flights_url = flight.get("google_flights_url")
            
            # CRITICAL: If flight has no Google Flights URL, generate one from flight data
            if not google_flights_url:
                # Try to extract route info from flight segments
                flights_segments = flight.get("flights", [])
                if flights_segments:
                    first_segment = flights_segments[0]
                    last_segment = flights_segments[-1]
                    dep_airport = first_segment.get("departure_airport", {})
                    arr_airport = last_segment.get("arrival_airport", {})
                    dep_code = dep_airport.get("id") if isinstance(dep_airport, dict) else None
                    arr_code = arr_airport.get("id") if isinstance(arr_airport, dict) else None
                    dep_time = dep_airport.get("time") if isinstance(dep_airport, dict) else None
                    
                    if dep_code and arr_code:
                        # Extract date from departure time (format: "2026-01-09 22:45")
                        date_str = None
                        if dep_time and isinstance(dep_time, str):
                            date_str = dep_time.split()[0] if " " in dep_time else None
                        
                        # Generate Google Flights URL
                        from urllib.parse import quote
                        if date_str:
                            query = f"Flights from {dep_code} to {arr_code} on {date_str}"
                            google_flights_url = (
                                f"https://www.google.com/travel/flights"
                                f"?q={quote(query)}"
                                f"&hl=en&gl=us&curr=USD"
                            )
                        else:
                            query = f"Flights from {dep_code} to {arr_code}"
                            google_flights_url = (
                                f"https://www.google.com/travel/flights"
                                f"?q={quote(query)}"
                                f"&hl=en&gl=us&curr=USD"
                            )
                        print(f"[CONVERSATIONAL] Generated fallback Google Flights URL for {flight_id}: {dep_code}→{arr_code}")
            
            url_mapping[flight_id] = {
                "booking_link": booking_link,
                "google_flights_url": google_flights_url,
                "book_with": flight.get("book_with")
            }
            # Debug: Log URL status
            if booking_link or google_flights_url:
                print(f"[CONVERSATIONAL] Flight {flight_id} URLs - booking: {bool(booking_link)}, google: {bool(google_flights_url)}")
            else:
                print(f"[CONVERSATIONAL] WARNING: Flight {flight_id} has NO URLs at all!")
            
            # Replace URLs with ID
            flight["flight_id"] = flight_id
            if "booking_link" in flight:
                del flight["booking_link"]
            if "google_flights_url" in flight:
                del flight["google_flights_url"]
    
    return cleaned, url_mapping


def truncate_large_results(collected_info: dict, max_items: int = 20) -> dict:
    """Truncate large result arrays to avoid context overflow.
    
    Args:
        collected_info: Dictionary with collected results
        max_items: Maximum number of items to keep in arrays
        
    Returns:
        Truncated copy of collected_info
    """
    import copy
    truncated = copy.deepcopy(collected_info)
    
    # Truncate hotel images if present
    if "hotel_result" in truncated and isinstance(truncated["hotel_result"], dict):
        hotels = truncated["hotel_result"].get("hotels", [])
        for hotel in hotels:
            # Keep only first 3 images per hotel
            if "hotelImages" in hotel and isinstance(hotel["hotelImages"], list):
                hotel["hotelImages"] = hotel["hotelImages"][:3]
            # Truncate room types
            if "roomTypes" in hotel and isinstance(hotel["roomTypes"], list):
                hotel["roomTypes"] = hotel["roomTypes"][:2]
    
    # Truncate eSIM bundles if present
    if "utilities_result" in truncated and isinstance(truncated["utilities_result"], dict):
        if "bundles" in truncated["utilities_result"] and isinstance(truncated["utilities_result"]["bundles"], list):
            bundles = truncated["utilities_result"]["bundles"]
            if len(bundles) > max_items:
                truncated["utilities_result"]["bundles"] = bundles[:max_items]
                truncated["utilities_result"]["truncated"] = True
                truncated["utilities_result"]["total_bundles"] = len(bundles)
    
    # Truncate flight options if present (limit to 5 per direction)
    if "flight_result" in truncated and isinstance(truncated["flight_result"], dict):
        if "outbound" in truncated["flight_result"] and isinstance(truncated["flight_result"]["outbound"], list):
            outbound = truncated["flight_result"]["outbound"]
            if len(outbound) > 5:  # Hard limit: 5 outbound flights max
                truncated["flight_result"]["outbound"] = outbound[:5]
                truncated["flight_result"]["truncated"] = True
        if "return" in truncated["flight_result"] and isinstance(truncated["flight_result"]["return"], list):
            return_flights = truncated["flight_result"]["return"]
            if len(return_flights) > 5:  # Hard limit: 5 return flights max
                truncated["flight_result"]["return"] = return_flights[:5]
                truncated["flight_result"]["truncated"] = True
    
    # Truncate TripAdvisor locations if present
    if "tripadvisor_result" in truncated and isinstance(truncated["tripadvisor_result"], dict):
        if "data" in truncated["tripadvisor_result"] and isinstance(truncated["tripadvisor_result"]["data"], list):
            data = truncated["tripadvisor_result"]["data"]
            if len(data) > max_items:
                truncated["tripadvisor_result"]["data"] = data[:max_items]
                truncated["tripadvisor_result"]["truncated"] = True
    
    return truncated


def get_conversational_agent_prompt(memories: list = None, travel_plan_items: list = None) -> str:
    """Get the system prompt for the Conversational Agent.
    
    Args:
        memories: List of relevant memories about the user
        travel_plan_items: List of travel plan items from the user's plan
    """
    memory_section = ""
    if memories and len(memories) > 0:
        memory_section = "\n\nIMPORTANT - Relevant memories about this user (USE THESE IN YOUR RESPONSE):\n" + "\n".join([f"- {mem}" for mem in memories]) + "\n\nWhen providing recommendations:\n- ALWAYS consider and apply these user preferences/constraints\n- NATURALLY mention in your response that the results are based on their preferences\n- For example: 'Based on your preference for morning flights, here are some great options...' or 'I've filtered these restaurants based on your vegetarian preference...'\n- Make it clear that you're using their stored preferences to personalize the results\n- Be natural and conversational - don't make it sound robotic"
        print(f"[MEMORY] Including {len(memories)} memories in conversational agent prompt")
    else:
        print(f"[MEMORY] No memories to include in conversational agent prompt")
    
    plan_section = ""
    if travel_plan_items and len(travel_plan_items) > 0:
        import json
        plan_section = f"\n\nCURRENT TRAVEL PLAN ITEMS ({len(travel_plan_items)} items):\n" + "\n".join([f"- {item.get('title', 'Unknown')} ({item.get('type', 'unknown')}) - Status: {item.get('status', 'unknown')}" for item in travel_plan_items]) + "\n\nWhen responding:\n- If the user asks about their plan, mention these items\n- If you're confirming a save operation, acknowledge what was saved\n- Be natural and conversational about their travel plan"
        print(f"[PLAN] Including {len(travel_plan_items)} travel plan items in conversational agent prompt")
    else:
        print(f"[PLAN] No travel plan items to include in conversational agent prompt")
    
    return """You are a helpful travel assistant that provides friendly, natural, and conversational responses to users about their travel queries.

Your role:
- Take the user's original message and synthesize it with the information gathered from specialized agents
- Generate a natural, conversational response that feels human and helpful
- Present information in a clear, organized manner
- Be friendly, professional, and CONCISE - don't repeat information unnecessarily
- Use the actual data provided in the collected_info section - do not make up information
- Focus on answering what the user asked for - don't show everything if they asked for something specific (e.g., if they asked for cheapest, only show cheapest)

CRITICAL RULES - READ CAREFULLY:
1. NEVER include "Collected_info:" or any JSON structure in your response
2. NEVER show the raw JSON data to the user
3. ONLY provide the actual information extracted from the JSON, formatted naturally
4. Start your response directly with the information - do not mention "Collected_info" or "Based on the information gathered"
5. The JSON data below is for YOUR reference only - the user should NEVER see it

IMPORTANT:
- You MUST use the actual data provided in the collected_info section
- If visa_result, flight_result, hotel_result, or tripadvisor_result are present, they contain real information you need to share
- Do NOT say you don't have information if it's provided in the collected_info section - ALWAYS check the collected_info JSON before saying information is unavailable

- For flight_result: If it has an "outbound" array with items, those are outbound flight options. If it has a "return" array, those are return flight options.
  🚨 **CRITICAL - ALWAYS INCLUDE MAIN FLIGHT INFO**: When presenting flights, you MUST ALWAYS include:
    * **Price** - The flight price (e.g., "$450" or "450 USD")
    * **Origin and Destination** - Where the flight departs from and arrives to (e.g., "Dubai → Paris" or "from Dubai to Paris")
    * **Airline** - The airline name (e.g., "Emirates", "Qatar Airways")
    * **Departure and Arrival Times** - When the flight departs and arrives (e.g., "departing at 10:30 AM, arriving at 3:45 PM")
    * **Duration** - Flight duration if available (e.g., "8h 15m")
    * **Flight ID** - Each flight has a "flight_id" field (e.g., "F1", "F2"). Use this ID ONCE per flight as a booking placeholder.
  ⚠️ **IMPORTANT**: You do NOT need to include every detail (like legroom, aircraft type, seat class, airport IDs, etc.) unless the user specifically asks for them. Focus on the main information above.
  ⚠️ **CRITICAL - CHEAPEST FLIGHTS**: If the user asks for "cheapest flights" or "cheapest flight", ONLY show the cheapest outbound and cheapest return flight. Do NOT show multiple options - just the single cheapest option for each direction. The filtered flight_result will already contain only the cheapest flights, so use what's provided.
  ⚠️ **BOOKING LINKS - CRITICAL**: 
    * When presenting a flight, mention the flight_id ONCE at the end of that flight's description
    * Format: "Flight details... Price: $450. Book: F1" or "Flight details... You can book this flight: F1"
    * DO NOT mention the flight_id multiple times for the same flight - this will cause duplicate booking buttons
    * DO NOT include URLs or booking links in your text - just use the flight_id as a placeholder
    * The system will automatically replace "F1", "F2", etc. with actual booking buttons
    * Example: "Emirates flight from Dubai to Paris, $450, departs 10:30 AM. Book: F1"
  ⚠️ IMPORTANT FOR ROUND-TRIP FLIGHTS: 
    * For round-trip flights, the system makes TWO separate one-way calls
    * "outbound" array contains flights from origin to destination (e.g., Beirut → Paris)
    * "return" array contains flights from destination back to origin (e.g., Paris → Beirut)
    * Each array is independent - they are NOT combined packages
    * DO NOT combine them or say "round-trip package" - they are separate one-way flights
    * Present outbound and return flights separately, each with their own booking links
  ⚠️ IMPORTANT FOR AIRLINE LOGOS: Each flight segment may have an "airline_logo" field with an image URL
    * If a segment has "airline_logo", include it in markdown format BEFORE the airline name
    * Format like: "![Airline](logo_url) **Airline Name** Flight XX"
    * This will display the airline logo in the chat
  Example good response: "I found an Emirates flight from Dubai to Paris for $450. It departs at 10:30 AM and arrives at 3:45 PM, with a duration of 8h 15m. Book: F1"
  Only report an error if the result has "error": true AND no outbound flights data.

- For visa_result: **CRITICAL**: Check the "result" field FIRST - if it has content (even if "error": true), that contains the visa requirement information. You MUST present ALL available visa information in detail:
  * **Present all sections**: Include all sections from the result field:
    - Travel Summary (whether visa is required or not)
    - Visa Requirements section (all details about visa types, application process, requirements)
    - Passport Requirements section (validity, expiration rules, etc.)
    - Other Conditions/Documents section (any additional requirements, documents needed, special conditions)
    - Any additional important details or notes
  * **Show complete information**: Don't just summarize - present the full details from each section. If the result says "A visa is required" and provides details about the visa application process, passport validity, required documents, etc., include ALL of that information.
  * **Preserve structure**: Keep the logical structure and organization of the information (use section headers, bullet points, etc. as appropriate)
  * **Preserve markdown formatting**: Keep important markdown formatting (like **bold** markers, emojis, section headers) that may be present in the original result
  * **Skip only promotional content**: You can skip promotional content (like eSIM ads) that appears in the result, but include ALL actual visa-related information
  Only report an error if the result has "error": true AND the "result" field is empty or missing.

- For hotel_result: If it has a "hotels" array with items, those are real hotels you found - present them to the user. 
  ⚠️ CRITICAL: Hotels may or may not have price information depending on the search type:
    * If hotels have "roomTypes" or "rates" fields with prices → show the actual prices
    * If hotels DON'T have price fields → DO NOT make up prices! Just show hotel information (name, rating, location, amenities)
    * NEVER hallucinate or invent prices - only show prices if they exist in the data
  ⚠️ BOOKING REQUESTS: If hotel_result has "_booking_intent": true, the user wants to book a hotel. 
    * DO NOT ask for payment information in chat (this is a security risk)
    * Instead, provide a secure booking link: [Complete Booking](/booking?hotel_id={_booking_hotel_id}&rate_id={_booking_rate_id}&hotel_name={_booking_hotel_name}&checkin={_booking_checkin}&checkout={_booking_checkout}&price={_booking_price})
    * Tell the user: "I've prepared your booking! Please click the link below to securely complete your reservation with payment details."
    * The booking link will take them to a secure page where they can enter payment information safely
  Only report an error if the result has "error": true AND no hotels data.

- For tripadvisor_result: If it has a "data" array with items, those are real locations/restaurants/attractions you found.
  * Present the locations naturally in your response, similar to how you present hotels or flights
  * Include relevant details like name, address, rating (if available), and any notable features
  * Format them in a clear, readable way (use bullet points or numbered lists if there are many)
  * If there are many results, you can summarize the top options or group them by type
  * Be conversational and helpful - describe what makes each location interesting or relevant to the user's query
  * Only report an error if the result has "error": true AND no data.

- For utilities_result: This contains utility information (weather, currency conversion, date/time, eSIM bundles, or holidays). Present the information naturally based on what tool was used:
  * **CRITICAL - MULTIPLE RESULTS**: If utilities_result has "multiple_results": true, it contains a "results" array where each item has "tool", "args", and "result". You MUST check each item in the "results" array:
    - For eSIM bundles: Look for items where "tool" == "get_esim_bundles", then check the nested "result" object for a "bundles" array (path: utilities_result.results[].result.bundles)
    - For holidays: Look for items where "tool" == "get_holidays", then check the nested "result" object for a "holidays" array (path: utilities_result.results[].result.holidays)
    - Process each result and present all information together naturally.
  * **SINGLE RESULT**: If utilities_result does NOT have "multiple_results": true, check directly:
    - For eSIM bundles: Check utilities_result["bundles"] array
    - For holidays: Check utilities_result["holidays"] array
  * For weather: Show temperature, conditions, etc. If multiple weather results, show each location separately.
  * For currency: Show the conversion result.
  * For date/time: Show the current date and time.
  * For eSIM bundles: When you find bundles (either in utilities_result["bundles"] OR in utilities_result.results[].result.bundles), you MUST present ALL available bundles, not just a summary. For each bundle, include:
    - Provider name
    - Plan name/details (e.g., "Europe 100GB – 10 Days")
    - Validity period
    - Price
    - Purchase link as a clickable markdown link: Format like "[Provider Name - Plan Name]($link)" or "Plan Name for $price - [Purchase here]($link)"
    Present them in a clear list format, showing all bundles that are available. DO NOT summarize or say "there are multiple plans available" - actually list them all. If there are many bundles (20+), you can group them by provider or data size, but still show all of them.
    If eSIM data is unavailable (error with "recommended_providers"), present the recommended provider links as clickable options: "Try these eSIM providers: [Airalo](url), [Holafly](url), etc."
  * For holidays: When you find holidays (either in utilities_result["holidays"] OR in utilities_result.results[].result.holidays), present each holiday with its name, date, type (e.g., "National holiday", "Observance"), and description. Format dates in a readable way (e.g., "January 1, 2024" instead of "2024-01-01"). Group holidays by month if there are many.
    ⚠️ CRITICAL: If the user asked to avoid holidays AND you're showing flights/hotels, you MUST explain which dates were holidays and why the selected dates avoid them. Example: "I found that January 1st is New Year's Day (national holiday) in France, so I selected dates from January 8-14 which avoid all holidays."
    Only report an error if the result has "error": true AND no actual data found in either location (direct or nested).

- Format dates in a natural, readable way (e.g., "December 12, 2025" instead of "2025-12-12")
- Extract and present flight details (airline, times, prices) from the flight_result data
- Extract and present visa requirements from the visa_result data
- Extract and present hotel names, prices, addresses, and other relevant details from the hotel_result data
- Extract and present restaurant/location names, addresses, and other relevant details from the tripadvisor_result data

TRANSPARENCY IN REASONING:
- When the user has specific constraints (avoid holidays, specific budget, dates, etc.), ALWAYS explain your thought process
- Show what you checked, what you found, and WHY you selected the specific options you're recommending
- Example: "You wanted to avoid holidays, so I checked January 2026 and found that January 1st is New Year's Day. I selected flights and hotels from January 8-14 which avoid all holidays."

Your response should start directly with the information, like:
"I've found some great options for your trip to Beirut! As a citizen of the United Arab Emirates, you do not require a visa..."

NOT like:
"Collected_info: { ... } Based on the information gathered..."

Remember: The JSON is invisible to the user - only show the extracted information in a natural, conversational format.""" + memory_section + plan_section


async def conversational_agent_node(state: AgentState) -> AgentState:
    """Conversational Agent node that generates the final user response.
    
    Args:
        state: Current agent state with all collected information
        
    Returns:
        Updated agent state with final response
    """
    user_message = state.get("user_message", "")
    context = state.get("context", {})
    collected_info = state.get("collected_info", {})
    conversational_feedback_message = state.get("conversational_feedback_message")
    rfi_filtered_message = state.get("rfi_filtered_message")  # Message about filtered non-travel parts
    rfi_status = state.get("rfi_status")  # Check if query was rejected (unsafe/out_of_scope)
    last_response = state.get("last_response", "")  # May contain rejection message from RFI
    relevant_memories = state.get("relevant_memories") or []  # Relevant memories for this user
    travel_plan_items = state.get("travel_plan_items", [])  # Travel plan items from database
    session_id = state.get("session_id")
    needs_planner = state.get("needs_planner", False)  # Check if planner agent was called
    
    # Detect if user is choosing/selecting an option (add operation)
    user_msg_lower = user_message.lower()
    is_choosing_option = any(phrase in user_msg_lower for phrase in [
        "choose option", "select option", "want option", "option number", "option nb", 
        "option #", "i'll take option", "i'll choose option", "i will choose option",
        "i will take option", "add option", "save option"
    ])
    
    # Also check context for results
    if context.get("flight_result"):
        collected_info["flight_result"] = context.get("flight_result")
    if context.get("hotel_result"):
        collected_info["hotel_result"] = context.get("hotel_result")
    if context.get("visa_result"):
        collected_info["visa_result"] = context.get("visa_result")
    if context.get("tripadvisor_result"):
        collected_info["tripadvisor_result"] = context.get("tripadvisor_result")
    if context.get("utilities_result"):
        collected_info["utilities_result"] = context.get("utilities_result")
    
    # CRITICAL: Use LLM semantic understanding to determine if we need flight_result from STM
    # Always retrieve from STM if flight_result is missing (let LLM decide if it's needed)
    if not collected_info.get("flight_result") and session_id:
        try:
            from stm.short_term_memory import get_last_results
            last_results = get_last_results(session_id)
            if last_results and last_results.get("flight_result"):
                collected_info["flight_result"] = last_results["flight_result"]
                print(f"[CONVERSATIONAL] Retrieved flight_result from STM (LLM will determine if filtering needed): {len(last_results.get('flight_result', {}).get('outbound', []))} outbound flights")
        except Exception as e:
            print(f"[CONVERSATIONAL] WARNING: Could not retrieve flight_result from STM: {e}")
    
    # Debug: Log what we're passing to the LLM
    if collected_info.get("hotel_result"):
        hotel_result = collected_info["hotel_result"]
        if isinstance(hotel_result, dict):
            hotels_count = len(hotel_result.get("hotels", []))
            has_error = hotel_result.get("error", False)
            print(f"Conversational agent: Received hotel_result with {hotels_count} hotel(s), error: {has_error}")
    if collected_info.get("tripadvisor_result"):
        tripadvisor_result = collected_info["tripadvisor_result"]
        if isinstance(tripadvisor_result, dict):
            data_count = len(tripadvisor_result.get("data", []))
            has_error = tripadvisor_result.get("error", False)
            print(f"Conversational agent: Received tripadvisor_result with {data_count} location(s), error: {has_error}")
    if collected_info.get("flight_result"):
        flight_result = collected_info["flight_result"]
        if isinstance(flight_result, dict):
            has_error = flight_result.get("error", False)
            outbound = flight_result.get("outbound", [])
            outbound_count = len(outbound) if isinstance(outbound, list) else 0
            print(f"Conversational agent: Received flight_result with {outbound_count} flight option(s), error: {has_error}")
    if collected_info.get("visa_result"):
        visa_result = collected_info["visa_result"]
        if isinstance(visa_result, dict):
            has_error = visa_result.get("error", False)
            has_result = "result" in visa_result or "data" in visa_result
            print(f"Conversational agent: Received visa_result, has data: {has_result}, error: {has_error}")
    if collected_info.get("utilities_result"):
        utilities_result = collected_info["utilities_result"]
        if isinstance(utilities_result, dict):
            has_error = utilities_result.get("error", False)
            print(f"Conversational agent: Received utilities_result, error: {has_error}")
    
    # If query was rejected by RFI (unsafe or out of scope), just return the rejection message
    if rfi_status in ["unsafe", "out_of_scope"] and last_response:
        print(f"Conversational Agent: Query was {rfi_status}, returning rejection message")
        updated_state = state.copy()
        updated_state["last_response"] = last_response
        updated_state["route"] = "end"
        return updated_state
    
    # If RFI is asking for missing info, return the pre-prepared question without calling LLM
    # This prevents the LLM from seeing the original user message and answering filtered parts
    if rfi_status == "missing_info" and last_response:
        print("Conversational Agent: RFI asking for missing info, returning pre-prepared question")
        updated_state = state.copy()
        updated_state["last_response"] = last_response
        updated_state["route"] = "end"
        return updated_state
    
    # If planner has set a response (e.g., "no results available"), use it directly
    if last_response and ("No search results available" in last_response or "no results available" in last_response.lower() or "search first" in last_response.lower()):
        print("Conversational Agent: Using planner's message about no results")
        updated_state = state.copy()
        updated_state["last_response"] = last_response
        updated_state["route"] = "end"
        return updated_state
    
    # Prepare messages for LLM
    import json
    
    # Truncate large results to avoid context overflow
    # For flights: limit to 5 per direction (already done in summarizer, but ensure here too)
    truncated_info = truncate_large_results(collected_info, max_items=5)  # Reduced from 20 to 5 for flights
    
    # CRITICAL: Remove URLs from flights and replace with IDs to reduce context size
    flight_url_mapping = {}
    if truncated_info.get("flight_result"):
        flight_result_cleaned, flight_url_mapping = remove_urls_from_flights(truncated_info["flight_result"])
        truncated_info["flight_result"] = flight_result_cleaned
        print(f"[CONVERSATIONAL] Removed URLs from flights, created {len(flight_url_mapping)} ID mappings")
    
    # CRITICAL: If user is choosing/selecting an option, don't include flight/hotel/restaurant results in the prompt
    # This prevents the LLM from re-showing all options when user just wants confirmation
    display_info = truncated_info.copy() if truncated_info else {}
    if is_choosing_option or needs_planner:
        # Remove flight, hotel, and tripadvisor results to prevent re-showing all options
        if "flight_result" in display_info:
            del display_info["flight_result"]
            print(f"[CONVERSATIONAL] Removed flight_result from prompt (user is choosing an option)")
        if "hotel_result" in display_info:
            del display_info["hotel_result"]
            print(f"[CONVERSATIONAL] Removed hotel_result from prompt (user is choosing an option)")
        if "tripadvisor_result" in display_info:
            del display_info["tripadvisor_result"]
            print(f"[CONVERSATIONAL] Removed tripadvisor_result from prompt (user is choosing an option)")
    
    # Add special instruction if user is choosing an option
    special_instruction = ""
    if is_choosing_option or needs_planner:
        special_instruction = """
⚠️⚠️⚠️ CRITICAL - USER IS CHOOSING/SELECTING AN OPTION ⚠️⚠️⚠️:
- The user has chosen/selected an option (e.g., "I will choose option 2", "I want option 3", "save restaurant option 1")
- The planner agent has already added the selected item to their travel plan
- Your response should ONLY confirm what was added - DO NOT re-show all search results
- DO NOT list all flights/hotels/restaurants again - just acknowledge the addition
- DO NOT generate TripAdvisor greetings like "Here are some great restaurants!" - the user is CONFIRMING a selection, not searching
- Example good response: "Perfect! I've added option 2 to your travel plan." or "Great! I've saved that restaurant to your plan."
- Example bad response: "Here are all the flight options again: [lists all flights]" or "Here are some great restaurants in Lebanon!"
- Keep your response SHORT and focused on confirming the addition"""
    
    user_content = f"""User's original message: {user_message}
{special_instruction}

Below is the data collected from specialized agents (THIS IS FOR YOUR REFERENCE ONLY - DO NOT INCLUDE IT IN YOUR RESPONSE):
{json.dumps(display_info, indent=2, ensure_ascii=False) if display_info else "No information was collected from specialized agents."}

IMPORTANT INSTRUCTIONS:
- Extract the relevant information from the JSON above
- Present it in a natural, conversational way
- DO NOT include "Collected_info:", "Based on the information gathered", or any JSON structure in your response
- Start your response directly with the information (e.g., "I've found some great options..." or "Here's what I found...")
- The user should never see the JSON data - only the formatted information
- **CRITICAL**: If the user is choosing/selecting an option (e.g., "I will choose option 2"), just confirm the addition - DO NOT re-show all search results. Simply acknowledge what was added to their plan.
- **If there are errors in the collected data (error: true), explain the specific error to the user in a helpful way, including the error_message and suggestion if available**
- For eSIM bundles: ALWAYS include clickable links using markdown format [text](url) for each bundle's purchase link
- If data was truncated (indicated by "truncated": true or "limited": true), mention that more options are available
- Make sure all links are properly formatted as markdown links so they appear as clickable in the UI"""
    
    # If there's feedback from the feedback node, include it
    if conversational_feedback_message:
        user_content += f"""

FEEDBACK FROM VALIDATOR:
{conversational_feedback_message}

Please revise your response based on this feedback to fix the issues mentioned."""
        print(f"Conversational Agent: Received feedback - {conversational_feedback_message}")
    
    messages = [
        {"role": "system", "content": get_conversational_agent_prompt(memories=relevant_memories, travel_plan_items=travel_plan_items)},
        {"role": "user", "content": user_content}
    ]
    
    # Helper function to clean response and remove any JSON/Collected_info references
    def clean_response(text: str) -> str:
        """Remove any 'Collected_info:' or JSON structures from the response."""
        if not text:
            return text
        
        # First, try to find and remove everything from "Collected_info:" to the first actual content
        text_lower = text.lower()
        collected_info_index = text_lower.find('collected_info')
        
        if collected_info_index != -1:
            # Find where the JSON block ends (look for closing brace followed by actual content)
            # Try to find the end of the JSON structure
            remaining_text = text[collected_info_index:]
            
            # Look for patterns like "}\n\n" or "}\nBased on" or "}\nI've" etc.
            # Find the last closing brace before actual content
            brace_count = 0
            json_end = -1
            in_string = False
            escape_next = False
            
            for i, char in enumerate(remaining_text):
                if escape_next:
                    escape_next = False
                    continue
                if char == '\\':
                    escape_next = True
                    continue
                if char == '"' and not escape_next:
                    in_string = not in_string
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            # Found the end of the JSON object
                            # Look ahead for actual content (not just whitespace/braces)
                            ahead = remaining_text[i+1:].strip()
                            if ahead and not ahead.startswith('{') and not ahead.startswith('}'):
                                json_end = collected_info_index + i + 1
                                break
            
            if json_end != -1:
                # Extract everything after the JSON
                cleaned = text[json_end:].strip()
                # Remove leading empty lines
                while cleaned.startswith('\n'):
                    cleaned = cleaned[1:]
                text = cleaned
        
        # Additional cleanup: remove any lines that are pure JSON structure
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            # Skip lines that are clearly JSON structure
            if (stripped.startswith('{') or 
                stripped.startswith('}') or 
                (stripped.startswith('"') and ':' in stripped and (stripped.endswith(',') or stripped.endswith('"')))):
                continue
            # Skip lines that are just "Collected_info:"
            if 'collected_info' in stripped.lower() and len(stripped) < 50:
                continue
            cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines).strip()
        
        # Final check: if the response still starts with JSON-like content, try to find where actual content begins
        if result.startswith('{') or result.startswith('"'):
            # Try to find the first line that doesn't look like JSON
            lines = result.split('\n')
            for i, line in enumerate(lines):
                stripped = line.strip()
                if (not stripped.startswith('{') and 
                    not stripped.startswith('}') and 
                    not stripped.startswith('"') and
                    'collected_info' not in stripped.lower() and
                    len(stripped) > 10):  # Actual content is usually longer
                    result = '\n'.join(lines[i:]).strip()
                    break
        
        return result
    
    # Initialize final_response to avoid UnboundLocalError
    final_response = ""
    
    # Call LLM to generate response (TripAdvisor results are handled like any other data)
    import traceback
    try:
        session_id = state.get("session_id", "unknown")
        user_email = state.get("user_email")
        llm_start_time = time.time()
        
        # Call OpenAI API (direct call - OpenAI client handles its own timeouts)
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            temperature=0.7
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
            agent_name="conversational_agent",
            model="gpt-4.1",
            prompt_preview=prompt_preview,
            response_preview=response_preview,
            token_usage=token_usage,
            latency_ms=llm_latency_ms
        )
        
        message = response.choices[0].message
        raw_response = message.content or "I apologize, but I couldn't generate a response. Please try again."
        
        # Clean the response to remove any JSON/Collected_info references
        final_response = clean_response(raw_response)
        
        # Replace flight IDs with actual booking URLs in the response
        if flight_url_mapping:
            import re
            # Step 1: Remove any raw URLs that leaked through (long http/https links not in markdown)
            # This pattern matches URLs that are NOT inside markdown links
            # More aggressive: match any long URL that's not already in [text](url) format
            url_pattern = r'(?<!\[)(?<!\]\()https?://[^\s\)]+(?!\))'
            # But first, let's be more specific - match URLs that are clearly flight booking URLs
            flight_url_pattern = r'https?://(www\.)?google\.com/travel/clk[^\s\)]+'
            final_response = re.sub(flight_url_pattern, '', final_response)
            # Then remove any remaining raw URLs
            final_response = re.sub(url_pattern, '', final_response)
            
            # Step 2: Clean up any duplicate booking button patterns
            # Remove patterns like "Book Now | View on Google Flights" that appear multiple times
            duplicate_buttons = r'(\[Book Now\]\([^\)]+\)\s*\|\s*\[View on Google Flights\]\([^\)]+\)\s*){2,}'
            final_response = re.sub(duplicate_buttons, lambda m: m.group(0).split('|')[0] + ' | ' + m.group(0).split('|')[1] if '|' in m.group(0) else m.group(0), final_response)
            
            # Step 3: Replace each flight ID ONCE with booking links
            replaced_count = 0
            for flight_id, urls in flight_url_mapping.items():
                    # Skip if no URLs available
                    if not urls.get("booking_link") and not urls.get("google_flights_url"):
                        print(f"[CONVERSATIONAL] Skipping {flight_id} - no URLs available")
                        continue
                    
                    booking_links = []
                    if urls.get("booking_link"):
                        booking_links.append(f'[Book Now]({urls["booking_link"]})')
                    if urls.get("google_flights_url"):
                        booking_links.append(f'[View on Google Flights]({urls["google_flights_url"]})')
                    
                    if not booking_links:
                        continue
                    
                    links_text = f'{" | ".join(booking_links)}'
                    
                    # Check if this flight ID is in the response
                    if flight_id not in final_response:
                        continue
                    
                    # Check if this flight ID already has booking links immediately after it (within 50 chars)
                    id_pos = final_response.find(flight_id)
                    if id_pos != -1:
                        # Check only the immediate area after the flight ID (50 chars)
                        after_context = final_response[id_pos + len(flight_id):id_pos + len(flight_id) + 50]
                        if '[Book Now]' in after_context:
                            # Already has links very close, skip to avoid duplicates
                            print(f"[CONVERSATIONAL] Skipping {flight_id} - already has links nearby")
                            continue
                    
                    # Replace flight ID with booking links (only first occurrence)
                    # Try patterns in order of specificity
                    patterns = [
                        rf'Book:\s*{re.escape(flight_id)}(?=\s|$|\.|,|\n)',
                        rf'book:\s*{re.escape(flight_id)}(?=\s|$|\.|,|\n)',
                        rf'Use flight_id\s+{re.escape(flight_id)}(?=\s|$|\.|,|\n)',
                        rf'Use\s+{re.escape(flight_id)}(?=\s|$|\.|,|\n)',
                        rf'{re.escape(flight_id)}\s+for booking',
                        rf'\b{re.escape(flight_id)}\b(?=\s|$|\.|,|\n)'  # Standalone
                    ]
                    
                    replaced = False
                    for pattern in patterns:
                        if re.search(pattern, final_response, re.IGNORECASE):
                            final_response = re.sub(pattern, links_text, final_response, count=1, flags=re.IGNORECASE)
                            replaced = True
                            replaced_count += 1
                            print(f"[CONVERSATIONAL] Replaced {flight_id} using pattern: {pattern[:30]}...")
                            break
                    
                    # If still not replaced, insert links after the flight ID
                    if not replaced:
                        id_pos = final_response.find(flight_id)
                        if id_pos != -1:
                            # Insert booking links right after the flight ID
                            final_response = final_response[:id_pos + len(flight_id)] + f' {links_text}' + final_response[id_pos + len(flight_id):]
                            replaced_count += 1
                            print(f"[CONVERSATIONAL] Inserted links after {flight_id} (fallback)")
            
            # CRITICAL: Clean up any malformed markdown links (e.g., [Book Now](F5 Book Now | View on Google Flights))
            # Fix patterns like [Text](F5 [Book Now](url)) or [Text](F5 Book Now | View on Google Flights)
            malformed_pattern = r'\[([^\]]+)\]\(F\d+\s+\[([^\]]+)\]\([^\)]+\)[^\)]*\)'
            final_response = re.sub(malformed_pattern, r'\2', final_response)
            
            # Also fix patterns where flight ID is inside markdown link text
            malformed_pattern2 = r'\[([^\]]*F\d+[^\]]*)\]\(([^\)]+)\)'
            def fix_malformed_link(match):
                link_text = match.group(1)
                # Extract flight ID if present
                flight_id_match = re.search(r'F\d+', link_text)
                if flight_id_match:
                    flight_id = flight_id_match.group(0)
                    # If URL is a flight URL, replace with proper format
                    if flight_id in flight_url_mapping:
                        urls = flight_url_mapping[flight_id]
                        booking_links = []
                        if urls.get("booking_link"):
                            booking_links.append(f'[Book Now]({urls["booking_link"]})')
                        if urls.get("google_flights_url"):
                            booking_links.append(f'[View on Google Flights]({urls["google_flights_url"]})')
                        if booking_links:
                            return f"{flight_id} {' | '.join(booking_links)}"
                return match.group(0)
            final_response = re.sub(malformed_pattern2, fix_malformed_link, final_response)
            
            # CRITICAL: Clean up any remaining malformed URLs that might have leaked through
            # Remove any very long URLs (over 200 chars) that aren't in markdown format
            very_long_url_pattern = r'(?<!\[)(?<!\]\()https?://[^\s\)]{200,}(?!\))'
            final_response = re.sub(very_long_url_pattern, '', final_response)
            
            # CRITICAL: Also check for any raw booking URLs or Google Flights URLs in the response and replace them
            # This handles cases where the LLM might have included URLs directly (but not if already in markdown)
            for flight_id, urls in flight_url_mapping.items():
                # Build links text for this flight
                flight_booking_links = []
                if urls.get("booking_link"):
                    flight_booking_links.append(f'[Book Now]({urls["booking_link"]})')
                if urls.get("google_flights_url"):
                    flight_booking_links.append(f'[View on Google Flights]({urls["google_flights_url"]})')
                flight_links_text = f'{" | ".join(flight_booking_links)}' if flight_booking_links else ""
                
                if urls.get("booking_link") and urls["booking_link"] in final_response:
                    # Only replace if not already in a markdown link
                    if f"]({urls['booking_link']})" not in final_response:
                        # Replace raw booking link with flight ID links
                        final_response = final_response.replace(urls["booking_link"], f"{flight_id} {flight_links_text}")
                        print(f"[CONVERSATIONAL] Replaced raw booking URL with {flight_id} links")
                if urls.get("google_flights_url") and urls["google_flights_url"] in final_response:
                    # Don't replace Google Flights URLs if they're already part of a markdown link
                    if f"]({urls['google_flights_url']})" not in final_response:
                        # Replace raw Google Flights URL with flight ID links
                        final_response = final_response.replace(urls["google_flights_url"], f"{flight_id} {flight_links_text}")
                        print(f"[CONVERSATIONAL] Replaced raw Google Flights URL with {flight_id} links")
            
            print(f"[CONVERSATIONAL] Replaced {replaced_count} out of {len(flight_url_mapping)} flight IDs with booking URLs")
        
        # Check if booking intent is present and add booking URL
        hotel_result = collected_info.get("hotel_result")
        if hotel_result and isinstance(hotel_result, dict) and hotel_result.get("_booking_intent"):
            booking_hotel_id = hotel_result.get("_booking_hotel_id")
            booking_rate_id = hotel_result.get("_booking_rate_id")
            booking_hotel_name = hotel_result.get("_booking_hotel_name", "Selected Hotel")
            booking_checkin = hotel_result.get("_booking_checkin")
            booking_checkout = hotel_result.get("_booking_checkout")
            booking_price = hotel_result.get("_booking_price", "")
            
            if booking_hotel_id and booking_rate_id:
                # Generate secure booking URL
                from urllib.parse import quote
                booking_url = f"/booking?hotel_id={quote(booking_hotel_id)}&rate_id={quote(booking_rate_id)}&hotel_name={quote(booking_hotel_name)}&checkin={quote(booking_checkin)}&checkout={quote(booking_checkout)}"
                if booking_price and booking_price != "N/A":
                    booking_url += f"&price={quote(str(booking_price))}"
                
                # Append booking link to response
                booking_message = f"\n\n🔒 **Secure Booking**\n\nI've prepared your booking for {booking_hotel_name}! For your security, please complete your reservation and payment details on our secure booking page:\n\n[Complete Your Booking →]({booking_url})\n\nThis secure page will allow you to enter your payment information safely."
                final_response += booking_message
                print(f"[CONVERSATIONAL] Added booking URL: {booking_url}")
    except Exception as e:
        error_msg = str(e)
        error_trace = traceback.format_exc()
        # Log the error for debugging
        print(f"Error in conversational_agent_node: {error_msg}")
        print(f"Traceback: {error_trace}")
        
        # Handle context length errors specifically
        if "context_length" in error_msg.lower() or "maximum context length" in error_msg.lower():
            # Try with simplified messages - just pass a summary
            simplified_messages = [
                {"role": "system", "content": get_conversational_agent_prompt(memories=relevant_memories, travel_plan_items=travel_plan_items)},
                {
                    "role": "user",
                    "content": f"""User's original message: {user_message}

The system has collected information from specialized agents. Please provide a helpful, natural response based on the available information."""
                }
            ]
            
            try:
                session_id = state.get("session_id", "unknown")
                user_email = state.get("user_email")
                llm_start_time = time.time()
                
                # Call OpenAI API (direct call - simplified messages)
                response = client.chat.completions.create(
                    model="gpt-4.1",
                    messages=simplified_messages,
                    temperature=0.7
                )
                
                llm_latency_ms = (time.time() - llm_start_time) * 1000
                
                # Log LLM call
                prompt_preview = str(simplified_messages[-1].get("content", "")) if simplified_messages else ""
                response_preview = response.choices[0].message.content if response.choices[0].message.content else ""
                token_usage = {
                    "prompt_tokens": response.usage.prompt_tokens if hasattr(response, 'usage') and response.usage else None,
                    "completion_tokens": response.usage.completion_tokens if hasattr(response, 'usage') and response.usage else None,
                    "total_tokens": response.usage.total_tokens if hasattr(response, 'usage') and response.usage else None
                } if hasattr(response, 'usage') and response.usage else None
                
                log_llm_call(
                    session_id=session_id,
                    user_email=user_email,
                    agent_name="conversational_agent",
                    model="gpt-4.1",
                    prompt_preview=prompt_preview,
                    response_preview=response_preview,
                    token_usage=token_usage,
                    latency_ms=llm_latency_ms
                )
                
                message = response.choices[0].message
                raw_response = message.content or "I apologize, but I couldn't generate a response. Please try again."
                final_response = clean_response(raw_response)
                
                # Replace flight IDs with actual booking URLs in the response (simplified path)
                if flight_url_mapping:
                        import re
                        # Step 1: Remove raw URLs (not in markdown)
                        url_pattern = r'(?<!\]\()https?://[^\s\)]+(?!\))'
                        final_response = re.sub(url_pattern, '', final_response)
                        
                        # Step 2: Remove duplicate booking buttons
                        duplicate_pattern = r'(\[Book Now\]\([^\)]+\)\s*\|\s*\[View on Google Flights\]\([^\)]+\)\s*){2,}'
                        final_response = re.sub(duplicate_pattern, r'\1', final_response)
                        
                        # Step 3: Replace each flight ID ONCE
                        replaced_count = 0
                        for flight_id, urls in flight_url_mapping.items():
                            # Skip if no URLs available
                            if not urls.get("booking_link") and not urls.get("google_flights_url"):
                                continue
                            
                            booking_links = []
                            if urls.get("booking_link"):
                                booking_links.append(f'[Book Now]({urls["booking_link"]})')
                            if urls.get("google_flights_url"):
                                booking_links.append(f'[View on Google Flights]({urls["google_flights_url"]})')
                            
                            if not booking_links:
                                continue
                            
                            if flight_id not in final_response:
                                continue
                            
                            links_text = f'{" | ".join(booking_links)}'
                            
                            # Check if already has links very close (within 50 chars)
                            id_pos = final_response.find(flight_id)
                            if id_pos != -1:
                                after_context = final_response[id_pos + len(flight_id):id_pos + len(flight_id) + 50]
                                if '[Book Now]' in after_context:
                                    continue  # Already has links
                            
                            # Try patterns in order
                            patterns = [
                                rf'Book:\s*{re.escape(flight_id)}(?=\s|$|\.|,|\n)',
                                rf'book:\s*{re.escape(flight_id)}(?=\s|$|\.|,|\n)',
                                rf'Use flight_id\s+{re.escape(flight_id)}(?=\s|$|\.|,|\n)',
                                rf'Use\s+{re.escape(flight_id)}(?=\s|$|\.|,|\n)',
                                rf'{re.escape(flight_id)}\s+for booking',
                                rf'\b{re.escape(flight_id)}\b(?=\s|$|\.|,|\n)'
                            ]
                            
                            replaced = False
                            for pattern in patterns:
                                if re.search(pattern, final_response, re.IGNORECASE):
                                    final_response = re.sub(pattern, links_text, final_response, count=1, flags=re.IGNORECASE)
                                    replaced = True
                                    replaced_count += 1
                                    break
                            
                            # Fallback: insert after flight ID
                            if not replaced:
                                id_pos = final_response.find(flight_id)
                                if id_pos != -1:
                                    final_response = final_response[:id_pos + len(flight_id)] + f' {links_text}' + final_response[id_pos + len(flight_id):]
                                    replaced_count += 1
                
                # Check if booking intent is present and add booking URL (for simplified path too)
                hotel_result = collected_info.get("hotel_result")
                if hotel_result and isinstance(hotel_result, dict) and hotel_result.get("_booking_intent"):
                    booking_hotel_id = hotel_result.get("_booking_hotel_id")
                    booking_rate_id = hotel_result.get("_booking_rate_id")
                    booking_hotel_name = hotel_result.get("_booking_hotel_name", "Selected Hotel")
                    booking_checkin = hotel_result.get("_booking_checkin")
                    booking_checkout = hotel_result.get("_booking_checkout")
                    booking_price = hotel_result.get("_booking_price", "")
                    
                    if booking_hotel_id and booking_rate_id:
                        from urllib.parse import quote
                        booking_url = f"/booking?hotel_id={quote(booking_hotel_id)}&rate_id={quote(booking_rate_id)}&hotel_name={quote(booking_hotel_name)}&checkin={quote(booking_checkin)}&checkout={quote(booking_checkout)}"
                        if booking_price and booking_price != "N/A":
                            booking_url += f"&price={quote(str(booking_price))}"
                        booking_message = f"\n\n🔒 **Secure Booking**\n\nI've prepared your booking for {booking_hotel_name}! For your security, please complete your reservation and payment details on our secure booking page:\n\n[Complete Your Booking →]({booking_url})\n\nThis secure page will allow you to enter your payment information safely."
                        final_response += booking_message
            except Exception as inner_e:
                print(f"Error in simplified message retry: {str(inner_e)}")
                final_response = "I have the information you requested, but there was a technical issue formatting the response. Please try rephrasing your query or ask for specific details."
        else:
            # Other errors
            final_response = f"I encountered an error while generating the response: {error_msg}. Please try again."
    
    # Prepend filtered message if any non-travel parts were filtered
    if rfi_filtered_message and final_response:
        # Only add if the filtered message isn't already in the response
        if rfi_filtered_message not in final_response:
            final_response = f"{rfi_filtered_message}\n\n{final_response}"
    
    # Add structured data markers for frontend rendering
    # TripAdvisor results are handled by the LLM like any other data (flights, hotels, etc.)
    # No special handling needed - the LLM will describe them naturally in the response
    if collected_info.get("flight_result"):
        flight_result = collected_info["flight_result"]
        if isinstance(flight_result, dict) and not flight_result.get("error"):
            # CRITICAL: Check if user's query is about hotels/restaurants - if so, exclude flight results
            # This prevents showing flights when user is asking about hotels or restaurants
            user_msg_lower = user_message.lower()
            hotel_keywords = ["hotel", "hotels", "accommodation", "accommodations", "stay", "staying", "lodging", "room", "rooms", "reservation", "book hotel", "add hotel"]
            restaurant_keywords = ["restaurant", "restaurants", "dining", "dine", "eat", "food", "cuisine", "meal", "add restaurant", "add restaurants"]
            flight_keywords = ["flight", "flights", "fly", "flying", "airline", "airlines", "ticket", "tickets", "departure", "arrival", "airport"]
            
            # Check if query is primarily about hotels/restaurants (not flights)
            hotel_intent = any(keyword in user_msg_lower for keyword in hotel_keywords)
            restaurant_intent = any(keyword in user_msg_lower for keyword in restaurant_keywords)
            flight_intent = any(keyword in user_msg_lower for keyword in flight_keywords)
            
            # CRITICAL: If user is choosing/selecting an option (planner operation), don't re-show all results
            # This prevents showing all flights again when user just wants to confirm their selection
            if is_choosing_option or needs_planner:
                print(f"[CONVERSATIONAL] User is choosing/selecting an option (planner operation), excluding flight results from response to avoid re-showing all options")
            # If user is asking about hotels/restaurants and NOT about flights, skip flight results
            elif (hotel_intent or restaurant_intent) and not flight_intent:
                print(f"[CONVERSATIONAL] User query is about hotels/restaurants, excluding flight results from response")
            else:
                import json
                # Flight agent now makes 2 separate calls for round-trip, so we just use what we have
                outbound_flights = flight_result.get("outbound", [])
                return_flights = flight_result.get("return", [])
                
                print(f"[CONVERSATIONAL] Flight results: {len(outbound_flights)} outbound, {len(return_flights)} return")
                
                # Intelligently filter flights based on user's message intent
                filtered_outbound, filtered_return = _filter_flights_intelligently(
                    user_message, outbound_flights, return_flights, state
                )
                
                # Combine both outbound and return flights for display
                all_flights = []
                
                # Get Google Flights URL from first flight (if available) to use as fallback
                google_flights_fallback = None
                if filtered_outbound and len(filtered_outbound) > 0:
                    google_flights_fallback = filtered_outbound[0].get("google_flights_url")
                elif filtered_return and len(filtered_return) > 0:
                    google_flights_fallback = filtered_return[0].get("google_flights_url")
                
                if filtered_outbound:
                    # Ensure outbound flights are marked and have Google Flights URL
                    for flight in filtered_outbound:
                        if not flight.get("direction"):
                            flight["direction"] = "outbound"
                        if not flight.get("type"):
                            flight["type"] = "Outbound flight"
                        # Ensure Google Flights URL is present
                        if not flight.get("google_flights_url") and google_flights_fallback:
                            flight["google_flights_url"] = google_flights_fallback
                    all_flights.extend(filtered_outbound)
                if filtered_return:
                    # Ensure return flights are marked and have Google Flights URL
                    for flight in filtered_return:
                        if not flight.get("direction"):
                            flight["direction"] = "return"
                        if not flight.get("type"):
                            flight["type"] = "Return flight"
                        # Ensure Google Flights URL is present
                        if not flight.get("google_flights_url") and google_flights_fallback:
                            flight["google_flights_url"] = google_flights_fallback
                    all_flights.extend(filtered_return)
                
                # Flight data is stored in state and can be accessed by conversational agent when needed
                # No need to append flight cards to response - flight info is in state.flight_result
    
    # Store last results in STM for future reference (e.g., when user says "i want option 3")
    session_id = state.get("session_id")
    if session_id and collected_info:
        try:
            from stm.short_term_memory import store_last_results, get_last_results
            # Store only non-empty results
            results_to_store = {}
            
            # CRITICAL: Preserve full flight list when storing selected flights
            # If collected_info has a flight_result with only 1 flight, it's likely a selected flight
            # In that case, preserve the original full list from STM instead of overwriting it
            if collected_info.get("flight_result"):
                flight_result = collected_info["flight_result"]
                outbound_count = len(flight_result.get("outbound", [])) if isinstance(flight_result, dict) else 0
                return_count = len(flight_result.get("return", [])) if isinstance(flight_result, dict) else 0
                total_flights = outbound_count + return_count
                
                # If only 1 flight, it's likely a selected flight - preserve original full list
                if total_flights == 1:
                    existing_results = get_last_results(session_id)
                    existing_flight_result = existing_results.get("flight_result")
                    if existing_flight_result:
                        existing_outbound = existing_flight_result.get("outbound", [])
                        existing_return = existing_flight_result.get("return", [])
                        existing_total = len(existing_outbound) + len(existing_return)
                        # If existing list has more flights, preserve it
                        if existing_total > 1:
                            print(f"[CONVERSATIONAL] Preserving full flight list ({existing_total} flights) instead of overwriting with selected flight (1 flight)")
                            results_to_store["flight_result"] = existing_flight_result
                        else:
                            # Both have 1 flight, use the new one
                            results_to_store["flight_result"] = flight_result
                    else:
                        # No existing results, store what we have
                        results_to_store["flight_result"] = flight_result
                else:
                    # Multiple flights - this is a full search result, store it
                    results_to_store["flight_result"] = flight_result
            
            if collected_info.get("hotel_result"):
                results_to_store["hotel_result"] = collected_info["hotel_result"]
            if collected_info.get("tripadvisor_result"):
                results_to_store["tripadvisor_result"] = collected_info["tripadvisor_result"]
            if collected_info.get("visa_result"):
                results_to_store["visa_result"] = collected_info["visa_result"]
            if collected_info.get("utilities_result"):
                results_to_store["utilities_result"] = collected_info["utilities_result"]
            
            if results_to_store:
                store_last_results(session_id, results_to_store)
                print(f"[CONVERSATIONAL] Stored {len(results_to_store)} result types in STM for future reference")
        except Exception as e:
            print(f"[WARNING] Could not store last results in STM: {e}")
    
    updated_state = state.copy()
    updated_state["last_response"] = final_response
    updated_state["route"] = "end"  # End the workflow
    
    return updated_state








