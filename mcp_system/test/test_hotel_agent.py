"""Test script for Hotel Agent Client."""

import asyncio
import io
import sys
import os

# Fix encoding for Windows console (only if buffer is available and when run directly)
if __name__ == "__main__":
    try:
        if hasattr(sys.stdout, 'buffer') and sys.stdout.buffer is not None:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except (AttributeError, ValueError, OSError):
        # If buffer is not available or closed, skip encoding fix
        pass

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.hotel_agent_client import HotelAgentClient


async def test_hotel_agent():
    """Test Hotel Agent Client."""
    print("=" * 60)
    print("Testing Hotel Agent Client")
    print("=" * 60)
    
    try:
        # List tools
        hotel_tools = await HotelAgentClient.list_tools()
        print(f"\n✓ Available tools: {[t['name'] for t in hotel_tools]}")
        
        # Display tool descriptions
        print("\n📋 Tool Descriptions:")
        print("-" * 60)
        for tool in hotel_tools:
            print(f"\n  • {tool['name']}:")
            description = tool.get('description', 'N/A')
            # Show first line of description (main description)
            desc_lines = description.split('\n')
            main_desc = desc_lines[0].strip()
            print(f"    Description: {main_desc}")
            if 'inputSchema' in tool and 'properties' in tool['inputSchema']:
                params = list(tool['inputSchema']['properties'].keys())
                required = tool['inputSchema'].get('required', [])
                print(f"    Parameters: {', '.join(params)}")
                if required:
                    print(f"    Required: {', '.join(required)}")
        
        # Test tools
        print("\n" + "=" * 60)
        print("Testing Tools")
        print("=" * 60)
        
        # Test 1: Search by city and country
        print("\n1. Testing get_hotel_rates (by city and country)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_rates",
            checkin="2025-12-10",
            checkout="2025-12-17",
            occupancies=[{"adults": 2}],
            city_name="Paris",
            country_code="FR"
        )
        if not result.get("error"):
            hotels_count = len(result.get("hotels", []))
            print(f"✓ Found {hotels_count} hotel rates")
            if hotels_count > 0:
                print(f"  First hotel: {result['hotels'][0].get('hotelId', 'N/A') if isinstance(result['hotels'][0], dict) else 'N/A'}")
        else:
            print(f"✗ Error: {result.get('error_message')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 2: Search by IATA code with defaults
        print("\n2. Testing get_hotel_rates (by IATA code, using defaults)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_rates",
            checkin="2025-12-01",
            checkout="2025-12-03",
            occupancies=[{"adults": 1}],
            iata_code="JFK"
        )
        if not result.get("error"):
            hotels_count = len(result.get("hotels", []))
            print(f"✓ Found {hotels_count} hotel rates (using default currency: USD, guestNationality: US)")
            if result.get("message"):
                print(f"  Message: {result.get('message')}")
        else:
            print(f"✗ Error: {result.get('error_message')}")
        
        # Test 3: Multi-room booking
        print("\n3. Testing get_hotel_rates (multi-room booking)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_rates",
            checkin="2025-12-15",
            checkout="2025-12-20",
            occupancies=[
                {"adults": 2},
                {"adults": 1, "children": [10]}
            ],
            city_name="London",
            country_code="GB",
            max_rates_per_hotel=3
        )
        if not result.get("error"):
            hotels_count = len(result.get("hotels", []))
            print(f"✓ Found {hotels_count} hotel rates for multi-room booking")
        else:
            print(f"✗ Error: {result.get('error_message')}")
        
        # Test 3.5: Search with custom k parameter
        print("\n3.5. Testing get_hotel_rates (with k=5 limit)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_rates",
            checkin="2025-12-10",
            checkout="2025-12-17",
            occupancies=[{"adults": 2}],
            city_name="Paris",
            country_code="FR",
            k=5
        )
        if not result.get("error"):
            hotels_count = len(result.get("hotels", []))
            top_k = result.get("search_params", {}).get("top_k", "N/A")
            print(f"✓ Found {hotels_count} hotel rates (limited to top {top_k} as requested)")
            if hotels_count > 5:
                print(f"  Warning: Expected max 5 hotels but got {hotels_count}")
        else:
            print(f"✗ Error: {result.get('error_message')}")
        
        # Test 4: get_hotel_rates_by_price - verify sorting
        print("\n4. Testing get_hotel_rates_by_price (k=5, verify price sorting)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_rates_by_price",
            checkin="2025-12-10",
            checkout="2025-12-17",
            occupancies=[{"adults": 2}],
            city_name="Paris",
            country_code="FR",
            k=5
        )
        if not result.get("error"):
            hotels = result.get("hotels", [])
            hotels_count = len(hotels)
            sort_by = result.get("search_params", {}).get("sort_by", "N/A")
            print(f"✓ Found {hotels_count} hotel rates (sorted by price, top {5} requested)")
            print(f"  Sort method: {sort_by}")
            
            if hotels_count > 0:
                # Extract prices and verify sorting
                prices = []
                for hotel in hotels:
                    price = None
                    # Try to extract price from roomTypes
                    if "roomTypes" in hotel and isinstance(hotel["roomTypes"], list):
                        for room_type in hotel["roomTypes"]:
                            # Try offerRetailRate.amount first
                            if "offerRetailRate" in room_type and "amount" in room_type["offerRetailRate"]:
                                price = float(room_type["offerRetailRate"]["amount"])
                                break
                            # Try rates array
                            if "rates" in room_type and isinstance(room_type["rates"], list):
                                for rate in room_type["rates"]:
                                    if "retailRate" in rate and "total" in rate["retailRate"]:
                                        if isinstance(rate["retailRate"]["total"], list) and len(rate["retailRate"]["total"]) > 0:
                                            if "amount" in rate["retailRate"]["total"][0]:
                                                price = float(rate["retailRate"]["total"][0]["amount"])
                                                break
                                if price:
                                    break
                    prices.append(price if price is not None else float('inf'))
                
                # Verify prices are sorted (ascending)
                if len(prices) > 1:
                    is_sorted = all(prices[i] <= prices[i+1] for i in range(len(prices)-1))
                    if is_sorted:
                        print(f"✓ Prices are correctly sorted (lowest to highest)")
                        print(f"  Price range: ${prices[0]:.2f} - ${prices[-1]:.2f} USD")
                        print(f"  Prices: {[f'${p:.2f}' for p in prices if p != float('inf')]}")
                    else:
                        print(f"✗ ERROR: Prices are NOT sorted correctly!")
                        print(f"  Prices: {[f'${p:.2f}' for p in prices if p != float('inf')]}")
                elif len(prices) == 1:
                    print(f"✓ Single hotel found with price: ${prices[0]:.2f} USD" if prices[0] != float('inf') else "  (Price not available)")
                else:
                    print("  No hotels found to verify sorting")
            else:
                print("  No hotels found")
        else:
            print(f"✗ Error: {result.get('error_message')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 4.5: get_hotel_rates_by_price - Beirut, Lebanon with raw output
        print("\n4.5. Testing get_hotel_rates_by_price (k=5, Beirut, Lebanon - showing raw output)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_rates_by_price",
            checkin="2025-11-12",
            checkout="2025-11-13",
            occupancies=[{"adults": 1}],
            city_name="Beirut",
            country_code="LB",
            k=5
        )
        if not result.get("error"):
            hotels = result.get("hotels", [])
            hotels_count = len(hotels)
            sort_by = result.get("search_params", {}).get("sort_by", "N/A")
            print(f"✓ Found {hotels_count} hotel rates (sorted by price, top 5 requested)")
            print(f"  Sort method: {sort_by}")
            
            # Show raw output
            print("\n  📋 RAW OUTPUT:")
            print("  " + "=" * 58)
            import json
            print(json.dumps(result, indent=2, ensure_ascii=False))
            print("  " + "=" * 58)
            
            if hotels_count > 0:
                # Extract prices and verify sorting
                prices = []
                for hotel in hotels:
                    price = None
                    # Try to extract price from roomTypes
                    if "roomTypes" in hotel and isinstance(hotel["roomTypes"], list):
                        for room_type in hotel["roomTypes"]:
                            # Try offerRetailRate.amount first
                            if "offerRetailRate" in room_type and "amount" in room_type["offerRetailRate"]:
                                price = float(room_type["offerRetailRate"]["amount"])
                                break
                            # Try rates array
                            if "rates" in room_type and isinstance(room_type["rates"], list):
                                for rate in room_type["rates"]:
                                    if "retailRate" in rate and "total" in rate["retailRate"]:
                                        if isinstance(rate["retailRate"]["total"], list) and len(rate["retailRate"]["total"]) > 0:
                                            if "amount" in rate["retailRate"]["total"][0]:
                                                price = float(rate["retailRate"]["total"][0]["amount"])
                                                break
                                if price:
                                    break
                    prices.append(price if price is not None else float('inf'))
                
                # Verify prices are sorted (ascending)
                if len(prices) > 1:
                    is_sorted = all(prices[i] <= prices[i+1] for i in range(len(prices)-1))
                    if is_sorted:
                        print(f"\n  ✓ Prices are correctly sorted (lowest to highest)")
                        print(f"    Price range: ${prices[0]:.2f} - ${prices[-1]:.2f} USD")
                        print(f"    Prices: {[f'${p:.2f}' for p in prices if p != float('inf')]}")
                    else:
                        print(f"\n  ✗ ERROR: Prices are NOT sorted correctly!")
                        print(f"    Prices: {[f'${p:.2f}' for p in prices if p != float('inf')]}")
                elif len(prices) == 1:
                    print(f"\n  ✓ Single hotel found with price: ${prices[0]:.2f} USD" if prices[0] != float('inf') else "  (Price not available)")
        else:
            print(f"✗ Error: {result.get('error_message')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 5: get_hotel_details
        print("\n5. Testing get_hotel_details (by hotel ID)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_details",
            hotel_id="lp1897"
        )
        if not result.get("error"):
            hotel = result.get("hotel")
            if hotel:
                hotel_name = hotel.get("name", "N/A")
                hotel_id = hotel.get("id", "N/A")
                rating = hotel.get("rating", "N/A")
                print(f"✓ Found hotel details: {hotel_name} (ID: {hotel_id})")
                print(f"  Rating: {rating}")
                if "hotelImages" in hotel and len(hotel["hotelImages"]) > 0:
                    print(f"  Images: {len(hotel['hotelImages'])} available")
                if "rooms" in hotel:
                    print(f"  Room types: {len(hotel['rooms'])} available")
            else:
                print("✗ No hotel data returned")
        else:
            print(f"✗ Error: {result.get('error_message')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 5.5: get_hotel_details with language
        print("\n5.5. Testing get_hotel_details (with language parameter)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_details",
            hotel_id="lp1897",
            language="en"
        )
        if not result.get("error"):
            hotel = result.get("hotel")
            if hotel:
                hotel_name = hotel.get("name", "N/A")
                print(f"✓ Found hotel details with language: {hotel_name}")
            else:
                print("✗ No hotel data returned")
        else:
            print(f"✗ Error: {result.get('error_message')}")
        
        # Test error handling
        print("\n" + "=" * 60)
        print("Testing Error Handling")
        print("=" * 60)
        
        # Test 6: Validation error - missing location
        print("\n6. Testing validation error (missing location identifier)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_rates",
            checkin="2025-12-10",
            checkout="2025-12-17",
            occupancies=[{"adults": 2}]
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 7: Validation error - invalid date format
        print("\n7. Testing validation error (invalid date format)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_rates",
            checkin="2025/12/10",
            checkout="2025-12-17",
            occupancies=[{"adults": 2}],
            city_name="Paris",
            country_code="FR"
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 8: Validation error - checkout before checkin
        print("\n8. Testing validation error (checkout before checkin)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_rates",
            checkin="2025-12-17",
            checkout="2025-12-10",
            occupancies=[{"adults": 2}],
            city_name="Paris",
            country_code="FR"
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 9: Validation error - city without country
        print("\n9. Testing validation error (city without country)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_rates",
            checkin="2025-12-10",
            checkout="2025-12-17",
            occupancies=[{"adults": 2}],
            city_name="Paris"
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 10: Validation error - invalid occupancy
        print("\n10. Testing validation error (invalid occupancy - no adults)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_rates",
            checkin="2025-12-10",
            checkout="2025-12-17",
            occupancies=[{}],
            city_name="Paris",
            country_code="FR"
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 11: Validation error - invalid k parameter (k=0)
        print("\n11. Testing validation error (invalid k parameter - k=0)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_rates",
            checkin="2025-12-10",
            checkout="2025-12-17",
            occupancies=[{"adults": 2}],
            city_name="Paris",
            country_code="FR",
            k=0
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 12: Validation error - invalid k parameter (k too large)
        print("\n12. Testing validation error (invalid k parameter - k=300)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_rates",
            checkin="2025-12-10",
            checkout="2025-12-17",
            occupancies=[{"adults": 2}],
            city_name="Paris",
            country_code="FR",
            k=300
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 13: Validation error - get_hotel_rates_by_price with k=0
        print("\n13. Testing get_hotel_rates_by_price validation error (k=0)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_rates_by_price",
            checkin="2025-12-10",
            checkout="2025-12-17",
            occupancies=[{"adults": 2}],
            city_name="Paris",
            country_code="FR",
            k=0
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 14: Validation error - get_hotel_rates_by_price with k too large
        print("\n14. Testing get_hotel_rates_by_price validation error (k=300)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_rates_by_price",
            checkin="2025-12-10",
            checkout="2025-12-17",
            occupancies=[{"adults": 2}],
            city_name="Paris",
            country_code="FR",
            k=300
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 15: Validation error - get_hotel_details with empty hotel_id
        print("\n15. Testing get_hotel_details validation error (empty hotel_id)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_details",
            hotel_id=""
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 16: Validation error - get_hotel_details with invalid timeout
        print("\n16. Testing get_hotel_details validation error (invalid timeout - negative)...")
        result = await HotelAgentClient.call_tool(
            "get_hotel_details",
            hotel_id="lp1897",
            timeout=-1.0
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
    except Exception as e:
        print(f"\n✗ Error testing Hotel Agent: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        await HotelAgentClient.close()
    
    print("\n" + "=" * 60)
    print("Hotel Agent Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_hotel_agent())

