# Execution Flow Diagram

## Complete Flow

```
┌─────────────────┐
│  User Query     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Main Agent     │  ← Analyzes query and creates execution plan
└────────┬────────┘    with multiple steps
         │
         ▼
┌─────────────────┐
│ Plan Executor   │  ← Gets Step 1 from plan
└────────┬────────┘
         │
         ▼
   ┌─────┴─────┐
   │ STEP 1    │  ← Agents run in PARALLEL
   ├───────────┤
   │ Agent A   │───┐
   │ Agent B   │───┼─► All complete at same time
   │ Agent C   │───┘
   └─────┬─────┘
         │
         ▼
┌─────────────────┐
│ Plan Executor   │  ← Gets Step 2 from plan
└────────┬────────┘    (can use results from Step 1)
         │
         ▼
   ┌─────┴─────┐
   │ STEP 2    │  ← Agents run in PARALLEL
   ├───────────┤
   │ Agent D   │───┐
   │ Agent E   │───┼─► All complete at same time
   └─────┬─────┘   │
         │◄────────┘
         ▼
┌─────────────────┐
│ Plan Executor   │  ← No more steps, route to join_node
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Join Node     │  ← Collects all results from all steps
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Conversational  │  ← Generates final response
│     Agent       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Final Response │
└─────────────────┘
```

## Key Points

1. **Main Agent** creates a plan like:
   ```json
   {
     "execution_plan": [
       {
         "step_number": 1,
         "agents": ["agent_a", "agent_b"],
         "description": "Initial data gathering"
       },
       {
         "step_number": 2,
         "agents": ["agent_c"],
         "description": "Process results from step 1"
       }
     ]
   }
   ```

2. **Plan Executor** runs each step sequentially:
   - Execute all agents in step 1 (parallel)
   - Wait for all to complete
   - Execute all agents in step 2 (parallel)
   - Wait for all to complete
   - Continue until plan complete

3. **Join Node** collects results from ALL steps

4. **State is preserved** across steps - later agents can access earlier results

## Example Scenarios

### Scenario 1: All Independent (1 Step)
```
Query: "Find flights and hotels to Paris"

Step 1: [flight_agent, hotel_agent]
  → Both agents run simultaneously
  → No dependencies
```

### Scenario 2: Sequential Dependency (2 Steps)
```
Query: "Find cheapest European city, then search flights there"

Step 1: [tripadvisor_agent]
  → Find cheapest city

Step 2: [flight_agent]
  → Use city from step 1 to search flights
```

### Scenario 3: Complex Multi-Step (3 Steps)
```
Query: "Get weather for Paris, find attractions, then search hotels near them"

Step 1: [utilities_agent, tripadvisor_agent]
  → Get weather and find attractions (parallel)

Step 2: [hotel_agent]
  → Search hotels near attractions from step 1
```

