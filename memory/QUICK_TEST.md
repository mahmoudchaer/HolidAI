# Quick Test Guide for Memory System

## ✅ What's Working

Based on the test, the following are confirmed working:
1. ✅ Memory extraction (LLM analyzes messages)
2. ✅ Memory storage (memories are saved to Qdrant)
3. ✅ Collection creation (Qdrant collection exists with correct dimensions)

## 🧪 How to Test in Your App

### Step 1: Start Services
```bash
# Start database and Qdrant
docker-compose up -d

# Verify they're running
docker ps
```

### Step 2: Start Your Flask App
```bash
cd frontend
python app.py
```

### Step 3: Test Messages

**Login** to your app, then try these messages:

#### Message 1 (Should Store Memory):
```
"I'm allergic to peanuts and prefer vegetarian restaurants"
```

**What to look for:**
- In Flask app logs: `[OK] Stored memory for your@email.com: ...`
- This should be saved with importance 4

#### Message 2 (Should Use Memory):
```
"Find me restaurants in Paris"
```

**What to look for:**
- The agent should mention your allergy/preference
- Response should include vegetarian options
- Should avoid restaurants with peanuts

#### Message 3 (Another Memory):
```
"My budget for hotels is $150 per night maximum"
```

#### Message 4 (Should Use Memory):
```
"Find hotels in Tokyo"
```

**What to look for:**
- Agent should remember your $150 budget
- Should filter hotels by price

## 📊 How to Verify It's Working

### Check Logs

When you send a message, watch the Flask app terminal for:

**Memory Storage:**
```
[OK] Stored memory for user@example.com: User is allergic to peanuts...
```

**Memory Retrieval:**
- Memories are retrieved silently (no log by default)
- But they're passed to the conversational agent

### Check Qdrant Directly

```bash
# Check collection info
curl http://localhost:6333/collections/agent_memory

# Check collection stats
curl http://localhost:6333/collections/agent_memory/points/count
```

### Check if Memories Are Used

The best way is to:
1. Tell the agent a preference (e.g., "I'm vegetarian")
2. Wait for confirmation it was stored
3. Ask a related question (e.g., "Find restaurants")
4. Check if the agent mentions your preference

## 🐛 Troubleshooting

### Memories Not Being Stored

1. **Check Qdrant is running:**
   ```bash
   docker ps | grep qdrant
   ```

2. **Check Flask logs** for errors:
   - `[ERROR] Error storing memory`
   - `[WARNING] Could not connect to Qdrant`

3. **Check OpenAI API key** is set in `.env`

### Memories Not Being Retrieved

1. **Check if memories exist:**
   ```bash
   curl http://localhost:6333/collections/agent_memory/points/count
   ```

2. **Check user_email** matches in session

3. **Check Flask logs** for retrieval errors

### Agent Not Using Memories

1. **Check conversational agent prompt** includes memories
2. **Check state** has `relevant_memories` field populated
3. **Check logs** for memory retrieval

## 💡 Suggested Test Conversation

```
You: "I'm allergic to peanuts"

[Wait for response - check logs for memory storage]

You: "Find me restaurants in Paris"

[Agent should mention your allergy and suggest safe restaurants]

You: "I prefer budget hotels under $100"

[Wait for response - check logs]

You: "Show me hotels in Tokyo"

[Agent should remember your budget preference]
```

## 🎯 Success Indicators

✅ **Memory is working if:**
- You see `[OK] Stored memory` in logs
- Agent remembers your preferences in later messages
- Agent mentions your constraints (allergies, budget, etc.)
- Different conversations remember the same preferences

❌ **Memory is NOT working if:**
- No `[OK] Stored memory` messages
- Agent doesn't remember previous preferences
- Errors in logs about Qdrant connection
- Agent asks for information you already provided

