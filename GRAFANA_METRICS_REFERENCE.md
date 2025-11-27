# Grafana Metrics Reference

Quick reference for building Grafana dashboards from HolidAI logs.

## Available Metrics

### 1. API Call Metrics

**Source**: `api/{service}/{date}/log_*.json`

| Metric | Field | Type | Description |
|--------|-------|------|-------------|
| API Response Time | `response_time_ms` | Float | Response time in milliseconds |
| API Success Rate | `success` | Boolean | Whether API call succeeded |
| API Error Count | `success = false` | Count | Number of failed API calls |
| API Calls per Service | Count by `service` | Count | Total API calls per service |

**Dimensions**:
- `service`: flights, hotels, activities, visa, weather, holidays
- `endpoint`: API endpoint path
- `method`: GET, POST
- `response_status`: HTTP status code
- `error_message`: Error message (for failures)

**Example Queries**:
```
# Average response time by service
avg(response_time_ms) by (service)

# Success rate by service
sum(success) / count(*) by (service)

# Error rate
count(success = false) by (service, error_message)
```

---

### 2. Node Execution Metrics

**Source**: `agent/nodes/{node_name}/{date}/exit_*.json`

| Metric | Field | Type | Description |
|--------|-------|------|-------------|
| Node Latency | `latency_ms` | Float | Node execution time in milliseconds |
| Node Execution Count | Count | Integer | Number of node executions |

**Dimensions**:
- `node_name`: All LangGraph node names (see list below)
- `session_id`: Session identifier
- `user_email`: User email

**Node Names**:
- `memory_agent`, `rfi_node`, `main_agent`, `feedback`, `plan_executor`, `plan_executor_feedback`
- `visa_agent`, `visa_agent_feedback`, `flight_agent`, `flight_agent_feedback`
- `hotel_agent`, `hotel_agent_feedback`, `tripadvisor_agent`, `tripadvisor_agent_feedback`
- `utilities_agent`, `utilities_agent_feedback`, `join_node`
- `conversational_agent`, `conversational_agent_feedback`, `final_planner_agent`

**Example Queries**:
```
# Average node latency by node
avg(latency_ms) by (node_name)

# P95 latency by node
quantile(0.95, latency_ms) by (node_name)

# Node execution count
count() by (node_name)
```

---

### 3. Interaction Metrics

**Source**: `agent/interactions/{date}/session_{session_id}/log_*.json`

| Metric | Field | Type | Description |
|--------|-------|------|-------------|
| Interaction Latency | `latency_ms` | Float | Total time from user message to agent response |
| Interactions per Session | Count | Integer | Number of interactions per session |
| Daily Interactions | Count | Integer | Total interactions per day |

**Dimensions**:
- `session_id`: Session identifier
- `user_email`: User email

**Example Queries**:
```
# Average interaction latency
avg(latency_ms)

# P99 interaction latency
quantile(0.99, latency_ms)

# Interactions per user
count() by (user_email)
```

---

### 4. Feedback Failure Metrics

**Source**: `agent/feedback_failures/{date}/log_*.json`

| Metric | Field | Type | Description |
|--------|-------|------|-------------|
| Feedback Failures | Count | Integer | Number of feedback failures |
| Failure Rate | Count / Total | Percentage | Percentage of feedback validations that failed |

**Dimensions**:
- `feedback_node`: Name of feedback node
- `reason`: Failure reason string
- `session_id`: Session identifier
- `user_email`: User email

**Feedback Node Names**:
- `feedback` - Main agent feedback
- `plan_executor_feedback` - Plan executor validation
- `flight_agent_feedback` - Flight agent validation
- `hotel_agent_feedback` - Hotel agent validation
- `visa_agent_feedback` - Visa agent validation
- `tripadvisor_agent_feedback` - TripAdvisor agent validation
- `utilities_agent_feedback` - Utilities agent validation
- `conversational_agent_feedback` - Final response validation

**Example Queries**:
```
# Failures by feedback node
count() by (feedback_node)

# Failure rate by node
count() / (count() + count(node_exit where node_name matches feedback_node)) by (feedback_node)

# Top failure reasons
count() by (reason)
```

---

### 5. LLM Call Metrics

**Source**: `agent/llm_calls/{agent_name}/{date}/log_*.json`

| Metric | Field | Type | Description |
|--------|-------|------|-------------|
| LLM Latency | `latency_ms` | Float | LLM call response time |
| Token Usage | `token_usage.total_tokens` | Integer | Total tokens used |
| Prompt Tokens | `token_usage.prompt_tokens` | Integer | Prompt tokens |
| Completion Tokens | `token_usage.completion_tokens` | Integer | Completion tokens |
| LLM Calls per Agent | Count | Integer | Number of LLM calls per agent |

**Dimensions**:
- `agent_name`: Agent making the call (see list below)
- `model`: OpenAI model (gpt-4.1, gpt-4o)
- `session_id`: Session identifier
- `user_email`: User email

**Agent Names**:
- `main_agent`, `flight_agent`, `hotel_agent`, `visa_agent`, `tripadvisor_agent`, `utilities_agent`
- `conversational_agent`, `final_planner_agent`, `rfi_node`
- `feedback`, `plan_executor_feedback`, `flight_agent_feedback`, `hotel_agent_feedback`
- `visa_agent_feedback`, `tripadvisor_agent_feedback`, `utilities_agent_feedback`
- `conversational_agent_feedback`

**Example Queries**:
```
# Average LLM latency by agent
avg(latency_ms) by (agent_name)

# Total token usage
sum(token_usage.total_tokens)

# Token usage by agent
sum(token_usage.total_tokens) by (agent_name)

# LLM calls per agent
count() by (agent_name)

# Cost estimation (if you have token pricing)
sum(token_usage.prompt_tokens) * $0.01 + sum(token_usage.completion_tokens) * $0.03
```

---

## Recommended Dashboard Panels

### 1. API Performance Dashboard
- **Panel 1**: API Response Time (Line Chart) - `avg(response_time_ms) by (service)`
- **Panel 2**: API Success Rate (Gauge) - `sum(success) / count(*)`
- **Panel 3**: API Calls per Service (Bar Chart) - `count() by (service)`
- **Panel 4**: Error Rate by Service (Table) - `count(success = false) by (service, error_message)`

### 2. Agent Performance Dashboard
- **Panel 1**: Node Execution Time (Heatmap) - `latency_ms by (node_name)`
- **Panel 2**: Slowest Nodes (Bar Chart) - `avg(latency_ms) by (node_name)` sorted desc
- **Panel 3**: Node Execution Count (Table) - `count() by (node_name)`
- **Panel 4**: Node Success Rate (Gauge) - Based on feedback failures

### 3. LLM Usage Dashboard
- **Panel 1**: Token Usage Over Time (Line Chart) - `sum(token_usage.total_tokens)`
- **Panel 2**: Token Usage by Agent (Pie Chart) - `sum(token_usage.total_tokens) by (agent_name)`
- **Panel 3**: LLM Latency by Agent (Bar Chart) - `avg(latency_ms) by (agent_name)`
- **Panel 4**: LLM Calls per Agent (Table) - `count() by (agent_name)`

### 4. User Experience Dashboard
- **Panel 1**: Interaction Latency (Line Chart) - `avg(latency_ms)`
- **Panel 2**: P95 Interaction Latency (Stat) - `quantile(0.95, latency_ms)`
- **Panel 3**: Daily Active Users (Stat) - `count(distinct user_email)`
- **Panel 4**: Interactions per User (Histogram) - `count() by (user_email)`

### 5. Error Monitoring Dashboard
- **Panel 1**: Feedback Failures Over Time (Line Chart) - `count() where type = 'feedback_failure'`
- **Panel 2**: Failures by Feedback Node (Bar Chart) - `count() by (feedback_node)`
- **Panel 3**: API Errors by Service (Table) - `count() by (service, error_message) where success = false`
- **Panel 4**: Top Failure Reasons (Table) - `count() by (reason)`

---

## Time Series Queries

All logs have a `timestamp` field in ISO 8601 format. Use this for time-based aggregations:

```
# Hourly API calls
count() by (service, hour(timestamp))

# Daily interaction count
count() by (date(timestamp))

# Average latency per hour
avg(latency_ms) by (hour(timestamp))
```

---

## Filtering Examples

### By User
```
user_email = 'mahmoudchaerps@gmail.com'
```

### By Session
```
session_id = 'efbd5f6d-6ba1-401d-9d47-e533d8d58bfb'
```

### By Date Range
```
timestamp >= '2025-11-27T00:00:00Z' AND timestamp < '2025-11-28T00:00:00Z'
```

### By Service
```
service IN ('flights', 'hotels')
```

### By Node
```
node_name = 'flight_agent'
```

---

## Alerting Rules

### High API Error Rate
```
count(success = false) / count(*) > 0.1
Alert when: Error rate > 10%
```

### Slow API Calls
```
avg(response_time_ms) > 5000
Alert when: Average response time > 5 seconds
```

### High LLM Latency
```
avg(latency_ms) by (agent_name) > 10000
Alert when: Any agent has average latency > 10 seconds
```

### High Feedback Failure Rate
```
count(type = 'feedback_failure') / count(type = 'node_exit') > 0.2
Alert when: Feedback failure rate > 20%
```

### High Token Usage
```
sum(token_usage.total_tokens) > 1000000
Alert when: Daily token usage > 1M tokens
```

---

## Data Retention

Consider setting up retention policies:
- **API Logs**: 90 days
- **Node Logs**: 30 days
- **Interaction Logs**: 90 days
- **LLM Call Logs**: 30 days (can be expensive to store)
- **Feedback Failures**: 90 days (important for debugging)

---

## Cost Optimization

1. **Sample LLM logs**: Only store full logs for high-value queries
2. **Aggregate old data**: Convert detailed logs to aggregated metrics after 7 days
3. **Archive cold data**: Move logs older than 30 days to cold storage
4. **Index optimization**: Index on `timestamp`, `service`, `node_name`, `agent_name` for faster queries

