"""Conversational Agent node for LangGraph orchestration - generates final user response."""

import sys
import os
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import AgentState

# Load environment variables from .env file in main directory
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Maximum items to show per result type to avoid context length issues
MAX_FLIGHTS_TO_SHOW = 3
MAX_HOTELS_TO_SHOW = 5
MAX_TRIPADVISOR_ITEMS_TO_SHOW = 5
MAX_VISA_INFO_LENGTH = 2000  # characters


def _truncate_collected_info(collected_info: dict) -> dict:
    """Truncate collected_info to prevent context length errors.
    
    Args:
        collected_info: Full collected information dictionary
        
    Returns:
        Truncated version with only essential data
    """
    truncated = {}
    
    # Truncate flight results
    if "flight_result" in collected_info:
        flight_result = collected_info["flight_result"].copy()
        if not flight_result.get("error"):
            # Limit outbound flights - but keep ALL details for top flights
            if "outbound" in flight_result and isinstance(flight_result["outbound"], list):
                outbound = flight_result["outbound"]
                if len(outbound) > MAX_FLIGHTS_TO_SHOW:
                    # Keep COMPLETE information for top flights (all legs, all details)
                    flight_result["outbound"] = outbound[:MAX_FLIGHTS_TO_SHOW]
                    flight_result["_outbound_total"] = len(outbound)
            
            # Limit return flights - but keep ALL details for top flights
            if "return" in flight_result and isinstance(flight_result["return"], list):
                return_flights = flight_result["return"]
                if len(return_flights) > MAX_FLIGHTS_TO_SHOW:
                    # Keep COMPLETE information for top flights (all legs, all details)
                    flight_result["return"] = return_flights[:MAX_FLIGHTS_TO_SHOW]
                    flight_result["_return_total"] = len(return_flights)
            
            # Limit flexible flights
            if "flights" in flight_result and isinstance(flight_result["flights"], list):
                flights = flight_result["flights"]
                if len(flights) > MAX_FLIGHTS_TO_SHOW:
                    flight_result["flights"] = flights[:MAX_FLIGHTS_TO_SHOW]
                    flight_result["_flights_total"] = len(flights)
        
        truncated["flight_result"] = flight_result
    
    # Truncate hotel results
    if "hotel_result" in collected_info:
        hotel_result = collected_info["hotel_result"].copy()
        if not hotel_result.get("error") and "hotels" in hotel_result:
            hotels = hotel_result.get("hotels", [])
            if isinstance(hotels, list) and len(hotels) > MAX_HOTELS_TO_SHOW:
                # Keep only essential fields
                truncated_hotels = []
                for hotel in hotels[:MAX_HOTELS_TO_SHOW]:
                    truncated_hotel = {
                        "name": hotel.get("name"),
                        "price": hotel.get("price"),
                        "rating": hotel.get("rating"),
                        "address": hotel.get("address")
                    }
                    truncated_hotels.append(truncated_hotel)
                hotel_result["hotels"] = truncated_hotels
                hotel_result["_hotels_total"] = len(hotels)
        truncated["hotel_result"] = hotel_result
    
    # Truncate tripadvisor results
    if "tripadvisor_result" in collected_info:
        tripadvisor_result = collected_info["tripadvisor_result"].copy()
        if not tripadvisor_result.get("error"):
            # Limit locations
            if "locations" in tripadvisor_result and isinstance(tripadvisor_result["locations"], list):
                locations = tripadvisor_result["locations"]
                if len(locations) > MAX_TRIPADVISOR_ITEMS_TO_SHOW:
                    tripadvisor_result["locations"] = locations[:MAX_TRIPADVISOR_ITEMS_TO_SHOW]
                    tripadvisor_result["_locations_total"] = len(locations)
            
            # Limit reviews
            if "reviews" in tripadvisor_result and isinstance(tripadvisor_result["reviews"], list):
                reviews = tripadvisor_result["reviews"]
                if len(reviews) > MAX_TRIPADVISOR_ITEMS_TO_SHOW:
                    tripadvisor_result["reviews"] = reviews[:MAX_TRIPADVISOR_ITEMS_TO_SHOW]
                    tripadvisor_result["_reviews_total"] = len(reviews)
        truncated["tripadvisor_result"] = tripadvisor_result
    
    # Truncate visa results (limit text length)
    if "visa_result" in collected_info:
        visa_result = collected_info["visa_result"].copy()
        if not visa_result.get("error") and "result" in visa_result:
            visa_info = visa_result.get("result", "")
            if isinstance(visa_info, str) and len(visa_info) > MAX_VISA_INFO_LENGTH:
                visa_result["result"] = visa_info[:MAX_VISA_INFO_LENGTH] + "\n\n[... truncated for length ...]"
        truncated["visa_result"] = visa_result
    
    # Copy other results as-is
    for key, value in collected_info.items():
        if key not in ["flight_result", "hotel_result", "tripadvisor_result", "visa_result"]:
            truncated[key] = value
    
    return truncated


def get_conversational_agent_prompt() -> str:
    """Get the system prompt for the Conversational Agent."""
    return """You are a helpful travel assistant that provides friendly, clear responses to users about their travel queries.

Your role:
- Take the user's original message and all the information gathered from specialized agents
- Synthesize this information into a natural, conversational response
- Present the information in a clear, organized, and professional manner
- Be friendly, professional, and concise
- CRITICAL: You MUST use the actual data provided in the "collected_info" section below. If visa_result, flight_result, hotel_result, or tripadvisor_result are present, they contain the actual information you need to share with the user.

FORMATTING GUIDELINES:
- Use clear section titles in ALL CAPS between **bold** markers (e.g., **FLIGHT SEARCH RESULTS**, **OUTBOUND FLIGHTS**)
- For flights: Use numbered lists with aligned line breaks (each detail on its own line)
- Use minimal but friendly emojis: ✈️, 🌍, 💲, 🕓, ⏱
- Separate OUTBOUND and RETURN sections clearly
- Emphasize airline names and prices in **bold**
- Include a friendly closing line at the end (e.g., "Safe travels! ✈️")
- Format: Number | Airline (bold) | Price (bold) | Departure → Arrival | Duration | Stops
- Use consistent date formatting: "December 12, 2025" (not "2025-12-12")

You have access to:
- The user's original message
- Information collected from flight, hotel, visa, and TripAdvisor agents (if any were called)

IMPORTANT: When visa_result is provided, it contains the actual visa requirements information. You MUST include this information in your response. Do NOT say you don't have the information if it's provided in the collected_info section.

Create a comprehensive, well-structured response that addresses the user's query using all available information. Make it visually clean and easy to read."""


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
    
    # Build a summary of collected information
    info_summary = []
    if collected_info.get("flight_result"):
        info_summary.append("Flight information has been gathered.")
    if collected_info.get("hotel_result"):
        info_summary.append("Hotel information has been gathered.")
    if collected_info.get("visa_result"):
        info_summary.append("Visa requirement information has been gathered.")
    if collected_info.get("tripadvisor_result"):
        info_summary.append("TripAdvisor location/review information has been gathered.")
    
    # Also check context for results
    if context.get("flight_result"):
        collected_info["flight_result"] = context.get("flight_result")
        info_summary.append("Flight information has been gathered.")
    if context.get("hotel_result"):
        collected_info["hotel_result"] = context.get("hotel_result")
        info_summary.append("Hotel information has been gathered.")
    if context.get("visa_result"):
        collected_info["visa_result"] = context.get("visa_result")
        info_summary.append("Visa requirement information has been gathered.")
    if context.get("tripadvisor_result"):
        collected_info["tripadvisor_result"] = context.get("tripadvisor_result")
        info_summary.append("TripAdvisor location/review information has been gathered.")
    
    # Prepare messages for LLM
    messages = [
        {"role": "system", "content": get_conversational_agent_prompt()},
        {
            "role": "user", 
            "content": f"""User's original message: {user_message}

Collected information from agents:
{chr(10).join(info_summary) if info_summary else "No specialized agent information was collected."}

CRITICAL INSTRUCTIONS:
- You MUST use the actual data provided in the "Detailed collected information" section below
- If visa_result is present, it contains the visa requirements - you MUST include this information in your response
- If flight_result, hotel_result, or tripadvisor_result are present, include that information as well
- Do NOT say you don't have information if it's provided below
- Present the information in a clear, organized, and helpful way

FORMATTING REQUIREMENTS:
- For visa results: PRESERVE all markdown bold markers (**text**) exactly as provided - do NOT remove them
- For flight results: Do NOT use bold text (** or __) - keep everything in plain text
- Use exact format: ✈️ FLIGHT SEARCH RESULTS as header (no bold)
- Use emojis: 🌍 for route, 📅 for dates, 💺 for class/passengers, 🛫 for outbound, 🛬 for return
- Use number emojis: 1️⃣, 2️⃣, 3️⃣ for flight numbering
- Section headers: 🛫 OUTBOUND FLIGHTS and 🛬 RETURN FLIGHTS (no ###, no bold)
- Format each flight: Number emoji | Airline | 💲 Price (all on one line)
- Then indented details: 🕓 Departure: CODE TIME → CODE TIME (full date), ⏱ Duration: Xh Xm, 🚫 Stops: Direct flight or X stops
- Use separator lines (---) between major sections
- Include closing: "💡 Note: Prices are per adult, in economy class." and "🌟 Safe travels and enjoy your trip!" (no bold)
- Keep one blank line between flight entries
- Use full date format in departure line: (Dec 24, 2025) not just (Dec 24)"""
        }
    ]
    
    # Add collected info details if available
    if collected_info:
        import json
        # Extract and format results more prominently if present
        visa_result = collected_info.get("visa_result")
        flight_result = collected_info.get("flight_result")
        hotel_result = collected_info.get("hotel_result")
        
        content_parts = []
        
        # Format flight results prominently
        if flight_result and not flight_result.get("error"):
            outbound = flight_result.get("outbound", [])
            return_flights = flight_result.get("return", [])
            trip_type = flight_result.get("trip_type", "one-way")
            departure = flight_result.get("departure", "")
            arrival = flight_result.get("arrival", "")
            departure_date = flight_result.get("departure_date", "")
            arrival_date = flight_result.get("arrival_date", "")
            currency = flight_result.get("currency", "USD")
            
            # Format dates nicely
            def format_date(date_str):
                """Convert YYYY-MM-DD to 'December 12, 2025' format."""
                try:
                    from datetime import datetime
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    return dt.strftime("%B %d, %Y")
                except:
                    return date_str
            
            def format_date_short(date_str):
                """Convert YYYY-MM-DD to short format like 'Dec 24'."""
                try:
                    from datetime import datetime
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    return dt.strftime("%b %d")
                except:
                    return date_str
            
            def format_date_short_with_year(date_str):
                """Convert YYYY-MM-DD to short format like 'Dec 24, 2025'."""
                try:
                    from datetime import datetime
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    return dt.strftime("%b %d, %Y")
                except:
                    return date_str
            
            formatted_dep_date = format_date(departure_date) if departure_date else ""
            formatted_arr_date = format_date(arrival_date) if arrival_date else ""
            
            # Get passenger info
            passengers = flight_result.get("passengers", {})
            adults = passengers.get("adults", 1)
            children = passengers.get("children", 0)
            infants = passengers.get("infants", 0)
            passenger_text = f"{adults} Adult{'s' if adults > 1 else ''}"
            if children > 0:
                passenger_text += f", {children} Child{'ren' if children > 1 else ''}"
            if infants > 0:
                passenger_text += f", {infants} Infant{'s' if infants > 1 else ''}"
            
            # Get travel class
            travel_class = flight_result.get("travel_class", "economy")
            # Capitalize first letter for display
            travel_class_display = travel_class.capitalize() if travel_class else "Economy"
            
            # Get airport names for route display
            def get_airport_name(code):
                """Get airport name from code (simplified - could be enhanced with a lookup)."""
                airport_names = {
                    "BEY": "Beirut, Lebanon",
                    "DOH": "Doha, Qatar",
                    "DXB": "Dubai",
                    "JFK": "New York",
                    "LAX": "Los Angeles",
                    "LHR": "London",
                    "CDG": "Paris",
                    "NYC": "New York"
                }
                return airport_names.get(code, code)
            
            dep_name = get_airport_name(departure)
            arr_name = get_airport_name(arrival)
            
            content_parts.append("✈️ FLIGHT SEARCH RESULTS")
            content_parts.append("")
            content_parts.append(f"🌍 Route: {dep_name} ({departure}) → {arr_name} ({arrival})")
            if arrival_date:
                content_parts.append(f"📅 Dates: {formatted_dep_date} – {formatted_arr_date}")
            else:
                content_parts.append(f"📅 Dates: {formatted_dep_date}")
            content_parts.append(f"💺 Class/Passengers: Economy / {passenger_text}")
            content_parts.append("")
            content_parts.append("---")
            content_parts.append("")
            
            if outbound:
                total_outbound = flight_result.get("_outbound_total", len(outbound))
                content_parts.append("🛫 OUTBOUND FLIGHTS ({departure} → {arrival})".format(departure=departure, arrival=arrival))
                content_parts.append("")
                
                # Number emoji mapping
                number_emojis = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣"}
                
                for i, flight in enumerate(outbound[:MAX_FLIGHTS_TO_SHOW], 1):  # Show top flights
                    price = flight.get("price", "N/A")
                    flights_legs = flight.get("flights", [])
                    
                    # Get departure and arrival info
                    dep_code = "N/A"
                    dep_time = "N/A"
                    dep_date_display = ""
                    arr_code = "N/A"
                    arr_time = "N/A"
                    arr_date_display = ""
                    airline = "N/A"
                    duration = "N/A"
                    stops = "0"
                    stop_details = ""
                    
                    if flights_legs:
                        first_leg = flights_legs[0]
                        last_leg = flights_legs[-1]
                        
                        # Departure info
                        dep_airport = first_leg.get("departure_airport", {})
                        dep_code = dep_airport.get("id", "N/A")
                        dep_time_raw = dep_airport.get("time", "N/A")
                        dep_date_from_time = None
                        if "T" in str(dep_time_raw):
                            dep_time = str(dep_time_raw).split("T")[-1][:5]
                            dep_date_from_time = str(dep_time_raw).split("T")[0]
                            dep_date_display = format_date(dep_date_from_time) if dep_date_from_time else formatted_dep_date
                        else:
                            dep_time = str(dep_time_raw)[:5] if dep_time_raw else "N/A"
                            dep_date_display = formatted_dep_date
                        
                        # Arrival info
                        arr_airport = last_leg.get("arrival_airport", {})
                        arr_code = arr_airport.get("id", "N/A")
                        arr_time_raw = arr_airport.get("time", "N/A")
                        arr_date_from_time = None
                        if "T" in str(arr_time_raw):
                            arr_time = str(arr_time_raw).split("T")[-1][:5]
                            arr_date_from_time = str(arr_time_raw).split("T")[0]
                            arr_date_display = format_date(arr_date_from_time) if arr_date_from_time else formatted_dep_date
                        else:
                            arr_time = str(arr_time_raw)[:5] if arr_time_raw else "N/A"
                            arr_date_display = formatted_dep_date
                        
                        # Format date note (e.g., "Dec 24, 2025" or "Dec 24, 2025 → Dec 25, 2025")
                        date_note = ""
                        try:
                            # Use short date format with year for departure
                            if dep_date_from_time:
                                dep_date_short = format_date_short_with_year(dep_date_from_time)
                            else:
                                dep_date_short = format_date_short_with_year(departure_date)
                            
                            if arr_date_from_time:
                                arr_date_short = format_date_short_with_year(arr_date_from_time)
                            else:
                                arr_date_short = format_date_short_with_year(departure_date)
                            
                            # Compare dates using short format without year
                            dep_date_compare = format_date_short(dep_date_from_time if dep_date_from_time else departure_date)
                            arr_date_compare = format_date_short(arr_date_from_time if arr_date_from_time else departure_date)
                            
                            if dep_date_compare != arr_date_compare:
                                # Show both dates if different
                                date_note = f" ({dep_date_short} → {arr_date_short})"
                            else:
                                # Show just one date if same day
                                date_note = f" ({dep_date_short})"
                        except Exception as e:
                            # Fallback: use departure date
                            try:
                                date_note = f" ({format_date_short_with_year(departure_date)})"
                            except:
                                date_note = ""
                        
                        # Airline (show all if multiple)
                        airlines = [leg.get("airline", "") for leg in flights_legs if leg.get("airline")]
                        airline = ", ".join(set(airlines)) if airlines else "N/A"
                        
                        # Duration
                        total_duration = sum(leg.get("duration", 0) for leg in flights_legs)
                        if total_duration:
                            hours = total_duration // 60
                            minutes = total_duration % 60
                            duration = f"{hours}h {minutes}m"
                        
                        # Number of stops and stop details
                        num_stops = len(flights_legs) - 1
                        stops = str(num_stops)
                        if num_stops > 0:
                            # Get stopover airport names (shortened)
                            stop_airports = []
                            for leg in flights_legs[:-1]:
                                stop_airport = leg.get("arrival_airport", {})
                                stop_name = stop_airport.get("name", stop_airport.get("id", "Unknown"))
                                # Shorten airport names
                                if "International" in stop_name:
                                    stop_name = stop_name.replace("International", "Intl.")
                                stop_airports.append(stop_name)
                            stop_details = f" via {', '.join(stop_airports)}"
                    
                    # Format nicely in the requested style (plain text, no bold)
                    is_direct = stops == "0"
                    stop_text = "Direct flight" if is_direct else f"{stops} stop{stop_details}"
                    
                    num_emoji = number_emojis.get(i, f"{i}.")
                    # Format: 1️⃣ | Airline | 💲 Price (all on one line)
                    content_parts.append(f"{num_emoji} | {airline} | 💲 {price} {currency}")
                    content_parts.append("")
                    # Indented details
                    content_parts.append(f"   🕓 Departure: {dep_code} {dep_time} → {arr_code} {arr_time}{date_note}")
                    content_parts.append(f"   ⏱ Duration: {duration}")
                    content_parts.append(f"   🚫 Stops: {stop_text}")
                    content_parts.append("")
                
                if total_outbound > MAX_FLIGHTS_TO_SHOW:
                    content_parts.append("")
                    content_parts.append("")
                content_parts.append("---")
                content_parts.append("")
            
            if return_flights:
                total_return = flight_result.get("_return_total", len(return_flights))
                content_parts.append("🛬 RETURN FLIGHTS ({arrival} → {departure})".format(arrival=arrival, departure=departure))
                content_parts.append("")
                
                # Number emoji mapping
                number_emojis = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣"}
                
                for i, flight in enumerate(return_flights[:MAX_FLIGHTS_TO_SHOW], 1):  # Show top flights
                    price = flight.get("price", "N/A")
                    flights_legs = flight.get("flights", [])
                    
                    # Get departure and arrival info
                    dep_code = "N/A"
                    dep_time = "N/A"
                    dep_date_display = ""
                    arr_code = "N/A"
                    arr_time = "N/A"
                    arr_date_display = ""
                    airline = "N/A"
                    duration = "N/A"
                    stops = "0"
                    stop_details = ""
                    
                    if flights_legs:
                        first_leg = flights_legs[0]
                        last_leg = flights_legs[-1]
                        
                        # Departure info
                        dep_airport = first_leg.get("departure_airport", {})
                        dep_code = dep_airport.get("id", "N/A")
                        dep_time_raw = dep_airport.get("time", "N/A")
                        dep_date_from_time = None
                        if "T" in str(dep_time_raw):
                            dep_time = str(dep_time_raw).split("T")[-1][:5]
                            dep_date_from_time = str(dep_time_raw).split("T")[0]
                            dep_date_display = format_date(dep_date_from_time) if dep_date_from_time else formatted_arr_date
                        else:
                            dep_time = str(dep_time_raw)[:5] if dep_time_raw else "N/A"
                            dep_date_display = formatted_arr_date
                        
                        # Arrival info
                        arr_airport = last_leg.get("arrival_airport", {})
                        arr_code = arr_airport.get("id", "N/A")
                        arr_time_raw = arr_airport.get("time", "N/A")
                        arr_date_from_time = None
                        if "T" in str(arr_time_raw):
                            arr_time = str(arr_time_raw).split("T")[-1][:5]
                            arr_date_from_time = str(arr_time_raw).split("T")[0]
                            arr_date_display = format_date(arr_date_from_time) if arr_date_from_time else formatted_arr_date
                        else:
                            arr_time = str(arr_time_raw)[:5] if arr_time_raw else "N/A"
                            arr_date_display = formatted_arr_date
                        
                        # Format date note (e.g., "Dec 24, 2025" or "Dec 24, 2025 → Dec 25, 2025")
                        date_note = ""
                        try:
                            # Use short date format with year for departure
                            if dep_date_from_time:
                                dep_date_short = format_date_short_with_year(dep_date_from_time)
                            else:
                                dep_date_short = format_date_short_with_year(arrival_date)
                            
                            if arr_date_from_time:
                                arr_date_short = format_date_short_with_year(arr_date_from_time)
                            else:
                                arr_date_short = format_date_short_with_year(arrival_date)
                            
                            # Compare dates using short format without year
                            dep_date_compare = format_date_short(dep_date_from_time if dep_date_from_time else arrival_date)
                            arr_date_compare = format_date_short(arr_date_from_time if arr_date_from_time else arrival_date)
                            
                            if dep_date_compare != arr_date_compare:
                                # Show both dates if different
                                date_note = f" ({dep_date_short} → {arr_date_short})"
                            else:
                                # Show just one date if same day
                                date_note = f" ({dep_date_short})"
                        except Exception as e:
                            # Fallback: use arrival date
                            try:
                                date_note = f" ({format_date_short_with_year(arrival_date)})"
                            except:
                                date_note = ""
                        
                        # Airline (show all if multiple)
                        airlines = [leg.get("airline", "") for leg in flights_legs if leg.get("airline")]
                        airline = ", ".join(set(airlines)) if airlines else "N/A"
                        
                        # Duration
                        total_duration = sum(leg.get("duration", 0) for leg in flights_legs)
                        if total_duration:
                            hours = total_duration // 60
                            minutes = total_duration % 60
                            duration = f"{hours}h {minutes}m"
                        
                        # Number of stops and stop details
                        num_stops = len(flights_legs) - 1
                        stops = str(num_stops)
                        if num_stops > 0:
                            # Get stopover airport names (shortened)
                            stop_airports = []
                            for leg in flights_legs[:-1]:
                                stop_airport = leg.get("arrival_airport", {})
                                stop_name = stop_airport.get("name", stop_airport.get("id", "Unknown"))
                                # Shorten airport names
                                if "International" in stop_name:
                                    stop_name = stop_name.replace("International", "Intl.")
                                stop_airports.append(stop_name)
                            stop_details = f" via {', '.join(stop_airports)}"
                    
                    # Format nicely in the requested style (plain text, no bold)
                    is_direct = stops == "0"
                    stop_text = "Direct flight" if is_direct else f"{stops} stop{stop_details}"
                    
                    num_emoji = number_emojis.get(i, f"{i}.")
                    # Format: 1️⃣ | Airline | 💲 Price (all on one line)
                    content_parts.append(f"{num_emoji} | {airline} | 💲 {price} {currency}")
                    content_parts.append("")
                    # Indented details
                    content_parts.append(f"   🕓 Departure: {dep_code} {dep_time} → {arr_code} {arr_time}{date_note}")
                    content_parts.append(f"   ⏱ Duration: {duration}")
                    content_parts.append(f"   🚫 Stops: {stop_text}")
                    content_parts.append("")
                
                if total_return > MAX_FLIGHTS_TO_SHOW:
                    content_parts.append("")
                    content_parts.append("")
                content_parts.append("---")
                content_parts.append("")
            
            if not outbound and not return_flights:
                content_parts.append("No flights found for the specified criteria.")
                content_parts.append("")
            else:
                # Add closing note for flight results (plain text, no bold, dynamic based on actual values)
                # Build passenger note
                total_passengers = adults + children + infants
                if total_passengers == 1 and adults == 1:
                    passenger_note = "per adult"
                elif total_passengers == 1:
                    passenger_note = "per passenger"
                else:
                    passenger_note = f"for {total_passengers} passenger{'s' if total_passengers > 1 else ''}"
                
                # Build class note
                class_note = f"in {travel_class_display} class"
                
                # Combine into note
                note_text = f"💡 Note: Prices are {passenger_note}, {class_note}."
                content_parts.append(note_text)
                content_parts.append("")
                content_parts.append("🌟 Safe travels and enjoy your trip!")
                content_parts.append("")
        
        # Format flexible flight results
        if flight_result and not flight_result.get("error") and "flights" in flight_result:
            flights = flight_result.get("flights", [])
            if flights:
                content_parts.append("FLEXIBLE FLIGHT SEARCH RESULTS (from flight_result):")
                content_parts.append(f"Total flights found across dates: {len(flights)}")
                for i, flight in enumerate(flights[:MAX_FLIGHTS_TO_SHOW], 1):  # Show top flights
                    price = flight.get("price", "N/A")
                    search_date = flight.get("search_date", "N/A")
                    content_parts.append(f"  {i}. Date: {search_date} | Price: {price} {flight_result.get('currency', 'USD')}")
                if len(flights) > MAX_FLIGHTS_TO_SHOW:
                    content_parts.append(f"  ... and {len(flights) - MAX_FLIGHTS_TO_SHOW} more options")
                content_parts.append("")
        
        # Format visa results prominently
        if visa_result and not visa_result.get("error"):
            try:
                visa_info = visa_result.get("result", "")
                # Preserve markdown formatting (keep **bold** markers for markdown rendering)
                if isinstance(visa_info, str):
                    # Keep markdown bold markers intact - they will be rendered as bold in the UI
                    # Truncate if too long (already truncated in _truncate_collected_info, but be safe)
                    if len(visa_info) > MAX_VISA_INFO_LENGTH:
                        visa_info = visa_info[:MAX_VISA_INFO_LENGTH] + "\n\n[... truncated for length ...]"
                content_parts.append("VISA REQUIREMENTS (from visa_result):")
                content_parts.append(visa_info)
                content_parts.append("")
            except Exception as e:
                # If there's an error processing visa info, log it but don't fail
                content_parts.append(f"Visa requirements information is available but could not be formatted: {str(e)}")
                content_parts.append("")
        
        # Format hotel results prominently
        if hotel_result and not hotel_result.get("error"):
            try:
                hotels = hotel_result.get("hotels", [])
                total_hotels = len(hotels)
                filtered_count = hotel_result.get("_filtered", 0)
                
                if hotels:
                    content_parts.append("🏨 HOTEL SEARCH RESULTS")
                    content_parts.append("")
                    
                    # Show search params if available
                    search_params = hotel_result.get("search_params", {})
                    if search_params:
                        location = search_params.get("location", "Unknown")
                        checkin = search_params.get("checkin", "")
                        checkout = search_params.get("checkout", "")
                        if checkin and checkout:
                            content_parts.append(f"📍 Location: {location}")
                            content_parts.append(f"📅 Check-in: {checkin} | Check-out: {checkout}")
                            content_parts.append("")
                    
                    if filtered_count > 0:
                        content_parts.append(f"Found {total_hotels} hotel(s) matching your criteria (filtered from {total_hotels + filtered_count} total results).")
                    else:
                        content_parts.append(f"Found {total_hotels} hotel(s):")
                    content_parts.append("")
                    content_parts.append("---")
                    content_parts.append("")
                    
                    def extract_hotel_info(hotel):
                        """Extract hotel information from the enriched hotel structure."""
                        hotel_id = hotel.get("hotelId", "Unknown")
                        
                        # Extract price from roomTypes
                        price = "N/A"
                        currency = "USD"
                        min_price = float('inf')
                        
                        if "roomTypes" in hotel and isinstance(hotel["roomTypes"], list):
                            for room_type in hotel["roomTypes"]:
                                # Try offerRetailRate first
                                if "offerRetailRate" in room_type and "amount" in room_type["offerRetailRate"]:
                                    try:
                                        p = float(room_type["offerRetailRate"]["amount"])
                                        if p < min_price:
                                            min_price = p
                                            price = p
                                            currency = room_type["offerRetailRate"].get("currency", "USD")
                                    except (ValueError, TypeError):
                                        pass
                                
                                # Try rates array
                                if "rates" in room_type and isinstance(room_type["rates"], list):
                                    for rate in room_type["rates"]:
                                        if "retailRate" in rate and "total" in rate["retailRate"]:
                                            if isinstance(rate["retailRate"]["total"], list) and len(rate["retailRate"]["total"]) > 0:
                                                try:
                                                    p = float(rate["retailRate"]["total"][0].get("amount", 0))
                                                    if p > 0 and p < min_price:
                                                        min_price = p
                                                        price = p
                                                        currency = rate["retailRate"]["total"][0].get("currency", "USD")
                                                except (ValueError, TypeError):
                                                    pass
                        
                        # Format price
                        if price != "N/A" and price != float('inf'):
                            price_str = f"{price:.2f} {currency}"
                        else:
                            price_str = "Price not available"
                        
                        # Hotel name, rating, and address should now be in the enriched hotel data
                        name = hotel.get("name") or f"Hotel {hotel_id}"
                        rating = hotel.get("rating") or hotel.get("starRating") or hotel.get("stars")
                        address = hotel.get("address") or hotel.get("location")
                        
                        # Format rating
                        if rating:
                            try:
                                rating_float = float(rating)
                                rating_str = f"{rating_float:.1f} ⭐" if rating_float > 0 else "N/A"
                            except (ValueError, TypeError):
                                rating_str = str(rating) if rating else "N/A"
                        else:
                            rating_str = "N/A"
                        
                        return {
                            "id": hotel_id,
                            "name": name,
                            "price": price_str,
                            "rating": rating_str,
                            "address": address or "Address not available"
                        }
                    
                    # Show top hotels (already limited by MAX_HOTELS_TO_SHOW)
                    for i, hotel in enumerate(hotels[:MAX_HOTELS_TO_SHOW], 1):
                        hotel_info = extract_hotel_info(hotel)
                        content_parts.append(f"{i}. {hotel_info['name']}")
                        content_parts.append(f"   💲 Price: {hotel_info['price']}")
                        if hotel_info['rating'] != "N/A":
                            content_parts.append(f"   ⭐ Rating: {hotel_info['rating']}")
                        if hotel_info['address'] != "Address not available":
                            content_parts.append(f"   📍 Address: {hotel_info['address']}")
                        content_parts.append("")
                    
                    if total_hotels > MAX_HOTELS_TO_SHOW:
                        content_parts.append(f"... and {total_hotels - MAX_HOTELS_TO_SHOW} more hotel(s) available.")
                        content_parts.append("")
                    content_parts.append("---")
                    content_parts.append("")
                else:
                    content_parts.append("🏨 HOTEL SEARCH RESULTS")
                    content_parts.append("")
                    content_parts.append("No hotels found for the specified criteria.")
                    if filtered_count > 0:
                        content_parts.append(f"(Filtered out {filtered_count} hotel(s) that didn't match your criteria.)")
                    content_parts.append("")
            except Exception as e:
                # If there's an error processing hotel info, log it but don't fail
                import traceback
                error_trace = traceback.format_exc()
                print(f"Error formatting hotel results: {str(e)}")
                print(f"Traceback: {error_trace}")
                content_parts.append(f"Hotel information is available but could not be formatted: {str(e)}")
                content_parts.append("")
        
        # Truncate collected_info to prevent context length errors
        truncated_info = _truncate_collected_info(collected_info)
        
        # Add truncated collected info (more compact representation) - but only if not flight, hotel, or visa results
        # Flight, hotel, and visa results are already formatted above, so we don't need to duplicate
        if not flight_result and not hotel_result and not visa_result:
            content_parts.append("Full collected information (truncated for efficiency):")
            content_parts.append(json.dumps(truncated_info, indent=2, ensure_ascii=False))
        
        # Estimate content length and warn if still too large
        content_text = "\n".join(content_parts)
        # Rough token estimate: ~4 characters per token
        estimated_tokens = len(content_text) / 4
        
        if estimated_tokens > 6000:  # Leave room for system prompt and response
            # Further truncation: remove the full JSON dump, keep only summaries
            if "Full collected information" in content_text:
                content_parts = [p for p in content_parts if "Full collected information" not in p and not p.strip().startswith("{")]
                content_parts.append("Note: Full detailed data is available but truncated to fit context limits.")
            content_text = "\n".join(content_parts)
        
        messages.append({
            "role": "user",
            "content": content_text
        })
    
    # Call LLM to generate response
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7
        )
        
        message = response.choices[0].message
        final_response = message.content or "I apologize, but I couldn't generate a response. Please try again."
    
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        # Log the error for debugging
        print(f"Error in conversational_agent_node: {error_msg}")
        print(f"Traceback: {error_trace}")
        
        # Handle context length errors specifically
        if "context_length" in error_msg.lower() or "maximum context length" in error_msg.lower():
            # Try with even more aggressive truncation
            # Remove the full JSON dump entirely, keep only formatted summaries
            simplified_messages = [
                {"role": "system", "content": get_conversational_agent_prompt()},
                {
                    "role": "user",
                    "content": f"""User's original message: {user_message}

{chr(10).join(info_summary) if info_summary else "No specialized agent information was collected."}

The system has collected information from specialized agents. Please provide a helpful response based on the summary above. If you need specific details, ask the user or note that detailed information is available but was truncated for efficiency."""
                }
            ]
            
            try:
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=simplified_messages,
                    temperature=0.7
                )
                message = response.choices[0].message
                final_response = message.content or "I apologize, but I couldn't generate a response. Please try again."
            except Exception as e2:
                final_response = f"I have the information you requested, but there was a technical issue formatting the response. Please try rephrasing your query or ask for specific details."
        else:
            # Other errors
            final_response = f"I encountered an error while generating the response: {error_msg}. Please try again."
    
    updated_state = state.copy()
    updated_state["last_response"] = final_response
    updated_state["route"] = "end"  # End the workflow
    
    return updated_state

