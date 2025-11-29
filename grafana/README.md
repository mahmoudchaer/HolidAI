# HolidAI Logs & Metrics Dashboard

A comprehensive Docker-based solution for visualizing HolidAI application logs and metrics using Grafana and InfluxDB.

## Overview

This project provides:
- **Grafana Dashboard**: Beautiful, comprehensive dashboards for visualizing all HolidAI metrics
- **InfluxDB**: Time-series database for storing metrics
- **Log Ingester**: Python service that reads logs from Azure Blob Storage and writes metrics to InfluxDB

## Features

### Metrics Tracked

1. **Log Volume Metrics**
   - Logs received per hour
   - Logs received per day

2. **API Performance Metrics**
   - API response time (average by service)
   - API success rate
   - API calls per service
   - API errors by service

3. **Node/Agent Performance Metrics**
   - Node execution latency (average)
   - Slowest nodes (P95 latency)
   - Node execution count

4. **User Experience Metrics**
   - Interaction latency (average)
   - P95 interaction latency
   - Daily active users

5. **LLM Usage Metrics**
   - Token usage over time
   - Token usage by agent
   - LLM latency by agent
   - LLM calls per agent

6. **Error Monitoring**
   - Feedback failures over time
   - Failures by feedback node
   - API errors by service

## Prerequisites

- Docker and Docker Compose installed
- Azure Blob Storage account with logs
- Azure Blob Storage connection string

## Quick Start

1. **Clone or navigate to this directory**

2. **Set up environment variables**

   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your Azure Blob Storage connection string:
   ```bash
   AZURE_BLOB_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=holidailogs;AccountKey=YOUR_KEY_HERE;EndpointSuffix=core.windows.net
   ```

3. **Start the services**

   ```bash
   docker-compose up -d
   ```

   This will start:
   - InfluxDB on port 8086
   - Grafana on port 3000
   - Log ingester service

4. **Access Grafana**

   - Open your browser to `http://localhost:3000`
   - Login with:
     - Username: `admin`
     - Password: `admin`
   - The dashboard "HolidAI Logs & Metrics Dashboard" should be automatically loaded

5. **Initialize InfluxDB (First Time Only)**

   When you first start InfluxDB, you need to set it up:
   - Go to `http://localhost:8086`
   - Create an organization: `holidai`
   - Create a bucket: `holidai-logs`
   - Create an admin token and update it in `.env` and `docker-compose.yml`

   **OR** use the default setup (already configured in docker-compose.yml):
   - Organization: `holidai`
   - Bucket: `holidai-logs`
   - Token: `holidai-admin-token-change-in-production` (change this in production!)

## Architecture

```
Azure Blob Storage (Logs)
    ↓
Log Ingester Service (Python)
    ↓
InfluxDB (Time-series Database)
    ↓
Grafana (Visualization)
```

### Components

1. **Log Ingester** (`log_ingester/`)
   - Reads JSON log files from Azure Blob Storage
   - Processes logs and extracts metrics
   - Writes metrics to InfluxDB
   - Runs continuously, scanning for new logs every 60 seconds (configurable)

2. **InfluxDB**
   - Stores all metrics as time-series data
   - Provides Flux query language for Grafana

3. **Grafana**
   - Pre-configured dashboards
   - Auto-provisioned data source connection to InfluxDB
   - 18 panels showing various metrics

## Configuration

### Environment Variables

Edit `.env` file to configure:

- `AZURE_BLOB_CONNECTION_STRING`: Your Azure Blob Storage connection string
- `AZURE_BLOB_ACCOUNT_NAME`: Storage account name (default: `holidailogs`)
- `AZURE_BLOB_CONTAINER`: Container name (default: `holidai-logs`)
- `INGEST_INTERVAL`: How often to scan for new logs in seconds (default: `60`)

### InfluxDB Setup

The default InfluxDB configuration in `docker-compose.yml`:
- Username: `admin`
- Password: `adminpassword`
- Organization: `holidai`
- Bucket: `holidai-logs`
- Token: `holidai-admin-token-change-in-production`

**⚠️ IMPORTANT**: Change these values in production!

### Grafana Configuration

- Default login: `admin` / `admin`
- Dashboard is auto-provisioned from `grafana/dashboards/`
- Data source is auto-configured from `grafana/provisioning/datasources/`

## Dashboard Panels

The dashboard includes 18 panels:

1. **Logs Received Per Hour** - Time series
2. **Logs Received Per Day** - Time series
3. **API Response Time (Average by Service)** - Time series
4. **API Success Rate** - Gauge
5. **API Calls per Service** - Bar gauge
6. **Node Execution Latency (Average)** - Time series
7. **Slowest Nodes (P95 Latency)** - Bar gauge
8. **Interaction Latency (Average)** - Time series
9. **P95 Interaction Latency** - Stat
10. **Daily Active Users** - Stat
11. **LLM Token Usage Over Time** - Time series
12. **Token Usage by Agent** - Pie chart
13. **LLM Latency by Agent** - Time series
14. **Feedback Failures Over Time** - Time series
15. **Failures by Feedback Node** - Bar gauge
16. **API Errors by Service** - Table
17. **Node Execution Count** - Table
18. **LLM Calls per Agent** - Table

## Log Types Supported

The ingester processes the following log types from Azure Blob Storage:

1. **API Calls** (`api/{service}/{date}/log_*.json`)
   - Response time, success rate, errors

2. **Node Executions** (`agent/nodes/{node_name}/{date}/exit_*.json`)
   - Node latency, execution count

3. **Interactions** (`agent/interactions/{date}/session_{session_id}/log_*.json`)
   - Interaction latency, user activity

4. **Feedback Failures** (`agent/feedback_failures/{date}/log_*.json`)
   - Failure counts, failure reasons

5. **LLM Calls** (`agent/llm_calls/{agent_name}/{date}/log_*.json`)
   - Token usage, latency, call counts

## Troubleshooting

### Logs not appearing in Grafana

1. Check if the log ingester is running:
   ```bash
   docker-compose logs log-ingester
   ```

2. Verify Azure Blob Storage connection:
   - Check `.env` file has correct `AZURE_BLOB_CONNECTION_STRING`
   - Verify the connection string format

3. Check InfluxDB connection:
   ```bash
   docker-compose logs influxdb
   ```

4. Verify logs exist in Azure Blob Storage:
   - Check that log files exist in the container
   - Verify file naming matches expected patterns

### InfluxDB connection issues

1. Make sure InfluxDB is healthy:
   ```bash
   docker-compose ps
   ```

2. Check InfluxDB logs:
   ```bash
   docker-compose logs influxdb
   ```

3. Verify token matches in:
   - `.env` file
   - `docker-compose.yml`
   - `grafana/provisioning/datasources/influxdb.yml`

### Grafana not loading dashboard

1. Check Grafana logs:
   ```bash
   docker-compose logs grafana
   ```

2. Verify dashboard file exists:
   ```bash
   ls grafana/dashboards/
   ```

3. Check data source configuration:
   - Go to Grafana UI → Configuration → Data Sources
   - Verify InfluxDB connection is working

## Development

### Modifying the Dashboard

1. Edit `grafana/dashboards/holidai-logs-dashboard.json`
2. Restart Grafana: `docker-compose restart grafana`
3. Or edit directly in Grafana UI (changes persist in volume)

### Adding New Metrics

1. Modify `log_ingester/log_processor.py` to process new log types
2. Add new panels to the dashboard JSON
3. Restart services: `docker-compose restart`

### Testing Locally

1. Start services: `docker-compose up`
2. Check ingester logs: `docker-compose logs -f log-ingester`
3. Verify data in InfluxDB UI: `http://localhost:8086`

## Data Retention

Consider setting up retention policies in InfluxDB:
- API Logs: 90 days
- Node Logs: 30 days
- Interaction Logs: 90 days
- LLM Call Logs: 30 days
- Feedback Failures: 90 days

## Security Notes

⚠️ **Production Deployment**:

1. Change all default passwords and tokens
2. Use secrets management for sensitive credentials
3. Enable authentication in Grafana
4. Use HTTPS for Grafana
5. Restrict network access to services
6. Set up proper InfluxDB authentication

## Stopping Services

```bash
docker-compose down
```

To remove volumes (deletes all data):
```bash
docker-compose down -v
```

## Support

For issues or questions, refer to:
- `LOGGING_DOCUMENTATION.md` - Log structure documentation
- `GRAFANA_METRICS_REFERENCE.md` - Metrics reference guide

## License

This project is part of the HolidAI logging infrastructure.

