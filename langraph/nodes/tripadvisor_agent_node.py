"""TripAdvisor Agent node for LangGraph orchestration."""

import sys
import os
import json
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "mcp_system"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import AgentState
from clients.tripadvisor_agent_client import TripAdvisorAgentClient

# Load environment variables from .env file in main directory
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _load_tool_docs() -> dict:
    """Load tool documentation from JSON file."""
    docs_path = project_root / "mcp_system" / "tool_docs" / "tripadvisor_docs.json"
    try:
        with open(docs_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load tripadvisor tool docs: {e}")
        return {}


def _format_tool_docs(docs: dict) -> str:
    """Format tool documentation for inclusion in prompt."""
    if not docs:
        return ""
    
    formatted = "\n\n=== TOOL DOCUMENTATION ===\n\n"
    
    for tool_name, tool_info in docs.items():
        formatted += f"Tool: {tool_name}\n"
        formatted += f"Description: {tool_info.get('description', 'N/A')}\n\n"
        
        if 'inputs' in tool_info:
            formatted += "Input Parameters:\n"
            for param, desc in tool_info['inputs'].items():
                formatted += f"  - {param}: {desc}\n"
            formatted += "\n"
        
        if 'outputs' in tool_info:
            formatted += "Output Fields:\n"
            for field, desc in tool_info['outputs'].items():
                formatted += f"  - {field}: {desc}\n"
            formatted += "\n"
        
        if 'examples' in tool_info and tool_info['examples']:
            formatted += "Examples:\n"
            for i, example in enumerate(tool_info['examples'][:1], 1):  # Show first example only (many tools)
                formatted += f"  Example {i}: {example.get('title', 'N/A')}\n"
                formatted += f"    {json.dumps(example.get('body', {}), indent=4)}\n"
            formatted += "\n"
        
        formatted += "---\n\n"
    
    return formatted


def get_tripadvisor_agent_prompt() -> str:
    """Get the system prompt for the TripAdvisor Agent."""
    docs = _load_tool_docs()
    docs_text = _format_tool_docs(docs)
    
    base_prompt = """You are the TripAdvisor Agent, a specialized agent that helps users find attractions, restaurants, and reviews.

CRITICAL: You MUST use the available tools to search for locations/attractions. Do NOT respond without calling a tool.

Your role:
- Understand the user's message using your LLM reasoning capabilities
- Use your understanding to determine what search parameters are needed
- Use the appropriate TripAdvisor tool with parameters you determine from the user's message
- The tool schemas will show you exactly what parameters are needed

Available tools (you will see their full schemas with function calling):
- search_locations: Search for locations/attractions (general search)
- get_location_reviews: Get reviews for a location
- get_location_photos: Get photos for a location
- get_location_details: Get detailed information about a location
- search_nearby: Search for nearby locations
- search_locations_by_rating: Search locations filtered by minimum rating
- search_nearby_by_rating: Search nearby locations filtered by minimum rating
- get_top_rated_locations: Get top k highest-rated locations
- search_locations_by_price: Search locations filtered by maximum price level
- search_nearby_by_price: Search nearby locations filtered by maximum price level
- search_nearby_by_distance: Search nearby locations sorted by distance
- find_closest_location: Find the single closest location
- search_restaurants_by_cuisine: Search restaurants filtered by cuisine type
- get_multiple_location_details: Get details for multiple locations
- compare_locations: Compare 2-3 locations side by side

IMPORTANT:
- Use your LLM understanding to determine parameters from the user's message - NO code-based parsing is used
- Choose the most appropriate tool based on your understanding of the user's query
- Use the tool schemas to understand required vs optional parameters
- ALWAYS call a tool - do not ask for clarification unless absolutely critical information is missing
- You have access to the full tool documentation through function calling - use it to understand parameter requirements

CRITICAL: If the user requests photos or images for locations/restaurants:
1. FIRST call search_locations (or search_restaurants_by_cuisine) to get the list of locations
2. THEN call get_location_photos for EACH location using the location_id from the search results
3. The location_id is found in the "location_id" field of each location in the search results
4. If user asks for a specific number of photos (e.g., "2 photos"), use the limit parameter in get_location_photos
5. You can make multiple tool calls - call search_locations first, then get_location_photos for each location

CRITICAL: If the user asks for locations "near [landmark]" or "around [landmark]":
1. FIRST call search_locations to find the landmark location - DO NOT use category="restaurants" for this search! 
   - Search for the landmark name ONLY (e.g., "American University of Beirut")
   - Do NOT add "restaurants" to the search query
   - Do NOT use category parameter for the landmark search
   - This search is to find the LANDMARK itself, not restaurants
2. Extract the latitude and longitude from the first result (fields: "latitude" and "longitude")
   - If coordinates are not in the search result, call get_location_details with the location_id to get coordinates
3. THEN call search_nearby with lat_long parameter in format "latitude,longitude" (e.g., "33.8849,35.5168")
   - Use category="restaurants" if searching for restaurants, category="hotels" for hotels, etc.
   - Use radius=2.0 (or appropriate number) and radius_unit="km" for search_nearby
   - The radius parameter must be a NUMBER (float), not a string
4. The search_nearby results are the actual restaurants/locations you want to return

CRITICAL: If the user requests reviews for locations/restaurants:
1. FIRST get the list of locations using search_locations, search_nearby, or search_restaurants_by_cuisine
2. THEN call get_location_reviews for EACH location using the location_id
3. If user asks for a specific number of reviews (e.g., "1 review"), use the limit parameter in get_location_reviews

You have access to the full tool documentation through function calling. Use your LLM reasoning to understand the user's message and call the appropriate tool with the correct parameters."""
    
    return base_prompt + docs_text


async def tripadvisor_agent_node(state: AgentState) -> AgentState:
    """TripAdvisor Agent node that handles location and review queries.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated agent state with response
    """
    import time
    from datetime import datetime
    
    start_time = time.time()
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    # Check if this node should execute (for parallel execution mode)
    pending_nodes = state.get("pending_nodes", [])
    if isinstance(pending_nodes, list) and len(pending_nodes) > 0:
        # If we're in parallel mode and this node is not in pending_nodes, skip execution
        if "tripadvisor_agent" not in pending_nodes:
            # Not supposed to execute, just pass through to join_node
            updated_state = state.copy()
            updated_state["route"] = "join_node"
            print(f"[{timestamp}] TripAdvisor agent: SKIPPED (not in pending_nodes: {pending_nodes})")
            return updated_state
    
    print(f"[{timestamp}] TripAdvisor agent: STARTING execution (pending_nodes: {pending_nodes})")
    
    user_message = state.get("user_message", "")
    
    # Always use LLM to extract parameters from user message
    # LLM has access to tool documentation and can intelligently extract parameters
    # Get tools available to tripadvisor agent
    tools = await TripAdvisorAgentClient.list_tools()
    
    # Use the standard prompt - LLM will extract parameters from user message
    prompt = get_tripadvisor_agent_prompt()
    
    # Prepare messages for LLM
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_message}
    ]
    
    # Build function calling schema for tripadvisor tools
    functions = []
    def _sanitize_schema(schema: dict) -> dict:
        """Ensure arrays have 'items' and sanitize nested schemas."""
        if not isinstance(schema, dict):
            return schema
        sanitized = dict(schema)
        schema_type = sanitized.get("type")
        if schema_type == "array" and "items" not in sanitized:
            sanitized["items"] = {"type": "object"}
        if schema_type == "object":
            props = sanitized.get("properties", {})
            for key, val in list(props.items()):
                props[key] = _sanitize_schema(val)
            sanitized["properties"] = props
        if "items" in sanitized and isinstance(sanitized["items"], dict):
            sanitized["items"] = _sanitize_schema(sanitized["items"])
        return sanitized

    for tool in tools:
        input_schema = tool.get("inputSchema", {})
        input_schema = _sanitize_schema(input_schema)
        functions.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", f"TripAdvisor tool: {tool['name']}"),
                "parameters": input_schema
            }
        })
    
    # Call LLM with function calling - require tool use when functions are available
    if functions:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=functions,
            tool_choice="required"  # Force tool call when tools are available
        )
    else:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
    
    message = response.choices[0].message
    updated_state = state.copy()
    
    # Check if user is requesting photos or reviews
    user_lower = user_message.lower()
    wants_photos = any(word in user_lower for word in ["photo", "photos", "image", "images", "picture", "pictures", "pic", "pics"])
    wants_reviews = any(word in user_lower for word in ["review", "reviews", "rating", "ratings"])
    print(f"TripAdvisor agent: wants_photos={wants_photos}, wants_reviews={wants_reviews}, user_message={user_message[:100]}")
    
    # Check if user is asking for "near [landmark]" - need to find landmark first
    wants_nearby = any(word in user_lower for word in ["near", "nearby", "around", "close to"])
    
    # Check if LLM wants to call a tool
    if message.tool_calls:
        import json
        
        # Process all tool calls
        all_results = []
        locations_data = []
        landmark_coords = None
        
        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            
            # Fix radius if it's a string (convert to float/int)
            if "radius" in args and isinstance(args["radius"], str):
                try:
                    args["radius"] = float(args["radius"])
                except ValueError:
                    pass
            
            try:
                result = await TripAdvisorAgentClient.invoke(tool_name, **args)
                
                # If this is a search_locations call for a landmark (when user wants nearby), get coordinates
                # IMPORTANT: Only process if this search was for the landmark itself (not restaurants)
                # We detect this by checking if the search_query contains the landmark name but NOT restaurant keywords
                if tool_name == "search_locations" and wants_nearby and not result.get("error"):
                    # Check if this search was for the landmark (not restaurants)
                    # If args has category="restaurants", skip - that's not the landmark search
                    search_category = args.get("category", "").lower()
                    if search_category != "restaurants":
                        data = result.get("data", [])
                        if data and len(data) > 0:
                            # Get first result (the landmark)
                            landmark = data[0]
                            landmark_id = landmark.get("location_id") or landmark.get("locationId")
                            
                            # Check if it has coordinates directly
                            if "latitude" in landmark and "longitude" in landmark:
                                landmark_coords = f"{landmark['latitude']},{landmark['longitude']}"
                                print(f"Found landmark coordinates from search: {landmark_coords}")
                            # Otherwise, get coordinates from location details
                            elif landmark_id:
                                try:
                                    details_result = await TripAdvisorAgentClient.invoke(
                                        "get_location_details",
                                        location_id=landmark_id
                                    )
                                    if not details_result.get("error") and details_result.get("data"):
                                        details = details_result.get("data", {})
                                        if "latitude" in details and "longitude" in details:
                                            landmark_coords = f"{details['latitude']},{details['longitude']}"
                                            print(f"Found landmark coordinates from details: {landmark_coords}")
                                except Exception as e:
                                    print(f"Error getting location details for coordinates: {e}")
                
                # If this is a search_nearby call, store the results (these are the restaurants we want)
                if tool_name == "search_nearby" and not result.get("error") and result.get("data"):
                    locations_data = result.get("data", [])
                    print(f"Found {len(locations_data)} locations from search_nearby")
                
                # If this is a search_locations call for restaurants (not landmark), store locations
                # Only if it's NOT a landmark search (has category=restaurants or search query contains restaurant keywords)
                if tool_name in ["search_locations", "search_restaurants_by_cuisine"]:
                    search_category = args.get("category", "").lower()
                    search_query = args.get("search_query", "").lower()
                    # Only store if this is a restaurant search, not a landmark search
                    if (search_category == "restaurants" or "restaurant" in search_query) and not wants_nearby:
                        if not result.get("error") and result.get("data"):
                            locations_data = result.get("data", [])
                            print(f"Found {len(locations_data)} locations from search_locations")
                    # Also store if user wants photos/reviews and this is NOT a landmark search
                    elif (wants_photos or wants_reviews) and not wants_nearby:
                        if not result.get("error") and result.get("data"):
                            locations_data = result.get("data", [])
                            print(f"Found {len(locations_data)} locations from search")
                
                all_results.append({
                    "tool": tool_name,
                    "result": result
                })
                
            except Exception as e:
                all_results.append({
                    "tool": tool_name,
                    "result": {"error": True, "error_message": str(e)}
                })
        
        # If we found a landmark but haven't searched nearby yet, do that now
        if landmark_coords and not locations_data:
            try:
                # Extract category from user message (default to restaurants)
                category = "restaurants"
                if "restaurant" in user_lower:
                    category = "restaurants"
                elif "hotel" in user_lower:
                    category = "hotels"
                elif "attraction" in user_lower:
                    category = "attractions"
                
                # Default radius of 2km if not specified
                radius = 2.0
                
                nearby_result = await TripAdvisorAgentClient.invoke(
                    "search_nearby",
                    lat_long=landmark_coords,
                    category=category,
                    radius=radius,
                    radius_unit="km"
                )
                
                if not nearby_result.get("error") and nearby_result.get("data"):
                    locations_data = nearby_result.get("data", [])
                    all_results.append({
                        "tool": "search_nearby",
                        "result": nearby_result
                    })
            except Exception as e:
                print(f"Error searching nearby: {e}")
        
        # If we have locations and user wants photos, fetch photos for each location
        print(f"TripAdvisor agent: Checking photos - locations_data count: {len(locations_data) if locations_data else 0}, wants_photos: {wants_photos}")
        if locations_data and wants_photos:
            # Extract number of photos requested (default to 2 if "2 photos" mentioned, otherwise 5)
            photo_limit = 2 if "2 photo" in user_lower or "two photo" in user_lower else 5
            
            for location in locations_data[:10]:  # Limit to first 10 locations to avoid too many calls
                location_id = location.get("location_id")
                if location_id:
                    try:
                        photo_result = await TripAdvisorAgentClient.invoke(
                            "get_location_photos",
                            location_id=location_id,
                            limit=photo_limit
                        )
                        # Attach photos to the location
                        if not photo_result.get("error") and photo_result.get("data"):
                            import copy
                            photos = copy.deepcopy(photo_result.get("data", [])[:photo_limit])  # Deep copy to avoid reference issues
                            # Pre-extract URLs for easier access by conversational agent
                            for photo in photos:
                                if "images" in photo and isinstance(photo["images"], dict):
                                    # Extract URL in priority order: large -> medium -> original -> small
                                    photo_url = None
                                    for size in ["large", "medium", "original", "small"]:
                                        if size in photo["images"] and isinstance(photo["images"][size], dict):
                                            photo_url = photo["images"][size].get("url")
                                            if photo_url:
                                                break
                                    # Add a simplified url field for easier access
                                    if photo_url:
                                        photo["url"] = photo_url
                            location["photos"] = photos
                            print(f"Attached {len(photos)} photos to location {location.get('name', 'Unknown')} (ID: {location_id})")
                            if photos and photos[0].get("url"):
                                print(f"  First photo URL: {photos[0].get('url')}")
                        else:
                            location["photos"] = []
                            print(f"No photos found for location {location.get('name', 'Unknown')} (ID: {location_id})")
                    except Exception as e:
                        location["photos"] = []
                        print(f"Error fetching photos for location {location_id}: {e}")
        
        # If we have locations and user wants reviews, fetch reviews for each location
        if locations_data and wants_reviews:
            # Extract number of reviews requested (default to 1 if "1 review" mentioned, otherwise 5)
            review_limit = 1 if "1 review" in user_lower or "one review" in user_lower else 5
            
            for location in locations_data[:10]:  # Limit to first 10 locations to avoid too many calls
                location_id = location.get("location_id")
                if location_id:
                    try:
                        review_result = await TripAdvisorAgentClient.invoke(
                            "get_location_reviews",
                            location_id=location_id,
                            limit=review_limit
                        )
                        # Attach reviews to the location, but REMOVE avatar data to prevent confusion
                        if not review_result.get("error") and review_result.get("data"):
                            reviews = review_result.get("data", [])[:review_limit]
                            # Remove avatar data from each review to prevent displaying user photos
                            cleaned_reviews = []
                            for review in reviews:
                                cleaned_review = dict(review)
                                # Remove avatar from user object
                                if "user" in cleaned_review and isinstance(cleaned_review["user"], dict):
                                    user_copy = dict(cleaned_review["user"])
                                    user_copy.pop("avatar", None)  # Remove avatar completely
                                    cleaned_review["user"] = user_copy
                                cleaned_reviews.append(cleaned_review)
                            location["reviews"] = cleaned_reviews
                        else:
                            location["reviews"] = []
                    except Exception as e:
                        location["reviews"] = []
                        print(f"Error fetching reviews for location {location_id}: {e}")
        
        # Combine results - use the search result as the main result, but include photos and reviews
        if all_results:
            # Find the main result - prioritize search_nearby for "near" queries, otherwise use search results
            main_result = None
            if wants_nearby:
                # For "near" queries, ONLY use search_nearby results (not the landmark search)
                for result_item in all_results:
                    if result_item["tool"] == "search_nearby":
                        main_result = result_item["result"]
                        break
            else:
                # For regular searches, use search results
                for result_item in all_results:
                    if result_item["tool"] in ["search_nearby", "search_locations", "search_restaurants_by_cuisine"]:
                        main_result = result_item["result"]
                        break
            
            if not main_result and all_results:
                # Fallback: use first non-landmark result
                for result_item in all_results:
                    if result_item["tool"] != "get_location_details":
                        main_result = result_item["result"]
                        break
            
            if not main_result and all_results:
                main_result = all_results[0]["result"]
            
            # If we have locations with photos/reviews, update the main result
            # CRITICAL: Only use locations_data if it's from search_nearby (for "near" queries) or from actual restaurant searches
            if locations_data and len(locations_data) > 0:
                # Verify these are actually restaurants (for "near" queries)
                if wants_nearby:
                    # Filter to ensure we only have restaurants, not landmarks
                    filtered_locations = []
                    for loc in locations_data:
                        category = loc.get("category", "").lower()
                        name = loc.get("name", "").lower()
                        # Only include if it's a restaurant category OR if name doesn't contain university/museum
                        is_restaurant = category == "restaurants" or "restaurant" in category
                        is_not_landmark = "university" not in name and "museum" not in name and "campus" not in name
                        if is_restaurant or (is_not_landmark and category != "attractions"):
                            filtered_locations.append(loc)
                    if filtered_locations:
                        locations_data = filtered_locations
                        print(f"Filtered to {len(locations_data)} restaurant locations (removed landmarks)")
                    else:
                        print(f"Warning: No restaurants found after filtering. Original count: {len(locations_data)}")
                
                # CRITICAL: Verify each location has unique photos before storing
                print(f"\n=== VERIFYING PHOTOS FOR {len(locations_data)} LOCATIONS ===")
                for idx, loc in enumerate(locations_data):
                    loc_name = loc.get("name", "Unknown")
                    loc_id = loc.get("location_id", "N/A")
                    photos = loc.get("photos", [])
                    print(f"Location {idx}: {loc_name} (ID: {loc_id}) - {len(photos)} photos")
                    if photos:
                        for photo_idx, photo in enumerate(photos):
                            photo_url = photo.get("url", "NO URL")
                            print(f"  Photo {photo_idx}: {photo_url[:80]}...")
                    else:
                        print(f"  WARNING: No photos for this location!")
                print("=== END PHOTO VERIFICATION ===\n")
                
                main_result["data"] = locations_data
            
            # Store the combined result
            tripadvisor_result = main_result
            
            # Format the response
            if tripadvisor_result.get("error"):
                response_text = f"I encountered an error while searching TripAdvisor: {tripadvisor_result.get('error_message', 'Unknown error')}"
                if tripadvisor_result.get("suggestion"):
                    response_text += f"\n\nSuggestion: {tripadvisor_result.get('suggestion')}"
            
            # Store the raw result directly in state for parallel execution (both legacy and new structure)
            updated_state["tripadvisor_result"] = tripadvisor_result
            if "results" not in updated_state:
                updated_state["results"] = {}
            updated_state["results"]["tripadvisor_agent"] = tripadvisor_result
            updated_state["results"]["tripadvisor"] = tripadvisor_result
            updated_state["results"]["tripadvisor_result"] = tripadvisor_result
            elapsed = time.time() - start_time
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{timestamp}] TripAdvisor agent: COMPLETED in {elapsed:.2f}s")
            updated_state["results"]["activities"] = tripadvisor_result
            # No need to set route - using add_edge means we automatically route to join_node
        
        return updated_state
    
    # No tool call - store empty result
    error_result = {"error": True, "error_message": "No TripAdvisor search parameters provided"}
    updated_state["tripadvisor_result"] = error_result
    if "results" not in updated_state:
        updated_state["results"] = {}
    updated_state["results"]["tripadvisor_agent"] = error_result
    updated_state["results"]["tripadvisor"] = error_result
    updated_state["results"]["tripadvisor_result"] = error_result
    elapsed = time.time() - start_time
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] TripAdvisor agent: COMPLETED (no tool call) in {elapsed:.2f}s")
    updated_state["results"]["activities"] = error_result
    # No need to set route - using add_edge means we automatically route to join_node
    
    return updated_state

