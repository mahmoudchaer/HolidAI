# Known Limitations and Important Notes

## Hotel Pricing Limitation

### Issue:
The `get_list_of_hotels` tool returns hotel metadata (name, address, rating, stars, amenities, images) but **NO PRICING INFORMATION**.

### Why:
- `get_list_of_hotels` is designed for browsing hotels WITHOUT requiring dates
- Hotel room rates depend on check-in/check-out dates and occupancy
- Without dates, there are no rates to return

### Solution:
**If user wants hotel PRICES:**
- Use `get_hotel_rates` or `get_hotel_rates_by_price` tools
- These tools REQUIRE:
  - Check-in date (`checkin`)
  - Check-out date (`checkout`)
  - Occupancy details (`occupancies`)
  - Location (city_name + country_code)

### Example Queries:

❌ **Won't work for price conversions:**
```
"Get hotels in Beirut and convert prices to EUR"
```
→ `get_list_of_hotels` returns no prices to convert

✅ **Will work for price conversions:**
```
"Get hotel rates in Beirut for Dec 1-5 and convert prices to EUR"
```
→ `get_hotel_rates` returns actual room rates that can be converted

## Agent Confusion with Multi-Domain Queries

### Issue:
When a query mentions multiple domains (hotels + restaurants), individual agents may get confused because they receive the full user message.

### Example:
```
User: "Get hotels and restaurants in Beirut. Convert hotel prices to EUR."
```
- TripAdvisor agent may search for "hotels" instead of focusing on "restaurants"
- Utilities agent may call extra tools (like weather) not requested

### Solutions Implemented:
1. **Updated agent prompts** to focus on their specific domain
2. **TripAdvisor agent** now ignores hotel-related queries
3. **Utilities agent** now focuses only on explicitly requested operations

### Best Practice:
For complex queries, the main agent should break them into focused steps where each agent receives clear context.

## Currency Conversion Requirements

### To convert prices:
1. **Prices must exist** in the data (from `get_hotel_rates`, `get_esim_bundles`, etc.)
2. **Specify currencies** (from_currency, to_currency)
3. **Optionally specify amount** (if not provided, will use 1.0 as default)

### Tools that provide prices:
- ✅ `get_hotel_rates` - provides room rates
- ✅ `get_hotel_rates_by_price` - provides room rates sorted by price
- ✅ `get_esim_bundles` - provides eSIM bundle prices
- ✅ `agent_get_flights_tool` - provides flight prices
- ❌ `get_list_of_hotels` - NO prices (metadata only)
- ❌ `get_hotel_details` - NO prices (metadata only)
- ❌ `search_locations` - NO prices (locations/attractions)

## Hallucination Prevention

### Conversational Agent Rules:
- **NEVER make up prices** if they don't exist in the data
- **NEVER invent information** not provided by specialized agents
- **ONLY show data** that actually exists in the collected_info

### If hotels don't have prices:
- ✅ Show: name, rating, location, amenities, description
- ❌ DON'T show: made-up prices or fake currency conversions

