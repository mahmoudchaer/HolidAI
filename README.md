# HolidAI - Travel Assistant

Multi-agent travel assistant using LangGraph orchestration.

## Architecture

- **Orchestrator (Main Agent)**: Routes queries to specialized agents and accumulates information
- **Specialized Agents**: Flight, Hotel, Visa, TripAdvisor, Utilities (weather, currency, date/time)
- **Conversational Agent**: Generates final user response from collected information

## Setup

1. Install dependencies:
```bash
pip install -r mcp_system/requirements.txt
pip install -r langraph/requirements.txt
pip install -r frontend/requirements.txt
```

2. Set up `.env` file with `OPENAI_API_KEY`

3. Start PostgreSQL database (for authentication):
```bash
docker-compose up -d
```

4. Start MCP server (in one terminal):
```bash
cd mcp_system/server
python main_server.py
```

5. Start UI (in another terminal):
```bash
cd frontend
python app.py
```

6. Open browser to `http://localhost:5000`
   - Main app: `http://localhost:5000`
   - Sign up: `http://localhost:5000/signup`
   - Log in: `http://localhost:5000/login`

