"""
LangGraph agent with Anthropic Claude and tool access.
Proper ReAct agent implementation.
"""

import os
import sys
from dotenv import load_dotenv
from typing import Annotated, TypedDict, Literal
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# Load environment variables
load_dotenv()

# Import all our tools
from tools.serpapi_tools import (
    fetch_hotels, 
    get_hotel_details,
    search_hotels_near_landmark,
    search_hotels_by_chain,
    search_hotels_with_deals
)
from tools.hotel_tools import (
    filter_hotels_by_rating,
    filter_hotels_by_price,
    filter_hotels_by_class,
    sort_hotels_by_price,
    sort_hotels_by_rating,
    get_top_hotels,
    select_hotel_by_index,
    get_hotel_summary,
    format_hotels_list
)
from tools.enhanced_hotel_tools import (
    filter_hotels_by_amenities,
    filter_hotels_by_location_type,
    filter_hotels_by_room_features,
    sort_hotels_by_value,
    sort_hotels_by_popularity,
    sort_hotels_by_distance_from_landmark,
    compare_hotels_detailed,
    get_hotel_recommendations,
    analyze_hotel_trends
)
from tools.budget_tools import (
    calculate_total_budget,
    estimate_daily_expenses
)
from tools.explore_tools import (
    get_nearby_places,
    format_nearby_places
)
from tools.presentation_tools import (
    format_hotel_cards,
    format_hotel_comparison,
    format_hotel_highlights,
    format_budget_summary
)
from tools.booking_tools import (
    quick_book_hotel,
    format_booking_confirmation,
    save_booking_to_database,
    get_user_bookings,
    cancel_booking_in_database
)
from tools.flight_tools import (
    search_flights,
    search_flights_by_price,
    search_flights_by_airline,
    search_flights_by_duration,
    get_flight_deals,
    compare_flight_options,
    suggest_flight_dates
)
from tools.flight_booking_tools import (
    quick_book_flight,
    format_flight_booking_confirmation,
    save_flight_booking_to_database,
    get_user_flight_bookings,
    cancel_flight_booking_in_database,
    format_flight_bookings_list
)

def create_hotel_agent():
    """Create a ReAct agent with hotel planning tools."""
    
    # Initialize LLM
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Streamlined tools to prevent recursion issues
    tools = [
        # Core search tools
        fetch_hotels,                    # Basic hotel search
        search_hotels_near_landmark,      # Search near landmarks
        search_hotels_by_chain,           # Search by hotel chain
        
        # Essential filtering tools
        filter_hotels_by_price,          # Filter by price
        filter_hotels_by_rating,         # Filter by rating
        filter_hotels_by_amenities,      # Filter by amenities
        
        # Essential sorting tools
        sort_hotels_by_price,            # Sort by price
        sort_hotels_by_rating,           # Sort by rating
        sort_hotels_by_value,            # Sort by value
        
        # Essential analysis tools
        get_top_hotels,                  # Get top N hotels
        format_hotel_cards,              # Format hotels as clean cards
        get_hotel_summary,               # Get hotel summary
        
        # Budget tools
        calculate_total_budget,          # Calculate total costs
        
        # Exploration tools
        get_nearby_places,              # Get nearby attractions
        
        # Flight search tools
        search_flights,                 # Search for flights
        search_flights_by_price,        # Search flights by price range
        search_flights_by_airline,      # Search flights by airline
        search_flights_by_duration,     # Search flights by duration
        get_flight_deals,              # Get flight deals
        compare_flight_options,         # Compare flight options
        suggest_flight_dates,          # Suggest alternative dates when no flights found
        
        # Flight booking tools
        quick_book_flight,             # Complete flight booking
        format_flight_booking_confirmation, # Format flight confirmation
        save_flight_booking_to_database,    # Save flight booking
        get_user_flight_bookings,      # Get user's flight bookings
        cancel_flight_booking_in_database,  # Cancel flight booking
        format_flight_bookings_list,   # Format flight bookings list
        
        # Hotel booking tools
        quick_book_hotel,               # Complete booking process
        format_booking_confirmation,    # Format booking confirmation
        save_booking_to_database,       # Save booking to database
        get_user_bookings,              # Get user's booking history
        cancel_booking_in_database      # Cancel booking
    ]
    
    # Simplified system message to prevent recursion
    system_message = SystemMessage(content="""You are HolidAI, an AI travel assistant. Help users find and book hotels AND flights efficiently.

SEARCH & FILTERING:
- fetch_hotels: Search hotels (city, dates, guests)
- search_hotels_near_landmark: Find hotels near attractions
- search_hotels_by_chain: Search specific hotel chains
- filter_hotels_by_price: Filter by maximum price
- filter_hotels_by_rating: Filter by minimum rating
- filter_hotels_by_amenities: Filter by required amenities
- sort_hotels_by_price: Sort by price
- sort_hotels_by_rating: Sort by rating
- sort_hotels_by_value: Sort by value (rating/price)

ANALYSIS & PRESENTATION:
- get_top_hotels: Get top N hotels
- format_hotel_cards: Format hotels as clean cards
- get_hotel_summary: Get hotel summary
- calculate_total_budget: Calculate total costs
- get_nearby_places: Find nearby attractions

FLIGHT SEARCH:
- search_flights: Search flights (origin, destination, dates, passengers)
- search_flights_by_price: Search flights by price range
- search_flights_by_airline: Search flights by specific airline
- search_flights_by_duration: Search flights by duration
- get_flight_deals: Get flight deals and offers
- compare_flight_options: Compare different flight options
- suggest_flight_dates: Suggest alternative dates when no flights found

HOTEL BOOKING:
- quick_book_hotel: Complete hotel booking (hotel, dates, guests, guest info)
- format_booking_confirmation: Show formatted hotel booking confirmation
- save_booking_to_database: Save hotel booking to database
- get_user_bookings: Show user's hotel booking history
- cancel_booking_in_database: Cancel existing hotel booking

FLIGHT BOOKING:
- quick_book_flight: Complete flight booking (flight data, passenger info)
- format_flight_booking_confirmation: Show formatted flight booking confirmation
- save_flight_booking_to_database: Save flight booking to database
- get_user_flight_bookings: Show user's flight booking history
- cancel_flight_booking_in_database: Cancel existing flight booking
- format_flight_bookings_list: Format flight bookings list

GUIDELINES:
1. Ask for missing info (city, dates, preferences for hotels; origin, destination, dates for flights)
2. Use format_hotel_cards for clean hotel presentation
3. Show max 5 hotels/flights to avoid overwhelming users
4. For hotel bookings: use quick_book_hotel with all details at once
5. For flight bookings: use quick_book_flight with flight data and passenger info
6. Keep responses concise and focused
7. Always use real data from tools
8. Support both hotel and flight search/booking requests
9. When no flights found: use suggest_flight_dates to offer alternatives
10. Explain why flights might not be available (dates too far ahead, route issues, etc.)
11. Provide helpful suggestions and alternative options when searches fail""")
    
    # Create ReAct agent with tools
    agent = create_react_agent(llm, tools)
    
    return agent, system_message


def validate_request_complexity(user_message: str) -> tuple[bool, str]:
    """Validate if request is too complex and suggest simplifications."""
    message_lower = user_message.lower()
    
    # Check for multiple cities
    city_indicators = ['in ', 'at ', 'near ', 'around ']
    city_count = sum(1 for indicator in city_indicators if indicator in message_lower)
    
    # Check for multiple requirements
    requirement_words = ['and', 'also', 'plus', 'additionally', 'furthermore']
    requirement_count = sum(1 for word in requirement_words if word in message_lower)
    
    # Check for very long messages
    if len(user_message) > 200:
        return False, "Your request seems quite detailed. Try asking about one city or hotel type at a time."
    
    # Check for multiple cities
    if city_count > 2:
        return False, "I can help you search one city at a time. Which city would you like to start with?"
    
    # Check for too many requirements
    if requirement_count > 3:
        return False, "Let's focus on your most important requirements first. What's your top priority?"
    
    return True, ""

def chat_with_agent(agent, system_message, user_message: str, conversation_history=None):
    """Chat with the agent with recursion limit handling."""
    if conversation_history is None:
        conversation_history = []
    
    # Validate request complexity first
    is_valid, validation_message = validate_request_complexity(user_message)
    if not is_valid:
        return validation_message, conversation_history
    
    # Build message list
    messages = [system_message]
    for msg in conversation_history:
        messages.append(msg)
    
    # Add user message
    messages.append(HumanMessage(content=user_message))
    
    try:
        # Run agent with recursion limit
        result = agent.invoke(
            {"messages": messages},
            config={"recursion_limit": 20}  # Increased limit to 20 steps
        )
        
        # Get the last AI message
        ai_messages = [msg for msg in result["messages"] if msg.type == "ai"]
        if ai_messages:
            response = ai_messages[-1].content
        else:
            response = "I'm sorry, I couldn't process that request. Please try rephrasing your question."
        
        return response, result["messages"]
        
    except Exception as e:
        # Handle recursion or other errors gracefully
        error_msg = str(e)
        if "recursion" in error_msg.lower():
            return """I apologize, but I encountered a processing limit. Here are some ways to help:

🔧 **Try breaking down your request:**
- Ask about one city at a time
- Specify your budget range
- Mention specific amenities you need
- Ask for hotels in a particular area

💡 **Example focused questions:**
- "Find hotels in Paris under $200 per night"
- "Show me 4-star hotels with pools in Miami"
- "What are the top-rated hotels near Times Square?"

Would you like to try a more specific search?""", messages
        else:
            return f"I encountered an error: {error_msg}. Please try rephrasing your question.", messages


if __name__ == "__main__":
    # Test the agent
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not found in .env file")
        exit(1)
    
    if not os.getenv("SERPAPI_KEY"):
        print("❌ Error: SERPAPI_KEY not found in .env file")
        exit(1)
    
    print("🤖 HotelPlanner Agent - ReAct Agent with Tools")
    print("Type 'quit' to exit.\n")
    
    agent, system_message = create_hotel_agent()
    conversation = []
    
    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("👋 Goodbye!")
                break
            
            if not user_input:
                continue
            
            print("🤖 Thinking...")
            response, conversation = chat_with_agent(agent, system_message, user_input, conversation)
            print(f"Agent: {response}\n")
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"❌ Error: {e}\n")

