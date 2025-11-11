# HolidAI - Travel Assistant

Multi-agent travel assistant using LangGraph orchestration.

## Architecture

- **Orchestrator (Main Agent)**: Routes queries to specialized agents and accumulates information
- **Specialized Agents**: Flight, Hotel, Visa, TripAdvisor
- **Conversational Agent**: Generates final user response from collected information

## Setup

1. Install dependencies:
```bash
pip install -r langraph/requirements.txt
pip install -r frontend/requirements.txt
```

2. Set up `.env` file with `OPENAI_API_KEY`

3. Start MCP server (if not running):
```bash
cd mcp_system/server
python main_server.py
```

4. Start UI:
```bash
cd frontend
python app.py
```

5. Open browser to `http://localhost:5000`

