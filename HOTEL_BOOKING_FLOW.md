# Hotel Booking Flow - Complete Guide

## Overview

This document explains what happens when a user asks to book a specific hotel after viewing available options.

## Complete Flow

### Step 1: User Searches for Hotels
**User says:** "Find hotels in Paris for December 10-17"

**What happens:**
1. Request goes through: `memory_agent` → `rfi_node` → `main_agent` → `plan_executor` → `hotel_agent`
2. `hotel_agent` calls `get_hotel_rates` tool
3. Results stored in `state.hotel_result` with structure:
   ```json
   {
     "error": false,
     "hotels": [
       {
         "hotelId": "lp1336",
         "name": "Hotel Example",
         "roomTypes": [
           {
             "rates": [
               {
                 "optionRefId": "opt_12345",
                 "rateId": "rate_67890"
               }
             ]
           }
         ]
       }
     ]
   }
   ```
4. Results flow to `conversational_agent` which displays them to the user

### Step 2: User Selects a Hotel to Book
**User says:** "Book the first hotel" or "I want to book Hotel Example"

**What happens:**
1. Request goes through: `memory_agent` → `rfi_node` → `main_agent` → `plan_executor` → `hotel_agent`
2. **NEW:** `hotel_agent` now receives:
   - `user_message`: "Book the first hotel"
   - `previous_hotel_result`: The previous search results from `state.hotel_result`
   - Context showing available hotels with their `hotel_id` and `rate_id` (optionRefId)

3. The agent's prompt includes:
   ```
   === PREVIOUS HOTEL SEARCH RESULTS (for booking reference) ===
   Hotel 1: Hotel Example
     - hotel_id: lp1336
     - rate_id (optionRefId): opt_12345
   ```

4. Agent extracts:
   - `hotel_id`: From `hotel.hotelId` or `hotel.id`
   - `rate_id`: From `hotel.roomTypes[].rates[].optionRefId` or `hotel.optionRefId`
   - Guest info: From user message (name, email, phone)
   - Payment info: From user message (card number, expiry, CVV, holder name)
   - Dates: From previous search or user message
   - Occupancies: From previous search or user message

5. Agent calls `book_hotel_room` tool with extracted parameters

### Step 3: Booking Tool Execution
**Tool called:** `book_hotel_room`

**Parameters:**
- `hotel_id`: "lp1336" (extracted from previous results)
- `rate_id`: "opt_12345" (extracted from previous results)
- `checkin`: "2025-12-10" (from previous search)
- `checkout`: "2025-12-17" (from previous search)
- `occupancies`: [{"adults": 2}] (from previous search)
- `guest_first_name`: "John" (from user message)
- `guest_last_name`: "Doe" (from user message)
- `guest_email`: "john@example.com" (from user message)
- `card_number`: "4242424242424242" (from user message)
- `card_expiry`: "12/25" (from user message)
- `card_cvv`: "123" (from user message)
- `card_holder_name`: "John Doe" (from user message)

**What happens:**
1. Tool validates all parameters
2. Makes API call to LiteAPI: `POST /v3.0/bookings`
3. Returns booking result:
   ```json
   {
     "error": false,
     "booking_id": "booking_abc123",
     "confirmation_code": "CONF-456789",
     "status": "confirmed",
     "booking": { ... }
   }
   ```

### Step 4: Result Handling
**What happens:**
1. `hotel_agent` stores booking result in `state.hotel_result`
2. Routes to `hotel_agent_feedback` for validation
3. Then to `plan_executor` → `join_node` → `conversational_agent`
4. `conversational_agent` formats and displays the booking confirmation to the user

## Routing Path

```
User Request
    ↓
memory_agent (retrieve memories)
    ↓
rfi_node (validate completeness)
    ↓
main_agent (determine needs)
    ↓
plan_executor (create execution plan)
    ↓
hotel_agent (execute booking)
    ↓
hotel_agent_feedback (validate result)
    ↓
plan_executor (continue or finish)
    ↓
join_node (collect all results)
    ↓
conversational_agent (format response)
    ↓
END (return to user)
```

## Key Features

### ✅ What Works Now

1. **Previous Results Access**: Hotel agent can access `state.hotel_result` from previous searches
2. **Context Injection**: Previous hotel results are automatically included in the agent's context
3. **ID Extraction**: Agent knows how to extract `hotel_id` and `rate_id` from previous results
4. **Tool Routing**: `book_hotel_room` tool is properly registered and accessible
5. **Result Handling**: Booking results are properly stored and routed to conversational agent

### ⚠️ Requirements

For booking to work, the user must provide:
1. **Guest Information**:
   - First name
   - Last name
   - Email
   - Phone (optional)

2. **Payment Information**:
   - Card number
   - Card expiry (MM/YY or MM/YYYY)
   - CVV
   - Card holder name

3. **Previous Hotel Search**: Must have called `get_hotel_rates` first to get valid `hotel_id` and `rate_id`

### 🔄 Fallback Behavior

If previous results are not available:
- Agent will first call `get_hotel_rates` to get hotels and rates
- Then extract IDs and proceed with booking

If `rate_id` is missing from previous results:
- Agent may need to call `get_hotel_rates` again for the specific hotel
- Or inform user that rates need to be refreshed

## Example User Flow

```
User: "Find hotels in Paris for December 10-17 for 2 adults"
→ System: Shows 5 hotels with prices

User: "I want to book the first hotel. My name is John Doe, email is john@example.com. 
       Card: 4242424242424242, expiry 12/25, CVV 123, name John Doe"
→ System: 
   1. Extracts hotel_id="lp1336" and rate_id="opt_12345" from first hotel
   2. Calls book_hotel_room with all parameters
   3. Returns: "Booking confirmed! Booking ID: booking_abc123, Confirmation: CONF-456789"
```

## Testing

To test the booking flow:

1. **Search for hotels first:**
   ```
   "Find hotels in Paris for December 10-17"
   ```

2. **Then book:**
   ```
   "Book the first hotel. Name: John Doe, Email: john@example.com, 
    Card: 4242424242424242, Expiry: 12/25, CVV: 123"
   ```

The system should:
- ✅ Extract hotel_id and rate_id from previous results
- ✅ Call book_hotel_room tool
- ✅ Return booking confirmation

## Troubleshooting

### Issue: "Cannot find rate_id"
**Solution:** The API response structure might be different. Check:
- `hotel.roomTypes[].rates[].optionRefId`
- `hotel.optionRefId`
- May need to call `get_hotel_rates` again for that specific hotel

### Issue: "Previous results not available"
**Solution:** The agent will automatically call `get_hotel_rates` first if needed

### Issue: "Missing payment information"
**Solution:** Agent will ask user for missing payment details (handled by RFI node)

