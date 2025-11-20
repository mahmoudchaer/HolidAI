# Memory System Testing Guide

## How to Verify Memory is Working

### 1. Start the Services

Make sure all services are running:

```bash
# Start database and Qdrant
docker-compose up -d

# Verify Qdrant is running
docker ps | grep qdrant

# Check Qdrant health
curl http://localhost:6333/health
```

### 2. Test Messages That Should Trigger Memory Storage

The memory system will save **factual information about user preferences, constraints, or important details**. Here are good test messages:

#### High Importance (should be saved):
- "I'm allergic to peanuts, so please avoid restaurants that serve peanuts"
- "I prefer hotels with a pool and gym"
- "I always travel with my dog, so I need pet-friendly hotels"
- "My budget for hotels is $150 per night maximum"
- "I'm vegetarian, so please suggest vegetarian restaurants"
- "I prefer window seats on flights"
- "I need wheelchair accessible hotels"

#### Medium Importance (might be saved):
- "I love Italian food"
- "I prefer morning flights"
- "I like beach destinations"

#### Low Importance (usually not saved):
- "Hello"
- "What's the weather?"
- "Show me flights to Paris" (without personal context)

### 3. How to Check if Memories Are Stored

#### Option A: Check Qdrant Directly

```bash
# Connect to Qdrant container
docker exec -it holidai_qdrant sh

# Or use curl to check collection
curl http://localhost:6333/collections/agent_memory
```

#### Option B: Check Application Logs

When you send a message, look for these log messages:

```
✓ Stored memory for user@example.com: I'm allergic to peanuts...
```

#### Option C: Create a Test Script

See `test_memory.py` below.

### 4. How to Verify Memories Are Being Used

After storing a memory, send a related query:

1. **First message** (stores memory):
   - "I'm allergic to peanuts"

2. **Second message** (should use memory):
   - "Find me restaurants in Paris"
   - The agent should remember your allergy and avoid peanut-serving restaurants

3. **Check the response** - it should mention your allergy preference

### 5. Testing Workflow

1. **Login/Signup** to get a user session
2. **Send a personal preference message**:
   ```
   "I'm vegetarian and prefer budget hotels under $100 per night"
   ```
3. **Check logs** for: `✓ Stored memory for...`
4. **Send a related query**:
   ```
   "Find me hotels in Tokyo"
   ```
5. **Check the response** - it should mention your vegetarian preference and budget constraint

### 6. Debugging

If memories aren't being stored:

1. **Check Qdrant is running**:
   ```bash
   docker ps | grep qdrant
   ```

2. **Check Qdrant logs**:
   ```bash
   docker logs holidai_qdrant
   ```

3. **Check Flask app logs** for errors:
   - Look for "⚠ Error storing memory" or "⚠ Warning: Could not connect to Qdrant"

4. **Verify collection exists**:
   ```bash
   curl http://localhost:6333/collections
   ```

5. **Check memory extraction**:
   - Look for "⚠ Error in memory extraction" in logs

### 7. Expected Behavior

✅ **Working correctly:**
- Personal preferences are extracted and stored
- Memories appear in agent responses
- Agent remembers user constraints across conversations

❌ **Not working:**
- No log messages about storing memories
- Agent doesn't remember previous preferences
- Errors in logs about Qdrant connection

