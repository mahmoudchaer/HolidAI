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
from langchain_anthropic import ChatAnthropic
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
from tools.serpapi_tools import fetch_hotels, get_hotel_details
from tools.hotel_tools import (
    filter_hotels_by_rating,
    filter_hotels_by_price,
    filter_hotels_by_class,
    sort_hotels_by_price,
    sort_hotels_by_rating,
    get_top_hotels,
    select_hotel_by_index,
    get_hotel_summary
)
from tools.budget_tools import (
    calculate_total_budget,
    estimate_daily_expenses
)
from tools.explore_tools import (
    get_nearby_places,
    format_nearby_places
)

def create_hotel_agent():
    """Create a ReAct agent with hotel planning tools."""
    
    # Initialize LLM
    llm = ChatAnthropic(
        model="claude-3-5-sonnet-20241022",
        temperature=0,
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    
    # Essential tools only (reduced to save tokens)
    tools = [
        fetch_hotels,          # Search hotels
        filter_hotels_by_price, # Filter by price
        sort_hotels_by_price,   # Sort by price
        get_top_hotels,         # Get top N
        get_hotel_summary,      # Show summary
        calculate_total_budget, # Budget calc
        get_nearby_places,      # Nearby places
        format_nearby_places    # Format places
    ]
    
    # System message - shorter to save tokens
    system_message = SystemMessage(content="""You are HotelPlanner. Help users find hotels using these tools:

- fetch_hotels: Search hotels (needs city, check_in_date, check_out_date)
- filter_hotels_by_price: Filter by max price
- sort_hotels_by_price: Sort by price
- get_top_hotels: Get top N (default 5)
- get_hotel_summary: Show hotel details
- calculate_total_budget: Calculate costs
- get_nearby_places: Get nearby attractions

Always use tools for real data. Ask for city/dates if missing. Show max 5 hotels. Be brief.""")
    
    # Create ReAct agent with tools
    agent = create_react_agent(llm, tools)
    
    return agent, system_message


def chat_with_agent(agent, system_message, user_message: str, conversation_history=None):
    """Chat with the agent."""
    if conversation_history is None:
        conversation_history = []
    
    # Build message list
    messages = [system_message]
    for msg in conversation_history:
        messages.append(msg)
    
    # Add user message
    messages.append(HumanMessage(content=user_message))
    
    # Run agent
    result = agent.invoke({"messages": messages})
    
    # Get the last AI message
    ai_messages = [msg for msg in result["messages"] if msg.type == "ai"]
    if ai_messages:
        response = ai_messages[-1].content
    else:
        response = "I'm sorry, I couldn't process that."
    
    return response, result["messages"]


if __name__ == "__main__":
    # Test the agent
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ Error: ANTHROPIC_API_KEY not found in .env file")
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

