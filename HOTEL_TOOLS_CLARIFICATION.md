# Hotel Tools Clarification

## Important Distinction

There are THREE different hotel tools with different purposes:

### 1. `get_list_of_hotels` ⭐ PRIMARY BROWSING TOOL
**Purpose**: Search and browse hotels in a city/location
**Requires**: At least one search criterion (city_name, country_code, hotel_name, or geo coordinates)
**Does NOT require**: Dates, occupancy
**Use case**: General hotel browsing, finding hotels in a city, searching by name
**Example**: "Find hotels in Beirut", "Show me hotels in Paris", "Search for Hilton hotels"
**Returns**: List of hotels with metadata (name, address, rating, stars, amenities, images)
**⚠️ CRITICAL**: This tool returns NO PRICES/RATES - only general hotel information

### 2. `get_hotel_details`
**Purpose**: Get detailed information about a SPECIFIC hotel
**Requires**: `hotel_id` (e.g., 'lp42fec')
**Does NOT require**: Dates, occupancy
**Use case**: Getting full details of a specific hotel when you already have its ID
**Example**: "Tell me more about hotel lp42fec", "Get details of this hotel"
**Returns**: Comprehensive hotel information (description, facilities, rooms, policies, reviews)

### 3. `get_hotel_rates`
**Purpose**: Get room availability and pricing for specific dates
**Requires**: 
- Destination (city_name, country_code) OR hotel_ids
- Check-in date
- Check-out date
- Occupancy (number of adults/children)
**Use case**: Booking, checking availability, getting room prices
**Example**: "Book a hotel in Paris for Feb 1-7", "Hotel rates in Rome for next week"
**Returns**: Available rooms with pricing for the specified dates

## Why This Matters

- **get_list_of_hotels**: Can be called WITHOUT dates (browsing/searching)
- **get_hotel_details**: Can be called WITHOUT dates (viewing specific hotel)
- **get_hotel_rates**: MUST have dates (checking availability/pricing)

## Decision Tree for Hotel Agent

### User Query Analysis:

**1. General browsing/searching** ("Find hotels in Beirut", "Hotels in Paris", "Show me hotels")
   → Use `get_list_of_hotels`
   - No dates needed
   - Searches by city, country, or name
   - Returns list of hotels with basic info
   
**2. Specific hotel details** ("Tell me about hotel lp42fec", "Get details of this hotel")
   → Use `get_hotel_details`
   - Requires hotel_id
   - No dates needed
   - Returns comprehensive hotel information
   
**3. Booking/availability/pricing** ("Book hotel in Paris for Feb 1-7", "Hotel rates", "Check availability")
   → Use `get_hotel_rates`
   - Dates REQUIRED
   - If user doesn't provide dates, agent should ask for them
   - Returns available rooms with pricing

## Previous Issue (FIXED)

The system was trying to use `get_hotel_rates` for general browsing queries like "Find hotels in Beirut", which failed because:
1. User didn't provide dates
2. The tool requires dates for rate lookups
3. There was NO tool available for general hotel browsing

## Solution Implemented

✅ Created `get_list_of_hotels` tool for general hotel browsing
✅ Updated `hotel_docs.json` with clear use cases and distinctions
✅ Now hotel agent can:
   1. Browse hotels without dates using `get_list_of_hotels`
   2. View specific hotel details using `get_hotel_details`
   3. Check availability/pricing using `get_hotel_rates` (dates required)

