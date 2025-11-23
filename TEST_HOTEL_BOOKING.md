# How to Test Hotel Booking Functionality

This guide explains how to test the hotel booking tool that was integrated with LiteAPI.

## Prerequisites

1. **LiteAPI API Key**: Make sure you have `LITEAPI_KEY` set in your `.env` file
2. **MCP Server Running**: The MCP server must be running to test the tools
3. **Test Environment**: Use LiteAPI's sandbox/test environment for safe testing

## Testing Methods

### Method 1: Automated Test Script (Recommended)

We've created a dedicated test script that tests the complete booking flow:

```bash
cd mcp_system/test
python test_hotel_booking.py
```

This script will:
1. Search for hotel rates to get a valid `rate_id` (optionRefId)
2. Attempt to book a room with test payment details
3. Test validation errors
4. Show detailed results and debugging information

### Method 2: Manual Testing via Python

You can test the booking tool directly using Python:

```python
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "mcp_system"))

from clients.hotel_agent_client import HotelAgentClient

async def test_booking():
    # Step 1: Search for rates first
    rates_result = await HotelAgentClient.call_tool(
        "get_hotel_rates",
        checkin="2025-12-10",
        checkout="2025-12-17",
        occupancies=[{"adults": 2}],
        city_name="Paris",
        country_code="FR"
    )
    
    if rates_result.get("error"):
        print(f"Error: {rates_result.get('error_message')}")
        return
    
    hotels = rates_result.get("hotels", [])
    if not hotels:
        print("No hotels found")
        return
    
    # Extract hotel_id and rate_id from first hotel
    hotel = hotels[0]
    hotel_id = hotel.get("hotelId")
    
    # Find optionRefId in the rates response
    rate_id = None
    if "roomTypes" in hotel:
        for room_type in hotel.get("roomTypes", []):
            for rate in room_type.get("rates", []):
                if "optionRefId" in rate:
                    rate_id = rate["optionRefId"]
                    break
            if rate_id:
                break
    
    if not rate_id:
        print("Could not find rate_id (optionRefId) in response")
        return
    
    # Step 2: Book the room
    booking_result = await HotelAgentClient.call_tool(
        "book_hotel_room",
        hotel_id=hotel_id,
        rate_id=rate_id,
        checkin="2025-12-10",
        checkout="2025-12-17",
        occupancies=[{"adults": 2}],
        guest_first_name="John",
        guest_last_name="Doe",
        guest_email="john.doe@example.com",
        card_number="4242424242424242",  # Test card
        card_expiry="12/25",
        card_cvv="123",
        card_holder_name="John Doe"
    )
    
    if booking_result.get("error"):
        print(f"Booking failed: {booking_result.get('error_message')}")
    else:
        print(f"Booking successful!")
        print(f"Booking ID: {booking_result.get('booking_id')}")
        print(f"Confirmation: {booking_result.get('confirmation_code')}")
    
    await HotelAgentClient.close()

asyncio.run(test_booking())
```

### Method 3: Testing via the Hotel Agent (End-to-End)

Test the booking through the actual hotel agent node:

1. **Start the LangGraph system** (if not already running)
2. **Send a booking request** through the chat interface or API

Example user message:
```
"I want to book a hotel in Paris for December 10-17 for 2 adults. 
My name is John Doe, email is john.doe@example.com. 
Card: 4242424242424242, expiry 12/25, CVV 123, name John Doe."
```

The agent should:
1. Search for hotel rates
2. Extract the rate_id from the response
3. Call the booking tool with the provided information

## Important Notes

### 1. Rate ID (optionRefId) Requirements

The booking tool requires a `rate_id` (optionRefId) from a **recent** hotel rates search. Important points:

- **Rates expire quickly** - Always search for fresh rates before booking
- The `optionRefId` is found in the `rates` array within `roomTypes` in the hotel response
- If you can't find `optionRefId`, the API response structure might be different

### 2. Test Payment Cards

For testing, use LiteAPI's test/sandbox card numbers:
- **Test Card**: `4242424242424242`
- **Expiry**: Any future date (e.g., `12/25`)
- **CVV**: Any 3-4 digits (e.g., `123`)

⚠️ **Never use real payment cards in test environments!**

### 3. Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| "Invalid rate_id" | Search for fresh rates - rates expire quickly |
| "Rate no longer available" | The rate might have been booked or expired. Search again. |
| "Payment declined" | Check if you're using test/sandbox environment |
| "Authentication failed" | Verify `LITEAPI_KEY` in `.env` file |
| "Cannot find optionRefId" | Check the API response structure - it might be in a different field |

### 4. Response Structure

The booking tool returns:
- `booking_id`: Unique booking identifier
- `confirmation_code`: Hotel confirmation code
- `status`: Booking status (typically "confirmed")
- `booking`: Full booking details from LiteAPI

## Verification Checklist

- [ ] MCP server is running
- [ ] `LITEAPI_KEY` is set in `.env`
- [ ] Can search for hotel rates successfully
- [ ] Can extract `rate_id` (optionRefId) from rates response
- [ ] Booking tool is registered and accessible
- [ ] Validation errors work correctly
- [ ] Booking succeeds (or fails gracefully with clear error messages)

## Debugging

If booking fails, check:

1. **API Response Structure**: Print the rates response to see the exact structure:
   ```python
   import json
   print(json.dumps(rates_result, indent=2))
   ```

2. **Rate ID Location**: The `optionRefId` might be in different locations:
   - `hotel.roomTypes[].rates[].optionRefId`
   - `hotel.optionRefId`
   - `hotel.rates[].optionRefId`

3. **API Logs**: Check the MCP server logs for detailed error messages

4. **LiteAPI Documentation**: Verify the booking endpoint structure matches LiteAPI's current API

## Next Steps

After successful testing:
1. Integrate booking into your user interface
2. Handle booking confirmations and display them to users
3. Store booking references for future lookups
4. Implement booking cancellation if needed

