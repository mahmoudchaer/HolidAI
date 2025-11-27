# Logging System Documentation

This document describes all logging systems implemented in HolidAI for Grafana dashboard creation.

## Overview

All logs are stored in **Azure Blob Storage** with the following configuration:
- **Storage Account**: `holidailogs`
- **Container**: `holidai-logs`
- **Connection String**: Set via `AZURE_BLOB_CONNECTION_STRING` environment variable

## Log Types

### 1. External API Calls (`api/`)

**Path Structure**: `api/{service_name}/{YYYY-MM-DD}/log_{timestamp}.json`

**Services**: `flights`, `hotels`, `activities`, `visa`, `weather`, `holidays`

**JSON Structure**:
```json
{
  "timestamp": "2025-11-27T17:44:19.123456Z",
  "service": "flights",
  "endpoint": "/search",
  "method": "GET",
  "request_payload": {
    "departure": "BEY",
    "arrival": "DXB",
    "departure_date": "2026-01-16"
  },
  "response_status": 200,
  "response_time_ms": 1234.56,
  "success": true,
  "error_message": null,
  "user_id": "mahmoudchaerps@gmail.com",
  "session_id": "efbd5f6d-6ba1-401d-9d47-e533d8d58bfb",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Fields**:
- `timestamp`: ISO 8601 UTC timestamp
- `service`: One of: `flights`, `hotels`, `activities`, `visa`, `weather`, `holidays`
- `endpoint`: API endpoint path (e.g., `/search`, `/rates`, `/weather`)
- `method`: HTTP method (`GET`, `POST`)
- `request_payload`: Request body/parameters (sensitive fields redacted)
- `response_status`: HTTP status code
- `response_time_ms`: Response time in milliseconds (float)
- `success`: Boolean indicating if call succeeded
- `error_message`: Error message string if failed, `null` if successful
- `user_id`: User email (optional, can be `null`)
- `session_id`: Session UUID (optional, can be `null`)
- `trace_id`: Unique UUID for this API call

---

### 2. Node Enter Logs (`agent/nodes/`)

**Path Structure**: `agent/nodes/{node_name}/{YYYY-MM-DD}/enter_{timestamp}.json`

**Node Names**: 
- `memory_agent`, `rfi_node`, `main_agent`, `feedback`, `plan_executor`, `plan_executor_feedback`
- `visa_agent`, `visa_agent_feedback`, `flight_agent`, `flight_agent_feedback`
- `hotel_agent`, `hotel_agent_feedback`, `tripadvisor_agent`, `tripadvisor_agent_feedback`
- `utilities_agent`, `utilities_agent_feedback`, `join_node`
- `conversational_agent`, `conversational_agent_feedback`, `final_planner_agent`

**JSON Structure**:
```json
{
  "type": "node_enter",
  "session_id": "efbd5f6d-6ba1-401d-9d47-e533d8d58bfb",
  "user_email": "mahmoudchaerps@gmail.com",
  "node_name": "flight_agent",
  "timestamp": "2025-11-27T17:44:19.123456Z"
}
```

**Fields**:
- `type`: Always `"node_enter"`
- `session_id`: Session UUID (can be `"unknown"` if not available)
- `user_email`: User email (optional, can be `null`)
- `node_name`: Name of the LangGraph node
- `timestamp`: ISO 8601 UTC timestamp

---

### 3. Node Exit Logs (`agent/nodes/`)

**Path Structure**: `agent/nodes/{node_name}/{YYYY-MM-DD}/exit_{timestamp}.json`

**JSON Structure**:
```json
{
  "type": "node_exit",
  "session_id": "efbd5f6d-6ba1-401d-9d47-e533d8d58bfb",
  "user_email": "mahmoudchaerps@gmail.com",
  "node_name": "flight_agent",
  "latency_ms": 2345.67,
  "timestamp": "2025-11-27T17:44:21.468912Z"
}
```

**Fields**:
- `type`: Always `"node_exit"`
- `session_id`: Session UUID (can be `"unknown"` if not available)
- `user_email`: User email (optional, can be `null`)
- `node_name`: Name of the LangGraph node
- `latency_ms`: Node execution time in milliseconds (float)
- `timestamp`: ISO 8601 UTC timestamp

---

### 4. User Interaction Logs (`agent/interactions/`)

**Path Structure**: `agent/interactions/{YYYY-MM-DD}/session_{session_id}/log_{timestamp}.json`

**JSON Structure**:
```json
{
  "type": "interaction",
  "session_id": "efbd5f6d-6ba1-401d-9d47-e533d8d58bfb",
  "user_email": "mahmoudchaerps@gmail.com",
  "user_message": "hello can u get me flights from beirut to dubai jan 16 2026 to jan 19 2026",
  "agent_response": "I found several flight options for your trip...",
  "latency_ms": 12345.67,
  "token_usage": null,
  "timestamp": "2025-11-27T17:44:45.123456Z"
}
```

**Fields**:
- `type`: Always `"interaction"`
- `session_id`: Session UUID
- `user_email`: User email (optional, can be `null`)
- `user_message`: Complete user message/query
- `agent_response`: Complete agent response text
- `latency_ms`: Total interaction time in milliseconds (float) - from user message to agent response
- `token_usage`: Token usage object (currently `null`, reserved for future use)
- `timestamp`: ISO 8601 UTC timestamp

---

### 5. Feedback Failure Logs (`agent/feedback_failures/`)

**Path Structure**: `agent/feedback_failures/{YYYY-MM-DD}/log_{timestamp}.json`

**JSON Structure**:
```json
{
  "type": "feedback_failure",
  "session_id": "efbd5f6d-6ba1-401d-9d47-e533d8d58bfb",
  "user_email": "mahmoudchaerps@gmail.com",
  "feedback_node": "flight_agent_feedback",
  "reason": "Status: need_retry, Message: Flight results are incomplete, missing return flights",
  "timestamp": "2025-11-27T17:44:25.123456Z"
}
```

**Fields**:
- `type`: Always `"feedback_failure"`
- `session_id`: Session UUID (can be `"unknown"` if not available)
- `user_email`: User email (optional, can be `null`)
- `feedback_node`: Name of the feedback node that failed (e.g., `flight_agent_feedback`, `hotel_agent_feedback`, `feedback`, `plan_executor_feedback`, `conversational_agent_feedback`)
- `reason`: Failure reason string (includes validation status and feedback message)
- `timestamp`: ISO 8601 UTC timestamp

**Feedback Node Names**:
- `feedback` - Main agent feedback
- `plan_executor_feedback` - Plan executor structure validation
- `flight_agent_feedback` - Flight agent results validation
- `hotel_agent_feedback` - Hotel agent results validation
- `visa_agent_feedback` - Visa agent results validation
- `tripadvisor_agent_feedback` - TripAdvisor agent results validation
- `utilities_agent_feedback` - Utilities agent results validation
- `conversational_agent_feedback` - Final response validation

---

### 6. LLM Call Logs (`agent/llm_calls/`)

**Path Structure**: `agent/llm_calls/{agent_name}/{YYYY-MM-DD}/log_{timestamp}.json`

**Agent Names**:
- `main_agent`, `flight_agent`, `hotel_agent`, `visa_agent`, `tripadvisor_agent`, `utilities_agent`
- `conversational_agent`, `final_planner_agent`, `rfi_node`
- `feedback`, `plan_executor_feedback`, `flight_agent_feedback`, `hotel_agent_feedback`
- `visa_agent_feedback`, `tripadvisor_agent_feedback`, `utilities_agent_feedback`
- `conversational_agent_feedback`

**JSON Structure**:
```json
{
  "type": "llm_call",
  "session_id": "efbd5f6d-6ba1-401d-9d47-e533d8d58bfb",
  "user_email": "mahmoudchaerps@gmail.com",
  "agent_name": "flight_agent",
  "model": "gpt-4.1",
  "prompt_preview": "You are the Flight Agent. Analyze the user's request and call the appropriate flight search tool...",
  "response_preview": "I'll search for flights from Beirut to Dubai...",
  "token_usage": {
    "prompt_tokens": 1250,
    "completion_tokens": 350,
    "total_tokens": 1600
  },
  "latency_ms": 2345.67,
  "timestamp": "2025-11-27T17:44:20.123456Z"
}
```

**Fields**:
- `type`: Always `"llm_call"`
- `session_id`: Session UUID (can be `"unknown"` if not available)
- `user_email`: User email (optional, can be `null`)
- `agent_name`: Name of the agent making the LLM call
- `model`: OpenAI model used (e.g., `"gpt-4.1"`, `"gpt-4o"`)
- `prompt_preview`: First 500 characters of the prompt (truncated for storage)
- `response_preview`: First 500 characters of the response (truncated for storage)
- `token_usage`: Object with token counts (can be `null` if not available)
  - `prompt_tokens`: Number of prompt tokens (integer or `null`)
  - `completion_tokens`: Number of completion tokens (integer or `null`)
  - `total_tokens`: Total tokens used (integer or `null`)
- `latency_ms`: LLM call latency in milliseconds (float)
- `timestamp`: ISO 8601 UTC timestamp

---

## Timestamp Format

All timestamps use ISO 8601 format with UTC timezone:
- Format: `YYYY-MM-DDTHH:MM:SS.ffffffZ`
- Example: `2025-11-27T17:44:19.123456Z`
- Always ends with `Z` to indicate UTC

## Blob Path Examples

### API Logs
```
api/flights/2025-11-27/log_20251127_174419_123456.json
api/hotels/2025-11-27/log_20251127_174420_234567.json
api/activities/2025-11-27/log_20251127_174421_345678.json
api/visa/2025-11-27/log_20251127_174422_456789.json
api/weather/2025-11-27/log_20251127_174423_567890.json
api/holidays/2025-11-27/log_20251127_174424_678901.json
```

### Node Logs
```
agent/nodes/flight_agent/2025-11-27/enter_20251127_174419_123456.json
agent/nodes/flight_agent/2025-11-27/exit_20251127_174421_468912.json
agent/nodes/main_agent/2025-11-27/enter_20251127_174415_987654.json
agent/nodes/main_agent/2025-11-27/exit_20251127_174418_321098.json
```

### Interaction Logs
```
agent/interactions/2025-11-27/session_efbd5f6d-6ba1-401d-9d47-e533d8d58bfb/log_20251127_174445_123456.json
```

### Feedback Failure Logs
```
agent/feedback_failures/2025-11-27/log_20251127_174425_123456.json
```

### LLM Call Logs
```
agent/llm_calls/flight_agent/2025-11-27/log_20251127_174420_123456.json
agent/llm_calls/main_agent/2025-11-27/log_20251127_174416_234567.json
agent/llm_calls/conversational_agent/2025-11-27/log_20251127_174430_345678.json
```

## Query Patterns for Grafana

### 1. API Call Success Rate
- Filter: `service = 'flights' AND success = true`
- Group by: `service`, `date`

### 2. API Response Times
- Metric: `response_time_ms`
- Filter: `service = 'flights'`
- Aggregation: `avg`, `p95`, `p99`

### 3. Node Execution Times
- Metric: `latency_ms` from node_exit logs
- Filter: `node_name = 'flight_agent'`
- Aggregation: `avg`, `max`, `min`

### 4. LLM Token Usage
- Metric: `token_usage.total_tokens`
- Filter: `agent_name = 'flight_agent'`
- Aggregation: `sum`, `avg`

### 5. Interaction Latency
- Metric: `latency_ms` from interaction logs
- Aggregation: `avg`, `p95`, `p99`

### 6. Feedback Failure Rate
- Count: `type = 'feedback_failure'`
- Group by: `feedback_node`, `date`

### 7. LLM Call Latency by Agent
- Metric: `latency_ms` from llm_call logs
- Group by: `agent_name`
- Aggregation: `avg`, `p95`

### 8. API Error Rate
- Count: `success = false`
- Group by: `service`, `error_message`

## Fallback Logging

If Azure Blob Storage upload fails, logs are written to local filesystem:
- **Path**: `./logs/failed_blob_logs/`
- **Format**: `agent_log_{timestamp}.json` or `api_log_{timestamp}.json`
- **Structure**: Same JSON structure as blob logs

## Environment Variables

Required for logging to work:
```bash
AZURE_BLOB_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=holidailogs;AccountKey=...;EndpointSuffix=core.windows.net"
AZURE_BLOB_ACCOUNT_NAME="holidailogs"
AZURE_BLOB_CONTAINER="holidai-logs"
```

## Notes

1. **Sensitive Data**: API request payloads are redacted before logging (API keys, passwords, etc.)
2. **Non-blocking**: All logging is asynchronous and non-blocking
3. **Retry Logic**: Failed uploads are retried once before falling back to local storage
4. **Preview Fields**: `prompt_preview` and `response_preview` in LLM logs are truncated to 500 characters
5. **Optional Fields**: `user_email`, `session_id`, `token_usage` can be `null` if not available

