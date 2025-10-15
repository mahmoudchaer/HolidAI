# 🏨 HotelPlanner

AI-powered hotel search agent with LangGraph + Claude + SerpApi.

## Quick Start

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Create `.env` file with your API keys:**
```
SERPAPI_KEY=your_serpapi_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```
- SerpApi: https://serpapi.com/
- Anthropic: https://console.anthropic.com/

3. **Run the web app:**
```bash
python app.py
```

4. **Open browser:** http://localhost:5000

## Features

- 🤖 Claude-powered conversational agent
- 🔍 Real hotel search via SerpApi
- 🎯 Smart filtering and sorting
- 💰 Budget calculations
- 🗺️ Nearby attractions
- 💬 Chat interface
- 💾 Session memory

## Files

- `app.py` - Flask web server
- `agent.py` - LangGraph ReAct agent
- `tools/` - Hotel search tools
- `templates/chat.html` - Chat UI
- `static/` - CSS/JS

