"""Test script for TripAdvisor Agent Client."""

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

from clients.tripadvisor_agent_client import TripAdvisorAgentClient


async def test_tripadvisor_agent():
    """Test TripAdvisor Agent Client."""
    print("=" * 60)
    print("Testing TripAdvisor Agent Client")
    print("=" * 60)
    
    try:
        # List tools
        tripadvisor_tools = await TripAdvisorAgentClient.list_tools()
        print(f"\n✓ Available tools: {[t['name'] for t in tripadvisor_tools]}")
        
        # Display tool descriptions
        print("\n📋 Tool Descriptions:")
        print("-" * 60)
        for tool in tripadvisor_tools:
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
        
        # Test 1: Search locations by query
        print("\n1. Testing search_locations (by query)...")
        result = await TripAdvisorAgentClient.call_tool(
            "search_locations",
            search_query="Eiffel Tower"
        )
        if not result.get("error"):
            locations_count = len(result.get("data", []))
            print(f"✓ Found {locations_count} locations")
            if locations_count > 0:
                first_location = result['data'][0] if isinstance(result['data'], list) else {}
                # Try multiple possible field names for location ID
                location_id = (first_location.get('locationId') or 
                             first_location.get('id') or 
                             first_location.get('location_id') or 
                             'N/A')
                location_name = first_location.get('name', 'N/A')
                print(f"  First location: {location_name} (ID: {location_id})")
                # Debug: show available keys if ID is N/A
                if location_id == 'N/A' and first_location:
                    print(f"    (Available fields: {list(first_location.keys())[:5]}...)")
        else:
            error_msg = result.get('error_message') or result.get('error') or "Unknown error"
            print(f"✗ Error: {error_msg}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 2: Search locations with category filter
        print("\n2. Testing search_locations (with category filter)...")
        result = await TripAdvisorAgentClient.call_tool(
            "search_locations",
            search_query="Paris hotels",
            category="hotels"
        )
        if not result.get("error"):
            locations_count = len(result.get("data", []))
            print(f"✓ Found {locations_count} hotel locations")
        else:
            error_msg = result.get('error_message') or result.get('error') or "Unknown error"
            print(f"✗ Error: {error_msg}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 3: Search locations with coordinates and radius
        print("\n3. Testing search_locations (with coordinates and radius)...")
        result = await TripAdvisorAgentClient.call_tool(
            "search_locations",
            search_query="restaurants",
            lat_long="40.7128,-74.0060",
            radius=5,
            radius_unit="km",
            category="restaurants"
        )
        if not result.get("error"):
            locations_count = len(result.get("data", []))
            print(f"✓ Found {locations_count} restaurant locations near coordinates")
        else:
            error_msg = result.get('error_message') or result.get('error') or "Unknown error"
            print(f"✗ Error: {error_msg}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 4: Get location details (using location ID from test 1)
        print("\n4. Testing get_location_details...")
        # Use a known location ID (Eiffel Tower is typically around 60763)
        result = await TripAdvisorAgentClient.call_tool(
            "get_location_details",
            location_id=60763
        )
        if not result.get("error"):
            location_data = result.get("data", {})
            if location_data:
                location_name = location_data.get("name", "N/A")
                # Try multiple possible field names for location ID
                location_id = (location_data.get("locationId") or 
                             location_data.get("id") or 
                             location_data.get("location_id") or 
                             "N/A")
                # Try multiple possible field names for rating
                rating = (location_data.get("rating") or 
                         location_data.get("ratingValue") or 
                         location_data.get("averageRating") or 
                         "N/A")
                print(f"✓ Found location details: {location_name} (ID: {location_id})")
                print(f"  Rating: {rating}")
                if "address" in location_data:
                    address = location_data.get('address', {})
                    if isinstance(address, dict):
                        address_str = address.get('addressString') or address.get('street1') or str(address)
                    else:
                        address_str = str(address)
                    print(f"  Address: {address_str}")
                
                # Display URLs
                print(f"\n  📎 URLs:")
                if "webUrl" in location_data:
                    print(f"    TripAdvisor: {location_data.get('webUrl')}")
                elif "url" in location_data:
                    print(f"    TripAdvisor: {location_data.get('url')}")
                if "website" in location_data:
                    website = location_data.get("website")
                    if isinstance(website, str):
                        print(f"    Website: {website}")
                    elif isinstance(website, dict) and "url" in website:
                        print(f"    Website: {website.get('url')}")
            else:
                print("✗ No location data returned")
        else:
            error_msg = result.get('error_message') or result.get('error') or "Unknown error"
            print(f"✗ Error: {error_msg}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 5: Get location reviews
        print("\n5. Testing get_location_reviews...")
        result = await TripAdvisorAgentClient.call_tool(
            "get_location_reviews",
            location_id=60763,
            limit=3
        )
        if not result.get("error"):
            reviews = result.get("data", [])
            reviews_count = len(reviews)
            print(f"✓ Found {reviews_count} reviews")
            if reviews_count > 0:
                first_review = reviews[0]
                rating = first_review.get("rating", "N/A")
                print(f"  First review rating: {rating}")
        else:
            error_msg = result.get('error_message') or result.get('error') or "Unknown error"
            print(f"✗ Error: {error_msg}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 6: Get location photos
        print("\n6. Testing get_location_photos...")
        result = await TripAdvisorAgentClient.call_tool(
            "get_location_photos",
            location_id=60763,
            limit=3
        )
        if not result.get("error"):
            photos = result.get("data", [])
            photos_count = len(photos)
            print(f"✓ Found {photos_count} photos")
            if photos_count > 0:
                first_photo = photos[0]
                if "images" in first_photo:
                    images = first_photo.get("images", {})
                    print(f"  Photo has {len(images) if isinstance(images, dict) else 0} size variants")
                    
                    # Display photo URLs
                    print(f"\n  📸 Photo URLs:")
                    for i, photo in enumerate(photos[:2], 1):  # Show first 2 photos
                        print(f"\n    Photo {i}:")
                        if "images" in photo:
                            images = photo.get("images", {})
                            if isinstance(images, dict):
                                # Show available sizes
                                for size in ["original", "large", "medium", "small", "thumbnail"]:
                                    if size in images:
                                        print(f"      {size.capitalize()}: {images.get(size)}")
                                        break  # Show first available size
                                else:
                                    # If none of the standard sizes, show first available
                                    for size, url in list(images.items())[:1]:
                                        print(f"      {size}: {url}")
                        elif "url" in photo:
                            print(f"      URL: {photo.get('url')}")
        else:
            error_msg = result.get('error_message') or result.get('error') or "Unknown error"
            print(f"✗ Error: {error_msg}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 7: Search nearby
        print("\n7. Testing search_nearby...")
        result = await TripAdvisorAgentClient.call_tool(
            "search_nearby",
            lat_long="40.7128,-74.0060",
            category="attractions",
            radius=10,
            radius_unit="km"
        )
        if not result.get("error"):
            locations_count = len(result.get("data", []))
            print(f"✓ Found {locations_count} nearby attractions")
        else:
            error_msg = result.get('error_message') or result.get('error') or "Unknown error"
            print(f"✗ Error: {error_msg}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 8: Get location details with language and currency
        print("\n8. Testing get_location_details (with language and currency)...")
        result = await TripAdvisorAgentClient.call_tool(
            "get_location_details",
            location_id=60763,
            language="fr",
            currency="EUR"
        )
        if not result.get("error"):
            location_data = result.get("data", {})
            if location_data:
                location_name = location_data.get("name", "N/A")
                print(f"✓ Found location details with French language: {location_name}")
            else:
                print("✗ No location data returned")
        else:
            error_msg = result.get('error_message') or result.get('error') or "Unknown error"
            print(f"✗ Error: {error_msg}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 9: Search locations by price
        print("\n9. Testing search_locations_by_price...")
        result = await TripAdvisorAgentClient.call_tool(
            "search_locations_by_price",
            search_query="restaurants Paris",
            max_price_level=2,
            category="restaurants"
        )
        if not result.get("error"):
            locations_count = len(result.get("data", []))
            print(f"✓ Found {locations_count} budget-friendly restaurants (price level ≤ 2)")
            if locations_count > 0:
                first = result['data'][0]
                print(f"  First: {first.get('name', 'N/A')}")
        else:
            error_msg = result.get('error_message') or result.get('error') or "Unknown error"
            print(f"✗ Error: {error_msg}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 10: Search nearby by price
        print("\n10. Testing search_nearby_by_price...")
        result = await TripAdvisorAgentClient.call_tool(
            "search_nearby_by_price",
            lat_long="40.7128,-74.0060",
            max_price_level=2,
            category="restaurants",
            radius=5,
            radius_unit="km"
        )
        if not result.get("error"):
            locations_count = len(result.get("data", []))
            print(f"✓ Found {locations_count} budget-friendly restaurants nearby (price level ≤ 2)")
        else:
            error_msg = result.get('error_message') or result.get('error') or "Unknown error"
            print(f"✗ Error: {error_msg}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 11: Search nearby by distance
        print("\n11. Testing search_nearby_by_distance...")
        result = await TripAdvisorAgentClient.call_tool(
            "search_nearby_by_distance",
            lat_long="40.7128,-74.0060",
            category="restaurants",
            radius=5,
            radius_unit="km"
        )
        if not result.get("error"):
            locations_count = len(result.get("data", []))
            print(f"✓ Found {locations_count} restaurants sorted by distance (closest first)")
            if locations_count > 0:
                first = result['data'][0]
                distance = first.get('distance') or first.get('distanceValue', 'N/A')
                print(f"  Closest: {first.get('name', 'N/A')} (distance: {distance})")
        else:
            error_msg = result.get('error_message') or result.get('error') or "Unknown error"
            print(f"✗ Error: {error_msg}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 12: Find closest location
        print("\n12. Testing find_closest_location...")
        result = await TripAdvisorAgentClient.call_tool(
            "find_closest_location",
            lat_long="40.7128,-74.0060",
            category="restaurants",
            radius=5,
            radius_unit="km"
        )
        if not result.get("error"):
            closest = result.get("data", {})
            if closest:
                print(f"✓ Found closest restaurant: {closest.get('name', 'N/A')}")
                distance = closest.get('distance') or closest.get('distanceValue', 'N/A')
                print(f"  Distance: {distance}")
            else:
                print("  No locations found")
        else:
            error_msg = result.get('error_message') or result.get('error') or "Unknown error"
            print(f"✗ Error: {error_msg}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 13: Search restaurants by cuisine
        print("\n13. Testing search_restaurants_by_cuisine...")
        result = await TripAdvisorAgentClient.call_tool(
            "search_restaurants_by_cuisine",
            search_query="restaurants Rome",
            cuisine_types=["Italian"]
        )
        if not result.get("error"):
            locations_count = len(result.get("data", []))
            print(f"✓ Found {locations_count} Italian restaurants")
            if result.get("message"):
                print(f"  Note: {result.get('message')}")
        else:
            error_msg = result.get('error_message') or result.get('error') or "Unknown error"
            print(f"✗ Error: {error_msg}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 14: Get multiple location details
        print("\n14. Testing get_multiple_location_details...")
        result = await TripAdvisorAgentClient.call_tool(
            "get_multiple_location_details",
            location_ids=[60763, 186338]  # Eiffel Tower and another location
        )
        if not result.get("error"):
            locations = result.get("data", [])
            summary = result.get("summary", {})
            print(f"✓ Retrieved details for {summary.get('successful', 0)}/{summary.get('requested', 0)} locations")
            for i, loc in enumerate(locations[:2], 1):
                print(f"  {i}. {loc.get('name', 'N/A')}")
            if result.get("errors"):
                print(f"  Errors: {len(result.get('errors', []))} failed")
        else:
            error_msg = result.get('error_message') or result.get('error') or "Unknown error"
            print(f"✗ Error: {error_msg}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test 15: Compare locations
        print("\n15. Testing compare_locations...")
        result = await TripAdvisorAgentClient.call_tool(
            "compare_locations",
            location_ids=[60763, 186338]  # Compare 2 locations
        )
        if not result.get("error"):
            comparison = result.get("data", {})
            locations = comparison.get("locations", [])
            comp_summary = comparison.get("comparison", {})
            print(f"✓ Compared {len(locations)} locations")
            for i, loc in enumerate(locations, 1):
                print(f"  {i}. {loc.get('name', 'N/A')} - Rating: {loc.get('rating', 'N/A')}, Price: {loc.get('price_level', 'N/A')}")
            if comp_summary:
                if "highest_rated" in comp_summary:
                    print(f"  Highest rated: {comp_summary.get('highest_rated')}")
                if "most_affordable" in comp_summary:
                    print(f"  Most affordable: Price level {comp_summary.get('most_affordable')}")
        else:
            error_msg = result.get('error_message') or result.get('error') or "Unknown error"
            print(f"✗ Error: {error_msg}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        
        # Test end-to-end scenario
        print("\n" + "=" * 60)
        print("End-to-End Scenario Test")
        print("=" * 60)
        
        # Scenario: Find Byblos in Beirut, then get photos, reviews, and nearby restaurants
        print("\n📋 Scenario: Exploring Byblos in Beirut")
        print("-" * 60)
        print("Step 1: Searching for 'Byblos Beirut' location...")
        
        scenario_result = await TripAdvisorAgentClient.call_tool(
            "search_locations",
            search_query="Byblos Beirut",
            category="attractions"
        )
        
        if scenario_result.get("error"):
            print(f"✗ Error searching for location: {scenario_result.get('error_message')}")
        else:
            locations = scenario_result.get("data", [])
            if not locations:
                print("✗ No locations found for 'Byblos Beirut'")
                print("  Trying alternative search...")
                # Try without category
                scenario_result = await TripAdvisorAgentClient.call_tool(
                    "search_locations",
                    search_query="Byblos Lebanon"
                )
                locations = scenario_result.get("data", [])
            
            if locations:
                # Extract location ID from first result
                first_location = locations[0]
                location_id_raw = (first_location.get('locationId') or 
                                 first_location.get('id') or 
                                 first_location.get('location_id'))
                location_name = first_location.get('name', 'Unknown')
                
                # Convert location_id to int if it's a string
                location_id = None
                if location_id_raw is not None:
                    try:
                        location_id = int(location_id_raw)
                    except (ValueError, TypeError):
                        # If conversion fails, try to use as-is (might be string)
                        location_id = location_id_raw
                
                print(f"✓ Found location: {location_name}")
                if location_id:
                    print(f"  Location ID: {location_id} (type: {type(location_id).__name__})")
                    
                    # Show location details
                    if 'address' in first_location:
                        address = first_location.get('address', {})
                        if isinstance(address, dict):
                            address_str = address.get('addressString') or address.get('street1') or str(address)
                        else:
                            address_str = str(address)
                        print(f"  Address: {address_str}")
                    
                    # Get coordinates if available for nearby search
                    lat_long = None
                    if 'latitude' in first_location and 'longitude' in first_location:
                        lat = first_location.get('latitude')
                        lon = first_location.get('longitude')
                        if lat and lon:
                            lat_long = f"{lat},{lon}"
                            print(f"  Coordinates: {lat_long}")
                    elif 'location' in first_location:
                        loc = first_location.get('location', {})
                        if 'latitude' in loc and 'longitude' in loc:
                            lat = loc.get('latitude')
                            lon = loc.get('longitude')
                            if lat and lon:
                                lat_long = f"{lat},{lon}"
                                print(f"  Coordinates: {lat_long}")
                    
                    print("\n" + "-" * 60)
                    print("Step 2: Getting location details...")
                    details_result = await TripAdvisorAgentClient.call_tool(
                        "get_location_details",
                        location_id=location_id,
                        language="en"
                    )
                    
                    if not details_result.get("error"):
                        details = details_result.get("data", {})
                        if details:
                            print(f"✓ Location details retrieved")
                            rating = (details.get("rating") or 
                                     details.get("ratingValue") or 
                                     details.get("averageRating") or 
                                     "N/A")
                            print(f"  Rating: {rating}")
                            if "ranking" in details:
                                print(f"  Ranking: {details.get('ranking', 'N/A')}")
                            
                            # Display URLs
                            print(f"\n  📎 URLs:")
                            urls_found = False
                            
                            # TripAdvisor URL
                            if "webUrl" in details:
                                print(f"    TripAdvisor: {details.get('webUrl')}")
                                urls_found = True
                            elif "url" in details:
                                print(f"    TripAdvisor: {details.get('url')}")
                                urls_found = True
                            
                            # Website URL
                            if "website" in details:
                                website = details.get("website")
                                if isinstance(website, str):
                                    print(f"    Website: {website}")
                                    urls_found = True
                                elif isinstance(website, dict) and "url" in website:
                                    print(f"    Website: {website.get('url')}")
                                    urls_found = True
                            
                            # Additional URLs in various formats
                            if "urls" in details and isinstance(details["urls"], dict):
                                for url_type, url_value in details["urls"].items():
                                    if url_value:
                                        print(f"    {url_type}: {url_value}")
                                        urls_found = True
                            
                            if not urls_found:
                                print(f"    (No URLs found in response)")
                    else:
                        print(f"⚠ Could not get details: {details_result.get('error_message')}")
                    
                    print("\n" + "-" * 60)
                    print("Step 3: Getting photos for this location...")
                    photos_result = await TripAdvisorAgentClient.call_tool(
                        "get_location_photos",
                        location_id=location_id,
                        limit=5
                    )
                    
                    if not photos_result.get("error"):
                        photos = photos_result.get("data", [])
                        print(f"✓ Found {len(photos)} photos")
                        if photos:
                            first_photo = photos[0]
                            if "images" in first_photo:
                                images = first_photo.get("images", {})
                                print(f"  Photo sizes available: {', '.join(images.keys()) if isinstance(images, dict) else 'Multiple'}")
                            if "caption" in first_photo:
                                caption = first_photo.get("caption", "")[:50]
                                if caption:
                                    print(f"  First photo caption: {caption}...")
                            
                            # Display photo URLs
                            print(f"\n  📸 Photo URLs:")
                            for i, photo in enumerate(photos[:3], 1):  # Show first 3 photos
                                print(f"\n    Photo {i}:")
                                if "images" in photo:
                                    images = photo.get("images", {})
                                    if isinstance(images, dict):
                                        # Show different size URLs
                                        if "original" in images:
                                            print(f"      Original: {images.get('original')}")
                                        elif "large" in images:
                                            print(f"      Large: {images.get('large')}")
                                        elif "medium" in images:
                                            print(f"      Medium: {images.get('medium')}")
                                        elif "small" in images:
                                            print(f"      Small: {images.get('small')}")
                                        elif "thumbnail" in images:
                                            print(f"      Thumbnail: {images.get('thumbnail')}")
                                        else:
                                            # Show all available sizes
                                            for size, url in list(images.items())[:3]:
                                                print(f"      {size}: {url}")
                                elif "url" in photo:
                                    print(f"      URL: {photo.get('url')}")
                                elif "imageUrl" in photo:
                                    print(f"      URL: {photo.get('imageUrl')}")
                    else:
                        print(f"⚠ Could not get photos: {photos_result.get('error_message')}")
                    
                    print("\n" + "-" * 60)
                    print("Step 4: Getting reviews for this location...")
                    reviews_result = await TripAdvisorAgentClient.call_tool(
                        "get_location_reviews",
                        location_id=location_id,
                        limit=5
                    )
                    
                    if not reviews_result.get("error"):
                        reviews = reviews_result.get("data", [])
                        print(f"✓ Found {len(reviews)} reviews")
                        if reviews:
                            for i, review in enumerate(reviews[:3], 1):
                                rating = review.get("rating", "N/A")
                                title = review.get("title", "No title")[:40]
                                print(f"  Review {i}: Rating {rating} - {title}...")
                            
                            # Display review URLs
                            print(f"\n  📝 Review URLs:")
                            for i, review in enumerate(reviews[:3], 1):
                                if "url" in review:
                                    print(f"    Review {i}: {review.get('url')}")
                                elif "reviewUrl" in review:
                                    print(f"    Review {i}: {review.get('reviewUrl')}")
                                elif "webUrl" in review:
                                    print(f"    Review {i}: {review.get('webUrl')}")
                    else:
                        print(f"⚠ Could not get reviews: {reviews_result.get('error_message')}")
                    
                    print("\n" + "-" * 60)
                    print("Step 5: Searching for nearby restaurants...")
                    
                    if lat_long:
                        nearby_result = await TripAdvisorAgentClient.call_tool(
                            "search_nearby",
                            lat_long=lat_long,
                            category="restaurants",
                            radius=5,
                            radius_unit="km"
                        )
                        
                        if not nearby_result.get("error"):
                            nearby_restaurants = nearby_result.get("data", [])
                            print(f"✓ Found {len(nearby_restaurants)} nearby restaurants")
                            if nearby_restaurants:
                                print("  Top restaurants:")
                                for i, restaurant in enumerate(nearby_restaurants[:5], 1):
                                    name = restaurant.get("name", "Unknown")
                                    rating = (restaurant.get("rating") or 
                                            restaurant.get("ratingValue") or 
                                            "N/A")
                                    print(f"    {i}. {name} (Rating: {rating})")
                                
                                # Display restaurant URLs
                                print(f"\n  🍽️ Restaurant URLs:")
                                for i, restaurant in enumerate(nearby_restaurants[:5], 1):
                                    name = restaurant.get("name", f"Restaurant {i}")
                                    if "webUrl" in restaurant:
                                        print(f"    {i}. {name}: {restaurant.get('webUrl')}")
                                    elif "url" in restaurant:
                                        print(f"    {i}. {name}: {restaurant.get('url')}")
                                    elif "locationId" in restaurant or "id" in restaurant:
                                        rest_id = restaurant.get("locationId") or restaurant.get("id")
                                        if rest_id:
                                            print(f"    {i}. {name}: https://www.tripadvisor.com/Attraction_Review?lgr={rest_id}")
                        else:
                            print(f"⚠ Could not find nearby restaurants: {nearby_result.get('error_message')}")
                    else:
                        # Fallback: search for restaurants in Beirut
                        print("  (Coordinates not available, searching for restaurants in Beirut instead)")
                        nearby_result = await TripAdvisorAgentClient.call_tool(
                            "search_locations",
                            search_query="restaurants Beirut",
                            category="restaurants"
                        )
                        
                        if not nearby_result.get("error"):
                            restaurants = nearby_result.get("data", [])
                            print(f"✓ Found {len(restaurants)} restaurants in Beirut")
                            if restaurants:
                                print("  Top restaurants:")
                                for i, restaurant in enumerate(restaurants[:5], 1):
                                    name = restaurant.get("name", "Unknown")
                                    rating = (restaurant.get("rating") or 
                                            restaurant.get("ratingValue") or 
                                            "N/A")
                                    print(f"    {i}. {name} (Rating: {rating})")
                                
                                # Display restaurant URLs
                                print(f"\n  🍽️ Restaurant URLs:")
                                for i, restaurant in enumerate(restaurants[:5], 1):
                                    name = restaurant.get("name", f"Restaurant {i}")
                                    if "webUrl" in restaurant:
                                        print(f"    {i}. {name}: {restaurant.get('webUrl')}")
                                    elif "url" in restaurant:
                                        print(f"    {i}. {name}: {restaurant.get('url')}")
                                    elif "locationId" in restaurant or "id" in restaurant:
                                        rest_id = restaurant.get("locationId") or restaurant.get("id")
                                        if rest_id:
                                            print(f"    {i}. {name}: https://www.tripadvisor.com/Restaurant_Review?lgr={rest_id}")
                        else:
                            print(f"⚠ Could not find restaurants: {nearby_result.get('error_message')}")
                    
                    print("\n" + "=" * 60)
                    print("✅ End-to-End Scenario Complete!")
                    print("=" * 60)
                    print("\nSummary:")
                    print(f"  • Location: {location_name}")
                    print(f"  • Location ID: {location_id}")
                    print(f"  • Photos retrieved: {len(photos_result.get('data', [])) if not photos_result.get('error') else 0}")
                    print(f"  • Reviews retrieved: {len(reviews_result.get('data', [])) if not reviews_result.get('error') else 0}")
                    if lat_long:
                        print(f"  • Nearby restaurants found: {len(nearby_result.get('data', [])) if not nearby_result.get('error') else 0}")
                    else:
                        print(f"  • Restaurants in area found: {len(nearby_result.get('data', [])) if not nearby_result.get('error') else 0}")
                else:
                    print("✗ Could not extract location ID from search results")
                    print(f"  Available fields: {list(first_location.keys())[:10]}")
            else:
                    print("✗ No locations found for the search query")
        
        # Test second end-to-end scenario: Napoli Pizzeria
        print("\n" + "=" * 60)
        print("End-to-End Scenario Test 2: Napoli Pizzeria")
        print("=" * 60)
        
        # Scenario: Find pizzerias in Napoli, get details, photos, reviews, and nearby attractions
        print("\n📋 Scenario: Exploring Pizzerias in Napoli, Italy")
        print("-" * 60)
        print("Step 1: Searching for pizzerias in Napoli (user-friendly text search)...")
        
        # User-friendly approach: search by text query (like a real user would)
        scenario2_result = await TripAdvisorAgentClient.call_tool(
            "search_locations",
            search_query="pizzeria Napoli",
            category="restaurants",
            language="en"
        )
        
        if scenario2_result.get("error"):
            print(f"✗ Error searching: {scenario2_result.get('error_message')}")
            print("  Trying alternative search...")
            # Fallback: try without category filter
            scenario2_result = await TripAdvisorAgentClient.call_tool(
                "search_locations",
                search_query="pizza Napoli Italy"
            )
        
        if not scenario2_result.get("error"):
            restaurants = scenario2_result.get("data", [])
            print(f"✓ Found {len(restaurants)} restaurants")
            
            if restaurants:
                # Find a pizzeria (look for "pizza" or "pizzeria" in name)
                pizzeria = None
                for restaurant in restaurants:
                    name_lower = restaurant.get("name", "").lower()
                    if "pizza" in name_lower or "pizzeria" in name_lower:
                        pizzeria = restaurant
                        break
                
                # If no pizzeria found, use first restaurant
                if not pizzeria:
                    pizzeria = restaurants[0]
                    print(f"  (No pizzeria found in results, using first restaurant)")
                
                location_name = pizzeria.get("name", "Unknown")
                location_id_raw = (pizzeria.get('locationId') or 
                                 pizzeria.get('id') or 
                                 pizzeria.get('location_id'))
                
                # Convert location_id to int if it's a string
                location_id = None
                if location_id_raw is not None:
                    try:
                        location_id = int(location_id_raw)
                    except (ValueError, TypeError):
                        location_id = location_id_raw
                
                print(f"\n✓ Selected location: {location_name}")
                if location_id:
                    print(f"  Location ID: {location_id} (type: {type(location_id).__name__})")
                
                # Show address if available
                if 'address' in pizzeria:
                    address = pizzeria.get('address', {})
                    if isinstance(address, dict):
                        address_str = (address.get('addressString') or 
                                     address.get('street1') or 
                                     address.get('street') or
                                     str(address))
                    else:
                        address_str = str(address)
                    if address_str and address_str != "{}":
                        print(f"  Address: {address_str}")
                
                # Get coordinates
                lat_long_pizzeria = None
                if 'latitude' in pizzeria and 'longitude' in pizzeria:
                    lat = pizzeria.get('latitude')
                    lon = pizzeria.get('longitude')
                    if lat and lon:
                        lat_long_pizzeria = f"{lat},{lon}"
                        print(f"  Coordinates: {lat_long_pizzeria}")
                elif 'location' in pizzeria:
                    loc = pizzeria.get('location', {})
                    if 'latitude' in loc and 'longitude' in loc:
                        lat = loc.get('latitude')
                        lon = loc.get('longitude')
                        if lat and lon:
                            lat_long_pizzeria = f"{lat},{lon}"
                            print(f"  Coordinates: {lat_long_pizzeria}")
                
                # Show rating if available
                rating = (pizzeria.get("rating") or 
                         pizzeria.get("ratingValue") or 
                         pizzeria.get("averageRating") or 
                         "N/A")
                if rating != "N/A":
                    print(f"  Rating: {rating}")
                
                # Show URL if available
                if "webUrl" in pizzeria:
                    print(f"  URL: {pizzeria.get('webUrl')}")
                elif "url" in pizzeria:
                    print(f"  URL: {pizzeria.get('url')}")
                
                if location_id:
                    print("\n" + "-" * 60)
                    print("Step 2: Getting full location details...")
                    details2_result = await TripAdvisorAgentClient.call_tool(
                        "get_location_details",
                        location_id=location_id,
                        language="en",
                        currency="EUR"
                    )
                    
                    if not details2_result.get("error"):
                        details2 = details2_result.get("data", {})
                        if details2:
                            print(f"✓ Location details retrieved")
                            rating2 = (details2.get("rating") or 
                                      details2.get("ratingValue") or 
                                      details2.get("averageRating") or 
                                      "N/A")
                            print(f"  Rating: {rating2}")
                            
                            # Show address if available
                            if "address" in details2:
                                address2 = details2.get('address', {})
                                if isinstance(address2, dict):
                                    address_str2 = (address2.get('addressString') or 
                                                   address2.get('street1') or 
                                                   address2.get('street') or
                                                   str(address2))
                                else:
                                    address_str2 = str(address2)
                                if address_str2 and address_str2 != "{}":
                                    print(f"  Address: {address_str2}")
                            
                            if "ranking" in details2:
                                ranking = details2.get("ranking", {})
                                if isinstance(ranking, dict):
                                    rank_str = ranking.get("ranking_string", ranking.get("rank", "N/A"))
                                    if rank_str != "N/A":
                                        print(f"  Ranking: {rank_str}")
                                elif ranking:
                                    print(f"  Ranking: {ranking}")
                            
                            # Show cuisine type if available
                            if "cuisine" in details2:
                                cuisine = details2.get("cuisine", [])
                                if isinstance(cuisine, list) and cuisine:
                                    # Handle list of strings or list of dicts
                                    cuisine_strs = []
                                    for item in cuisine[:3]:
                                        if isinstance(item, str):
                                            cuisine_strs.append(item)
                                        elif isinstance(item, dict):
                                            # Extract name or value from dict
                                            name = item.get("name") or item.get("value") or str(item)
                                            cuisine_strs.append(name)
                                        else:
                                            cuisine_strs.append(str(item))
                                    if cuisine_strs:
                                        print(f"  Cuisine: {', '.join(cuisine_strs)}")
                                elif isinstance(cuisine, str):
                                    print(f"  Cuisine: {cuisine}")
                            
                            # Show price level if available
                            if "priceLevel" in details2:
                                price_level = details2.get('priceLevel')
                                if price_level:
                                    print(f"  Price Level: {price_level}")
                            
                            # Show phone if available
                            if "phone" in details2:
                                phone2 = details2.get("phone")
                                if phone2:
                                    print(f"  Phone: {phone2}")
                            
                            # Show hours if available
                            if "hours" in details2:
                                hours = details2.get("hours")
                                if hours:
                                    if isinstance(hours, dict) and "weekday_text" in hours:
                                        print(f"  Hours: {hours.get('weekday_text', [])[0] if hours.get('weekday_text') else 'N/A'}")
                                    elif isinstance(hours, str):
                                        print(f"  Hours: {hours}")
                            
                            # Display URLs
                            print(f"\n  📎 URLs:")
                            urls_found2 = False
                            
                            if "webUrl" in details2:
                                print(f"    TripAdvisor: {details2.get('webUrl')}")
                                urls_found2 = True
                            elif "url" in details2:
                                print(f"    TripAdvisor: {details2.get('url')}")
                                urls_found2 = True
                            
                            if "website" in details2:
                                website = details2.get("website")
                                if isinstance(website, str):
                                    print(f"    Website: {website}")
                                    urls_found2 = True
                                elif isinstance(website, dict) and "url" in website:
                                    print(f"    Website: {website.get('url')}")
                                    urls_found2 = True
                            
                            if "urls" in details2 and isinstance(details2["urls"], dict):
                                for url_type, url_value in details2["urls"].items():
                                    if url_value:
                                        print(f"    {url_type}: {url_value}")
                                        urls_found2 = True
                            
                            if not urls_found2:
                                print(f"    (No URLs found in response)")
                    else:
                        print(f"⚠ Could not get details: {details2_result.get('error_message')}")
                    
                    print("\n" + "-" * 60)
                    print("Step 3: Getting photos for this pizzeria...")
                    photos2_result = await TripAdvisorAgentClient.call_tool(
                        "get_location_photos",
                        location_id=location_id,
                        limit=5,
                        source="Traveler"
                    )
                    
                    if not photos2_result.get("error"):
                        photos2 = photos2_result.get("data", [])
                        print(f"✓ Found {len(photos2)} photos")
                        if photos2:
                            first_photo2 = photos2[0]
                            if "images" in first_photo2:
                                images2 = first_photo2.get("images", {})
                                print(f"  Photo sizes available: {', '.join(images2.keys()) if isinstance(images2, dict) else 'Multiple'}")
                            if "caption" in first_photo2:
                                caption2 = first_photo2.get("caption", "")[:50]
                                if caption2:
                                    print(f"  First photo caption: {caption2}...")
                            
                            # Display photo URLs
                            print(f"\n  📸 Photo URLs:")
                            for i, photo in enumerate(photos2[:3], 1):
                                print(f"\n    Photo {i}:")
                                if "images" in photo:
                                    images = photo.get("images", {})
                                    if isinstance(images, dict):
                                        # Show different size URLs in priority order
                                        if "original" in images:
                                            print(f"      Original: {images.get('original')}")
                                        elif "large" in images:
                                            print(f"      Large: {images.get('large')}")
                                        elif "medium" in images:
                                            print(f"      Medium: {images.get('medium')}")
                                        elif "small" in images:
                                            print(f"      Small: {images.get('small')}")
                                        elif "thumbnail" in images:
                                            print(f"      Thumbnail: {images.get('thumbnail')}")
                                        else:
                                            # Show all available sizes
                                            for size, url in list(images.items())[:3]:
                                                print(f"      {size}: {url}")
                                elif "url" in photo:
                                    print(f"      URL: {photo.get('url')}")
                                elif "imageUrl" in photo:
                                    print(f"      URL: {photo.get('imageUrl')}")
                    else:
                        print(f"⚠ Could not get photos: {photos2_result.get('error_message')}")
                    
                    print("\n" + "-" * 60)
                    print("Step 4: Getting reviews for this pizzeria...")
                    reviews2_result = await TripAdvisorAgentClient.call_tool(
                        "get_location_reviews",
                        location_id=location_id,
                        limit=5,
                        language="en"
                    )
                    
                    if not reviews2_result.get("error"):
                        reviews2 = reviews2_result.get("data", [])
                        print(f"✓ Found {len(reviews2)} reviews")
                        if reviews2:
                            print("\n  📝 Reviews:")
                            for i, review in enumerate(reviews2[:5], 1):
                                rating_review = review.get("rating", "N/A")
                                title = review.get("title", "No title")
                                text = review.get("text", "")
                                author = review.get("username", review.get("author", "Anonymous"))
                                date = review.get("publishedDate", review.get("date", "N/A"))
                                
                                print(f"\n    Review {i}:")
                                print(f"      Rating: {rating_review}/5")
                                print(f"      Title: {title}")
                                if text:
                                    text_preview = text[:100] + "..." if len(text) > 100 else text
                                    print(f"      Text: {text_preview}")
                                print(f"      Author: {author}")
                                print(f"      Date: {date}")
                            
                            # Display review URLs
                            print(f"\n  📝 Review URLs:")
                            for i, review in enumerate(reviews2[:3], 1):
                                if "url" in review:
                                    print(f"    Review {i}: {review.get('url')}")
                                elif "reviewUrl" in review:
                                    print(f"    Review {i}: {review.get('reviewUrl')}")
                                elif "webUrl" in review:
                                    print(f"    Review {i}: {review.get('webUrl')}")
                    else:
                        print(f"⚠ Could not get reviews: {reviews2_result.get('error_message')}")
                    
                    print("\n" + "-" * 60)
                    print("Step 5: Searching for nearby attractions in Napoli...")
                    
                    if lat_long_pizzeria:
                        # Use pizzeria coordinates if available
                        nearby_attractions_result = await TripAdvisorAgentClient.call_tool(
                            "search_nearby",
                            lat_long=lat_long_pizzeria,
                            category="attractions",
                            radius=3,
                            radius_unit="km"
                        )
                    else:
                        # Fallback: search attractions by text query
                        print("  (Coordinates not available, searching attractions by text query)")
                        nearby_attractions_result = await TripAdvisorAgentClient.call_tool(
                            "search_locations",
                            search_query="attractions Napoli",
                            category="attractions"
                        )
                    
                    if not nearby_attractions_result.get("error"):
                        attractions = nearby_attractions_result.get("data", [])
                        print(f"✓ Found {len(attractions)} nearby attractions")
                        if attractions:
                            print("  Top attractions:")
                            for i, attraction in enumerate(attractions[:5], 1):
                                name = attraction.get("name", "Unknown")
                                rating = (attraction.get("rating") or 
                                         attraction.get("ratingValue") or 
                                         "N/A")
                                print(f"    {i}. {name} (Rating: {rating})")
                            
                            # Display attraction URLs
                            print(f"\n  🏛️ Attraction URLs:")
                            for i, attraction in enumerate(attractions[:5], 1):
                                name = attraction.get("name", f"Attraction {i}")
                                if "webUrl" in attraction:
                                    print(f"    {i}. {name}: {attraction.get('webUrl')}")
                                elif "url" in attraction:
                                    print(f"    {i}. {name}: {attraction.get('url')}")
                                elif "locationId" in attraction or "id" in attraction:
                                    att_id = attraction.get("locationId") or attraction.get("id")
                                    if att_id:
                                        print(f"    {i}. {name}: https://www.tripadvisor.com/Attraction_Review?lgr={att_id}")
                    else:
                        print(f"⚠ Could not find nearby attractions: {nearby_attractions_result.get('error_message')}")
                    
                    print("\n" + "-" * 60)
                    print("Step 6: Searching for more restaurants in Napoli area...")
                    
                    # Use search_locations to find more pizzerias
                    more_restaurants_result = await TripAdvisorAgentClient.call_tool(
                        "search_locations",
                        search_query="pizzeria Napoli Italy",
                        category="restaurants",
                        language="en"
                    )
                    
                    if not more_restaurants_result.get("error"):
                        more_restaurants = more_restaurants_result.get("data", [])
                        print(f"✓ Found {len(more_restaurants)} pizzerias in Napoli")
                        if more_restaurants:
                            print("  Additional pizzerias:")
                            for i, restaurant in enumerate(more_restaurants[:5], 1):
                                name = restaurant.get("name", "Unknown")
                                rating = (restaurant.get("rating") or 
                                         restaurant.get("ratingValue") or 
                                         "N/A")
                                print(f"    {i}. {name} (Rating: {rating})")
                            
                            # Display restaurant URLs
                            print(f"\n  🍕 Pizzeria URLs:")
                            for i, restaurant in enumerate(more_restaurants[:5], 1):
                                name = restaurant.get("name", f"Pizzeria {i}")
                                if "webUrl" in restaurant:
                                    print(f"    {i}. {name}: {restaurant.get('webUrl')}")
                                elif "url" in restaurant:
                                    print(f"    {i}. {name}: {restaurant.get('url')}")
                                elif "locationId" in restaurant or "id" in restaurant:
                                    rest_id = restaurant.get("locationId") or restaurant.get("id")
                                    if rest_id:
                                        print(f"    {i}. {name}: https://www.tripadvisor.com/Restaurant_Review?lgr={rest_id}")
                    else:
                        print(f"⚠ Could not find more restaurants: {more_restaurants_result.get('error_message')}")
                    
                    print("\n" + "=" * 60)
                    print("✅ Napoli Pizzeria Scenario Complete!")
                    print("=" * 60)
                    print("\nSummary:")
                    print(f"  • Selected Pizzeria: {location_name}")
                    print(f"  • Location ID: {location_id}")
                    print(f"  • Details retrieved: {'Yes' if not details2_result.get('error') else 'No'}")
                    print(f"  • Photos retrieved: {len(photos2_result.get('data', [])) if not photos2_result.get('error') else 0}")
                    print(f"  • Reviews retrieved: {len(reviews2_result.get('data', [])) if not reviews2_result.get('error') else 0}")
                    print(f"  • Nearby attractions found: {len(nearby_attractions_result.get('data', [])) if not nearby_attractions_result.get('error') else 0}")
                    print(f"  • Additional pizzerias found: {len(more_restaurants_result.get('data', [])) if not more_restaurants_result.get('error') else 0}")
                    print(f"\n  🎯 All 5 tools used:")
                    print(f"    1. ✓ search_locations (find pizzerias in Napoli - user-friendly text search)")
                    print(f"    2. ✓ get_location_details (get pizzeria details)")
                    print(f"    3. ✓ get_location_photos (get pizzeria photos)")
                    print(f"    4. ✓ get_location_reviews (get pizzeria reviews)")
                    print(f"    5. ✓ search_nearby/search_locations (find nearby attractions and more pizzerias)")
                else:
                    print("✗ Could not extract location ID from search results")
            else:
                print("✗ No restaurants found")
        else:
            print(f"✗ Error in initial search: {scenario2_result.get('error_message')}")
        
        # Test error handling
        print("\n" + "=" * 60)
        print("Testing Error Handling")
        print("=" * 60)
        
        # Test 9: Validation error - empty search query
        print("\n9. Testing validation error (empty search query)...")
        result = await TripAdvisorAgentClient.call_tool(
            "search_locations",
            search_query=""
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
            if result.get("suggestion"):
                print(f"  Suggestion: {result.get('suggestion')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 10: Validation error - invalid category
        print("\n10. Testing validation error (invalid category)...")
        result = await TripAdvisorAgentClient.call_tool(
            "search_locations",
            search_query="Paris",
            category="invalid_category"
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 11: Validation error - invalid lat_long format
        print("\n11. Testing validation error (invalid lat_long format)...")
        result = await TripAdvisorAgentClient.call_tool(
            "search_locations",
            search_query="Paris",
            lat_long="invalid"
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 12: Validation error - invalid location_id
        print("\n12. Testing validation error (invalid location_id - negative)...")
        result = await TripAdvisorAgentClient.call_tool(
            "get_location_details",
            location_id=-1
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 13: Validation error - invalid limit (too high)
        print("\n13. Testing validation error (invalid limit - too high for reviews)...")
        result = await TripAdvisorAgentClient.call_tool(
            "get_location_reviews",
            location_id=60763,
            limit=10
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 14: Validation error - invalid offset (negative)
        print("\n14. Testing validation error (invalid offset - negative)...")
        result = await TripAdvisorAgentClient.call_tool(
            "get_location_reviews",
            location_id=60763,
            offset=-1
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 15: Validation error - missing lat_long for search_nearby
        print("\n15. Testing validation error (missing lat_long for search_nearby)...")
        result = await TripAdvisorAgentClient.call_tool(
            "search_nearby",
            lat_long=""
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 16: Validation error - invalid radius unit
        print("\n16. Testing validation error (invalid radius unit)...")
        result = await TripAdvisorAgentClient.call_tool(
            "search_nearby",
            lat_long="40.7128,-74.0060",
            radius_unit="invalid"
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
        # Test 17: Validation error - invalid photo source
        print("\n17. Testing validation error (invalid photo source)...")
        result = await TripAdvisorAgentClient.call_tool(
            "get_location_photos",
            location_id=60763,
            source="InvalidSource"
        )
        if result.get("error"):
            print(f"✓ Error caught: {result.get('error_message')}")
            print(f"  Error code: {result.get('error_code')}")
        else:
            print(f"✗ Expected validation error but got: {result}")
        
    except Exception as e:
        print(f"\n✗ Error testing TripAdvisor Agent: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        await TripAdvisorAgentClient.close()
    
    print("\n" + "=" * 60)
    print("TripAdvisor Agent Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_tripadvisor_agent())

