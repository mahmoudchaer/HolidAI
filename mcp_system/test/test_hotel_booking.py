"""Test script for Hotel Booking functionality."""

import asyncio
import io
import sys
import os
import json
from datetime import datetime, timedelta

# Fix encoding for Windows console
if __name__ == "__main__":
    try:
        if hasattr(sys.stdout, 'buffer') and sys.stdout.buffer is not None:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except (AttributeError, ValueError, OSError):
        pass

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.hotel_agent_client import HotelAgentClient


async def test_hotel_booking():
    """Test Hotel Booking functionality."""
    print("=" * 70)
    print("Testing Hotel Booking Functionality")
    print("=" * 70)
    
    try:
        # Step 1: First, search for hotel rates to get a rate_id
        print("\n" + "=" * 70)
        print("STEP 1: Search for Hotel Rates (to get rate_id)")
        print("=" * 70)
        
        # Calculate dates (7 days from now for check-in, 3 nights stay)
        checkin_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        checkout_date = (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')
        
        print(f"\n📅 Search Parameters:")
        print(f"  Check-in: {checkin_date}")
        print(f"  Check-out: {checkout_date}")
        print(f"  Location: Paris, France")
        print(f"  Occupancy: 2 adults")
        
        print("\n🔍 Searching for hotel rates...")
        rates_result = await HotelAgentClient.call_tool(
            "get_hotel_rates",
            checkin=checkin_date,
            checkout=checkout_date,
            occupancies=[{"adults": 2}],
            city_name="Paris",
            country_code="FR",
            k=3  # Get top 3 hotels
        )
        
        if rates_result.get("error"):
            print(f"\n✗ Error searching for rates: {rates_result.get('error_message')}")
            if rates_result.get("suggestion"):
                print(f"  Suggestion: {rates_result.get('suggestion')}")
            return
        
        hotels = rates_result.get("hotels", [])
        if not hotels or len(hotels) == 0:
            print("\n✗ No hotels found. Cannot proceed with booking test.")
            print("  Try different dates or location.")
            return
        
        print(f"\n✓ Found {len(hotels)} hotel(s) with rates")
        
        # Extract hotel_id and rate_id (optionRefId) from the first hotel
        selected_hotel = hotels[0]
        hotel_id = selected_hotel.get("hotelId") or selected_hotel.get("id")
        
        # Try to find optionRefId in the response
        rate_id = None
        option_ref_id = None
        
        # Check in roomTypes -> rates -> optionRefId
        if "roomTypes" in selected_hotel and isinstance(selected_hotel["roomTypes"], list):
            for room_type in selected_hotel["roomTypes"]:
                if "rates" in room_type and isinstance(room_type["rates"], list):
                    for rate in room_type["rates"]:
                        if "optionRefId" in rate:
                            option_ref_id = rate["optionRefId"]
                            break
                        if "rateId" in rate:
                            rate_id = rate["rateId"]
                            break
                    if option_ref_id or rate_id:
                        break
        
        # Also check directly in the hotel object
        if not option_ref_id and not rate_id:
            option_ref_id = selected_hotel.get("optionRefId")
            rate_id = selected_hotel.get("rateId")
        
        # Use optionRefId if available, otherwise use rateId
        booking_rate_id = option_ref_id or rate_id
        
        if not hotel_id:
            print("\n✗ Error: Could not extract hotel_id from rates response")
            print(f"  Hotel data: {json.dumps(selected_hotel, indent=2)[:500]}")
            return
        
        if not booking_rate_id:
            print("\n⚠️  Warning: Could not find optionRefId or rateId in response")
            print("  This might be because:")
            print("  1. The API response structure is different")
            print("  2. The rate needs to be selected differently")
            print("\n  Attempting to use hotel_id as rate_id (may not work)...")
            booking_rate_id = hotel_id
        
        print(f"\n📋 Selected Hotel for Booking:")
        print(f"  Hotel ID: {hotel_id}")
        print(f"  Rate ID (optionRefId): {booking_rate_id}")
        if selected_hotel.get("name"):
            print(f"  Hotel Name: {selected_hotel.get('name')}")
        
        # Step 2: Test booking with sample data
        print("\n" + "=" * 70)
        print("STEP 2: Test Hotel Booking")
        print("=" * 70)
        
        print("\n💳 Booking Parameters:")
        print(f"  Hotel ID: {hotel_id}")
        print(f"  Rate ID: {booking_rate_id}")
        print(f"  Check-in: {checkin_date}")
        print(f"  Check-out: {checkout_date}")
        print(f"  Guest: John Doe (john.doe@example.com)")
        print(f"  Payment: Test card (4242424242424242)")
        
        # IMPORTANT: Use test/sandbox card numbers for testing
        # LiteAPI sandbox typically accepts test cards like 4242424242424242
        print("\n⚠️  NOTE: Using test card number. For production, use real payment details.")
        print("  Make sure you're using LiteAPI sandbox/test environment!")
        
        print("\n🔐 Attempting to book hotel room...")
        booking_result = await HotelAgentClient.call_tool(
            "book_hotel_room",
            hotel_id=hotel_id,
            rate_id=booking_rate_id,
            checkin=checkin_date,
            checkout=checkout_date,
            occupancies=[{"adults": 2}],
            guest_first_name="John",
            guest_last_name="Doe",
            guest_email="john.doe@example.com",
            card_number="4242424242424242",  # Test card
            card_expiry="12/25",
            card_cvv="123",
            card_holder_name="John Doe",
            guest_phone="+1234567890",
            currency="USD",
            client_reference="TEST-BOOKING-001",
            remarks="Test booking from automated test script"
        )
        
        print("\n" + "=" * 70)
        print("Booking Result")
        print("=" * 70)
        
        if booking_result.get("error"):
            print(f"\n✗ Booking Failed")
            print(f"  Error Code: {booking_result.get('error_code', 'UNKNOWN')}")
            print(f"  Error Message: {booking_result.get('error_message')}")
            if booking_result.get("api_error_details"):
                print(f"  API Details: {booking_result.get('api_error_details')}")
            if booking_result.get("suggestion"):
                print(f"  Suggestion: {booking_result.get('suggestion')}")
            
            print("\n📝 Common Issues:")
            print("  1. Invalid rate_id (optionRefId) - Make sure it's from a recent rates search")
            print("  2. Rate no longer available - Rates expire quickly, search again")
            print("  3. Payment declined - Check if using test/sandbox environment")
            print("  4. API key issues - Verify LITEAPI_KEY in .env file")
            print("  5. Rate structure - The rate_id format might be different")
            
            # Show the raw response for debugging
            print("\n🔍 Raw Booking Response (for debugging):")
            print(json.dumps(booking_result, indent=2, ensure_ascii=False))
        else:
            print(f"\n✓ Booking Successful!")
            print(f"  Booking ID: {booking_result.get('booking_id', 'N/A')}")
            print(f"  Confirmation Code: {booking_result.get('confirmation_code', 'N/A')}")
            print(f"  Status: {booking_result.get('status', 'N/A')}")
            
            if booking_result.get("booking"):
                booking_data = booking_result.get("booking")
                print(f"\n📋 Full Booking Details:")
                print(json.dumps(booking_data, indent=2, ensure_ascii=False))
        
        # Step 3: Test validation errors
        print("\n" + "=" * 70)
        print("STEP 3: Test Booking Validation")
        print("=" * 70)
        
        validation_tests = [
            {
                "name": "Missing hotel_id",
                "params": {
                    "rate_id": "test_rate",
                    "checkin": checkin_date,
                    "checkout": checkout_date,
                    "occupancies": [{"adults": 2}],
                    "guest_first_name": "John",
                    "guest_last_name": "Doe",
                    "guest_email": "john@example.com",
                    "card_number": "4242424242424242",
                    "card_expiry": "12/25",
                    "card_cvv": "123",
                    "card_holder_name": "John Doe"
                },
                "expected_error": "hotel_id"
            },
            {
                "name": "Invalid email format",
                "params": {
                    "hotel_id": hotel_id,
                    "rate_id": booking_rate_id,
                    "checkin": checkin_date,
                    "checkout": checkout_date,
                    "occupancies": [{"adults": 2}],
                    "guest_first_name": "John",
                    "guest_last_name": "Doe",
                    "guest_email": "invalid-email",
                    "card_number": "4242424242424242",
                    "card_expiry": "12/25",
                    "card_cvv": "123",
                    "card_holder_name": "John Doe"
                },
                "expected_error": "email"
            },
            {
                "name": "Invalid card expiry format",
                "params": {
                    "hotel_id": hotel_id,
                    "rate_id": booking_rate_id,
                    "checkin": checkin_date,
                    "checkout": checkout_date,
                    "occupancies": [{"adults": 2}],
                    "guest_first_name": "John",
                    "guest_last_name": "Doe",
                    "guest_email": "john@example.com",
                    "card_number": "4242424242424242",
                    "card_expiry": "invalid",
                    "card_cvv": "123",
                    "card_holder_name": "John Doe"
                },
                "expected_error": "expiry"
            }
        ]
        
        for test in validation_tests:
            print(f"\n🧪 Testing: {test['name']}...")
            result = await HotelAgentClient.call_tool("book_hotel_room", **test["params"])
            if result.get("error") and result.get("error_code") == "VALIDATION_ERROR":
                print(f"  ✓ Validation error caught: {result.get('error_message')[:80]}...")
            else:
                print(f"  ✗ Expected validation error but got: {result.get('error_code', 'SUCCESS')}")
        
    except Exception as e:
        print(f"\n✗ Error testing Hotel Booking: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        await HotelAgentClient.close()
    
    print("\n" + "=" * 70)
    print("Hotel Booking Test Complete!")
    print("=" * 70)
    print("\n💡 Tips:")
    print("  - Use LiteAPI sandbox/test environment for testing")
    print("  - Rates expire quickly - always search for fresh rates before booking")
    print("  - Check LiteAPI documentation for correct rate_id format")
    print("  - Verify your LITEAPI_KEY has booking permissions")


if __name__ == "__main__":
    asyncio.run(test_hotel_booking())

