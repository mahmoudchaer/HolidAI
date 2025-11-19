# Feedback System Architecture

## Overview

The LangGraph system now includes comprehensive feedback validation at every stage of the workflow. Each agent has a dedicated feedback node that validates its output before proceeding to the next step. This ensures quality and correctness throughout the entire execution pipeline.

## Feedback Nodes

### 1. Main Agent Feedback (`feedback_node.py`)
- **Purpose**: Validates the execution plan logic created by the main agent
- **What it checks**:
  - Dependencies are properly ordered (e.g., holidays before booking)
  - Tool sequencing makes sense
  - No circular dependencies
- **On pass**: Routes to Plan Executor Feedback
- **On fail**: Routes back to Main Agent with feedback to regenerate plan

### 2. Plan Executor Feedback (`plan_executor_feedback_node.py`)
- **Purpose**: Validates the execution plan structure before execution
- **What it checks**:
  - Each step has valid agents assigned
  - Agent names are from available agents list
  - Step numbers are sequential
  - No empty agent arrays
- **On pass**: Routes to Plan Executor to begin execution
- **On fail**: Routes back to Main Agent to fix structure

### 3. Flight Agent Feedback (`flight_agent_feedback_node.py`)
- **Purpose**: Validates flight search results
- **What it checks**:
  - Results contain necessary information (airline, price, times)
  - Error messages are legitimate
  - Data quality (valid prices, routes match request)
  - Alignment with user's request (dates, trip type)
- **On pass**: Routes to Plan Executor for next step
- **On fail**: Retries Flight Agent (max 2 retries)

### 4. Hotel Agent Feedback (`hotel_agent_feedback_node.py`)
- **Purpose**: Validates hotel search results
- **What it checks**:
  - Hotels have names, locations, ratings
  - Price handling (may or may not be required)
  - Data quality and completeness
  - Results match user's location/criteria
- **On pass**: Routes to Plan Executor for next step
- **On fail**: Retries Hotel Agent (max 2 retries)

### 5. Visa Agent Feedback (`visa_agent_feedback_node.py`)
- **Purpose**: Validates visa requirement results
- **What it checks**:
  - Clear indication of visa requirement status
  - Information is specific to country pair
  - Results answer the user's question clearly
  - No vague or incomplete information
- **On pass**: Routes to Plan Executor for next step
- **On fail**: Retries Visa Agent (max 2 retries)

### 6. TripAdvisor Agent Feedback (`tripadvisor_agent_feedback_node.py`)
- **Purpose**: Validates location/attraction/restaurant search results
- **What it checks**:
  - Results match requested type (restaurants vs attractions)
  - Items have names, locations, ratings
  - Results match the search location
  - Data quality and relevance
- **On pass**: Routes to Plan Executor for next step
- **On fail**: Retries TripAdvisor Agent (max 2 retries)

### 7. Utilities Agent Feedback (`utilities_agent_feedback_node.py`)
- **Purpose**: Validates utility operation results (holidays, weather, currency, eSIM)
- **What it checks**:
  - Tool-specific validation (holidays have dates, weather has temp, etc.)
  - Multiple results are properly structured
  - Data completeness for each utility function
  - Error handling for eSIM with fallback providers
- **On pass**: Routes to Plan Executor for next step
- **On fail**: Retries Utilities Agent (max 2 retries)

### 8. Conversational Agent Feedback (`conversational_agent_feedback_node.py`)
- **Purpose**: Validates the final user response quality
- **What it checks**:
  - Response addresses user's original query
  - All collected information is included
  - No JSON or technical data visible to user
  - Links are properly formatted (especially eSIM)
  - No contradictions with collected data
  - Response is conversational and helpful
- **On pass**: Ends workflow
- **On fail**: Regenerates response (max 2 retries)

## Workflow Architecture

### Standard Flow
```
User Message
    ↓
Main Agent → Main Feedback → Plan Executor Feedback → Plan Executor
                ↓ fail                  ↓ fail               ↓
            (retry Main Agent)      (retry Main Agent)    Execute Step
                                                               ↓
                                            [Parallel Agents: Flight, Hotel, etc.]
                                                               ↓
                                        [Each Agent → Its Feedback Node]
                                                               ↓
                                            (if pass: continue, if fail: retry agent)
                                                               ↓
                                                          Join Node
                                                               ↓
                                            Conversational Agent → Conversational Feedback
                                                                            ↓
                                                                    (if pass: END)
```

### Retry Mechanism
- Each feedback node has a retry counter
- Maximum 2 retries per agent (configurable via `MAX_FEEDBACK_RETRIES`)
- After max retries, system proceeds to avoid infinite loops
- Feedback messages guide agents on what to fix

### State Management
New state fields added to `AgentState`:
- `plan_executor_feedback_message` and `plan_executor_retry_count`
- `flight_feedback_message` and `flight_feedback_retry_count`
- `hotel_feedback_message` and `hotel_feedback_retry_count`
- `visa_feedback_message` and `visa_feedback_retry_count`
- `tripadvisor_feedback_message` and `tripadvisor_feedback_retry_count`
- `utilities_feedback_message` and `utilities_feedback_retry_count`
- `conversational_feedback_message` and `conversational_feedback_retry_count`

## Benefits

1. **Quality Assurance**: Every agent's output is validated before proceeding
2. **Error Recovery**: Agents can retry with feedback instead of failing silently
3. **Logical Consistency**: Plans and results are checked for logical errors
4. **User Experience**: Final response is validated for quality and completeness
5. **Modularity**: Each feedback node is specialized for its agent's purpose
6. **Safety**: Max retry limits prevent infinite loops

## Configuration

To adjust retry limits, modify `MAX_FEEDBACK_RETRIES` in each feedback node file:
```python
MAX_FEEDBACK_RETRIES = 2  # Default value
```

To adjust the recursion limit for the entire graph, modify in `graph.py`:
```python
config = {"recursion_limit": 100}  # Default value
```

## Extending the System

To add a feedback node for a new agent:
1. Create `{agent_name}_feedback_node.py` in `langraph/nodes/`
2. Define validation rules specific to that agent's output
3. Add state fields in `state.py`: `{agent_name}_feedback_message` and `{agent_name}_feedback_retry_count`
4. Import and add node in `graph.py`
5. Wire the agent → feedback → plan_executor flow in `graph.py`
6. Initialize the new state fields in `run()` function

