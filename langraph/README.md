# LangGraph Orchestration Layer

LangGraph orchestration layer for multi-agent travel system.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

### 3. Run MCP Server

**Start MCP Server (includes all tools including delegate):**
```bash
cd ../mcp_system
python server/main_server.py
```

### 4. Run Tests

```bash
python test/test_langraph.py
```

## Architecture

- **MainAgent**: Orchestrator that reasons and delegates tasks
- **HotelAgent**: Specialized agent for hotel-related operations
- **State Management**: Shared state with routing control

## Structure

```
langraph/
├── nodes/
│   └── main_agent_node.py      # Main Agent LangGraph node
├── state.py                     # Shared state definition
├── graph.py                     # LangGraph orchestration
├── main.py                      # Interactive CLI entry point
└── test/
    └── test_langraph.py         # Tests
```

**MCP System Components:**
- `mcp_system/clients/main_agent_client.py` - Main Agent MCP client
- `mcp_system/tools/coordinator_tools.py` - Delegate tool
- `mcp_system/server/main_server.py` - Main MCP server (registers all tools)
```

