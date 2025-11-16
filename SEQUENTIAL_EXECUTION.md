# Sequential Execution System

## Overview

The LangGraph system now supports **multi-step sequential execution** where agents can run in steps, with later steps depending on results from earlier steps.

## How It Works

### Architecture

1. **Main Agent** - Creates a multi-step execution plan
2. **Plan Executor** - Executes the plan step-by-step
3. **Specialized Agents** - Run in parallel within each step
4. **Join Node** - Collects all results
5. **Conversational Agent** - Generates final response

### Execution Flow

```
User Query
    ↓
Main Agent (creates execution plan)
    ↓
Plan Executor (step 1)
    ↓
[Agent A, Agent B, Agent C] (parallel)
    ↓
Plan Executor (step 2)
    ↓
[Agent D] (uses results from step 1)
    ↓
Join Node
    ↓
Conversational Agent
```

## Examples

### Example 1: Simple Query (1 Step)
**Query:** "Find me flights and hotels to Paris"

**Execution Plan:**
- Step 1: `[flight_agent, hotel_agent]` - Both run in parallel

### Example 2: Sequential Dependency (2 Steps)
**Query:** "What's the weather in Paris? Then find hotels there."

**Execution Plan:**
- Step 1: `[utilities_agent]` - Get weather
- Step 2: `[hotel_agent]` - Find hotels (using location from step 1)

### Example 3: Complex Multi-Step
**Query:** "Find attractions in Rome, search flights there, then find nearby hotels"

**Execution Plan:**
- Step 1: `[tripadvisor_agent]` - Find attractions in Rome
- Step 2: `[flight_agent]` - Search flights to Rome
- Step 3: `[hotel_agent]` - Find hotels near attractions

## Key Features

✅ **Automatic Planning** - LLM analyzes query and creates optimal execution plan
✅ **Parallel Execution** - Independent agents run simultaneously within each step
✅ **Sequential Dependencies** - Later steps can access results from earlier steps
✅ **Flexible** - Adapts from simple (1 step) to complex (multiple steps) queries
✅ **Intelligent** - Main agent decides optimal step grouping

## Testing

Run the test script to see the system in action:

```bash
python test_sequential_execution.py
```

