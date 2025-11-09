# Travel Agent MCP System

MCP (Model Context Protocol) layer for the travel agent project. Provides a centralized tool server with per-agent access control.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the MCP Server

```bash
cd mcp_system
python server/main_server.py
```

The server will start on `http://localhost:8090`.

### 3. Test the System

In a separate terminal, you can run tests in different ways:

**Run all tests:**
```bash
cd mcp_system
python test/run_all_tests.py
```

**Run individual client tests:**
```bash
cd mcp_system
python test/test_hotel_agent.py
python test/test_permissions.py
```

**Or use the original combined test:**
```bash
cd mcp_system
python test_agents.py
```

## Structure

```
mcp_system/
├── server/
│   └── main_server.py       # MCP server hosting all tools
├── tools/
│   ├── hotel_tools.py       # Hotel-related tools
│   └── doc_loader.py        # Load tool documentation from JSON
├── tool_docs/
│   ├── hotel_docs.json      # Hotel tool metadata
│   └── README.md            # Documentation on tool metadata format
├── clients/
│   ├── base_client.py       # Base client with permission control
│   └── hotel_agent_client.py
├── test/
│   ├── test_hotel_agent.py  # Hotel agent tests
│   ├── test_permissions.py  # Permission enforcement tests
│   └── run_all_tests.py     # Run all tests
├── test_agents.py            # Original combined test script
└── requirements.txt
```

## Adding New Tools

1. **Create the tool documentation** in `tool_docs/`:
   - Add entries to existing JSON files (e.g., `hotel_docs.json`) or create a new one
   - See `tool_docs/README.md` for the JSON format

2. **Create the tool function** in `tools/` (e.g., `tools/payment_tools.py`):
   ```python
   from tools.doc_loader import get_doc
   
   def register_payment_tools(mcp):
       @mcp.tool(description=get_doc("process_payment", "payment"))
       def process_payment(amount: float, currency: str) -> dict:
           # Implementation here
           return {"status": "success", "amount": amount}
   ```

3. **Import and register** in `server/main_server.py`:
   ```python
   from tools.payment_tools import register_payment_tools
   
   register_payment_tools(mcp)
   ```

**Note:** Tool descriptions are loaded from JSON files, not from docstrings. See `tool_docs/README.md` for details.

## Adding New Agents

1. Create a client file in `clients/` (e.g., `clients/payment_agent_client.py`):

```python
from clients.base_client import BaseAgentClient

PaymentAgentClient = BaseAgentClient(
    name="PaymentAgent",
    allowed_tools=["process_payment", "refund_payment"]
)
```

2. Import in `test_agents.py` to test.

## API Endpoints

- `GET /` - Server status
- `GET /tools/list` - List all available tools
- `GET /tools/metadata` - Get detailed tool metadata
- `POST /tools/invoke` - Invoke a tool (requires `{"tool": "name", "parameters": {...}}`)

## Features

- **Data-driven tool metadata**: Tool descriptions, inputs, outputs, and examples stored in JSON files
- **Auto-generated tool schemas**: Input/output schemas generated from function signatures
- **Per-agent tool access control**: Each agent client restricted to its allowed tools
- **Async communication**: HTTP-based async client-server communication
- **Extensible architecture**: Easy to add new tools or agents following the same pattern

## Tool Documentation

Tool metadata (descriptions, inputs, outputs, examples) is stored in JSON files in `tool_docs/`:
- Edit `tool_docs/*_docs.json` to update tool descriptions
- See `tool_docs/README.md` for format details and how to add new tools

