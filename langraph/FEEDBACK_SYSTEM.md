# Feedback Validation System

## Overview

Added a feedback validation node between the Main Agent and Plan Executor to ensure execution plans are **LOGICALLY CORRECT** before execution.

**Important**: Feedback node ONLY validates plan logic. Each agent node handles its own missing parameter validation.

## Flow Diagram

```
User Query
    ↓
Main Agent (creates execution plan)
    ↓
Feedback Node (validates PLAN LOGIC only)
    ├── PASS → Plan Executor (execute plan)
    └── NEED_PLAN_FIX → Main Agent (fix plan with feedback)
```

## Validation Rules

### ONLY Plan Logic Validation

1. **Dependency Validation**:
   - If user wants to avoid holidays → holidays MUST be fetched BEFORE booking
   - If currency conversion needed → must come AFTER getting prices
   - If booking depends on city search → city search must come first

2. **Tool Sequencing**:
   - utilities_agent can call multiple tools in one step
   - Independent tasks can run in parallel
   - Dependent tasks must be sequential

3. **Common Illogical Patterns**:
   - User says "avoid holidays" but no holiday check before booking
   - Currency conversion without source data in earlier steps
   - Circular dependencies

### NOT Validated by Feedback Node

❌ Missing user parameters (origin, destination, dates, etc.)
   → Each agent handles this themselves

❌ Optional parameters
   → Agents decide what they need

❌ Data format validation
   → Handled by agents and tools

## Routing Decisions

### PASS
**Condition**: Plan logic is valid
**Action**: Route to `plan_executor` to execute the plan
**Example**: "Find hotels in Paris" → Step 1: [hotel_agent] ✅

### NEED_PLAN_FIX
**Condition**: Plan has logical errors or dependency issues
**Action**: Route back to `main_agent` with feedback to fix plan
**Example**: User wants to avoid holidays but plan doesn't fetch them ❌

## State Fields

```python
feedback_message: Optional[str]  # Feedback on plan logic issues
feedback_retry_count: int  # Counter to prevent infinite loops (max 2)
```

## Safety Features

- **Max Retries**: After 2 feedback loops, proceed anyway to avoid blocking
- **Error Handling**: On validation error, proceed to plan executor
- **Clear Feedback**: LLM provides specific feedback on logical issues

## Examples

### Example 1: Valid Simple Plan
```
User: "Find hotels in Paris"
Plan: Step 1: [hotel_agent]
Feedback: PASS
Action: Execute plan
Note: hotel_agent will handle any missing dates/parameters itself
```

### Example 2: Illogical Plan (Missing Holiday Check)
```
User: "Find hotels in Paris avoiding holidays"
Plan: Step 1: [hotel_agent] (NO holiday check!)
Feedback: NEED_PLAN_FIX
Message: "User wants to avoid holidays but plan doesn't fetch holidays before booking. Add utilities_agent with get_holidays in Step 1."
Action: Main agent revises plan
```

### Example 3: Valid Dependency Chain
```
User: "Get flight prices and convert to AED"
Plan:
  Step 1: [flight_agent]
  Step 2: [utilities_agent] - convert to AED
Feedback: PASS
Action: Execute plan (conversion comes after getting prices)
```

### Example 4: Missing Dependency
```
User: "Convert hotel prices to AED"
Plan: Step 1: [utilities_agent] - convert (no hotel search!)
Feedback: NEED_PLAN_FIX
Message: "Cannot convert hotel prices without first getting hotel data. Add hotel_agent in Step 1."
```

## Benefits

✅ **Catches illogical plans** (forgot to check holidays, wrong sequence)
✅ **Validates dependencies** (conversion after getting prices)
✅ **Self-correcting** (feedback loop allows plan fixes)
✅ **Simple & focused** (only validates plan logic)
✅ **Safe** (max retries prevent infinite loops)
✅ **Agent autonomy** (each agent handles its own parameter validation)

