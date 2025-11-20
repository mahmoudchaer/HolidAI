"""Utility to filter memories by agent domain relevance."""

def filter_memories_for_agent(memories: list, agent_type: str) -> list:
    """
    Filter memories to only include those relevant to a specific agent type.
    
    Args:
        memories: List of memory strings
        agent_type: Type of agent ('flight', 'hotel', 'tripadvisor', 'visa', 'utilities')
        
    Returns:
        Filtered list of memories relevant to the agent
    """
    if not memories:
        return []
    
    # Keywords that indicate relevance to each agent type
    relevance_keywords = {
        'flight': [
            'flight', 'airline', 'morning', 'evening', 'departure', 'arrival', 
            'time', 'prefers', 'prefer', 'seat', 'class', 'business', 'economy',
            'direct', 'layover', 'stopover', 'airport', 'luggage', 'baggage'
        ],
        'hotel': [
            'hotel', 'budget', 'price', 'star', 'rating', 'amenity', 'amenities',
            'wifi', 'pool', 'gym', 'breakfast', 'location', 'prefers', 'prefer',
            'room', 'suite', 'pet', 'parking', 'beach', 'city', 'downtown'
        ],
        'tripadvisor': [
            'restaurant', 'food', 'cuisine', 'vegetarian', 'vegan', 'allergic',
            'allergy', 'dietary', 'diet', 'prefers', 'prefer', 'meal', 'dining',
            'attraction', 'activity', 'museum', 'park', 'beach', 'tour'
        ],
        'visa': [
            'visa', 'passport', 'nationality', 'citizen', 'citizenship', 'country',
            'travel document', 'entry', 'requirement', 'prefers', 'prefer'
        ],
        'utilities': [
            'currency', 'weather', 'temperature', 'esim', 'sim', 'data', 'holiday',
            'time', 'timezone', 'convert', 'prefers', 'prefer'
        ]
    }
    
    if agent_type not in relevance_keywords:
        # Unknown agent type, return all memories
        return memories
    
    keywords = relevance_keywords[agent_type]
    filtered = []
    
    for memory in memories:
        memory_lower = memory.lower()
        # Check if memory contains any relevant keywords
        if any(keyword in memory_lower for keyword in keywords):
            filtered.append(memory)
    
    return filtered

