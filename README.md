# HolidAI ✈️

<div align="center">

**An intelligent multi-agent travel planning assistant powered by LangGraph**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18.3+-61dafb.svg)](https://reactjs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-green.svg)](https://langchain-ai.github.io/langgraph/)

</div>

---

## 📖 Overview

HolidAI is a sophisticated travel planning platform that leverages multiple specialized AI agents to help users plan comprehensive trips. The system orchestrates various agents—each specialized in different aspects of travel planning—to provide seamless flight bookings, hotel reservations, visa information, restaurant recommendations, and travel utilities.

Built with **LangGraph** for intelligent agent orchestration and featuring a modern React frontend, HolidAI delivers a conversational, user-friendly experience for planning your next adventure.

## ✨ Features

- 🤖 **Multi-Agent Architecture**: Specialized agents for flights, hotels, visas, restaurants, and utilities
- 🧠 **Intelligent Orchestration**: LangGraph-based workflow management for coordinated agent interactions
- 💬 **Conversational Interface**: Natural language interaction with real-time agent status updates
- 🔒 **Privacy-First**: Built-in PII (Personally Identifiable Information) redaction for data protection
- 🧩 **Memory System**: Long-term and short-term memory capabilities for personalized recommendations
- 🎨 **Modern UI**: Beautiful, responsive React frontend with Tailwind CSS
- 🐳 **Dockerized**: Complete containerized setup for easy deployment
- 📊 **Vector Search**: Qdrant integration for semantic search and memory retrieval
- 🔄 **Real-time Updates**: WebSocket-based communication for live agent status

## 🏗️ Architecture

HolidAI follows a microservices architecture with the following components:

```
┌─────────────┐
│   Frontend  │  React + Vite + Tailwind CSS
│  (Port 5000)│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  LangGraph  │  Agent Orchestration Engine
│  Orchestrator│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  MCP System │  Model Context Protocol Server
│ (Port 8090) │
└──────┬──────┘
       │
       ├──► PostgreSQL (Port 5437) - Relational Data
       ├──► Qdrant (Port 6333) - Vector Database
       └──► Redis (Port 6379) - Caching & Sessions
```

### Agent Types

- **Main Agent**: Coordinates overall conversation flow
- **Planner Agent**: Creates and refines travel plans
- **Flight Agent**: Handles flight searches and bookings
- **Hotel Agent**: Manages hotel searches and reservations
- **Visa Agent**: Provides visa requirements and information
- **TripAdvisor Agent**: Restaurant and activity recommendations
- **Utilities Agent**: Travel utilities and general assistance
- **Memory Agent**: Manages user preferences and history
- **Conversational Agent**: Handles general conversation

## 🛠️ Tech Stack

### Frontend
- **React 18.3+** - UI framework
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Utility-first CSS framework
- **Zustand** - State management
- **Framer Motion** - Animation library
- **Socket.io Client** - Real-time communication
- **React Router** - Navigation

### Backend
- **Python 3.8+** - Core language
- **LangGraph** - Agent orchestration
- **LangChain** - LLM framework
- **OpenAI API** - Language models
- **Presidio** - PII detection and redaction

### Infrastructure
- **PostgreSQL 16** - Primary database
- **Qdrant** - Vector database for embeddings
- **Redis 7** - Caching and session storage
- **Docker Compose** - Container orchestration

## 🚀 Getting Started

### Prerequisites

- [Docker](https://www.docker.com/get-started) and Docker Compose
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/HolidAI.git
   cd HolidAI
   ```

2. **Create environment file**
   
   Create a `.env` file in the project root with the following required environment variables:
   ```env
   # API Keys
   OPENAI_API_KEY=your_openai_api_key_here
   LITEAPI_KEY=your_liteapi_key_here
   TRIPADVISOR_KEY=your_tripadvisor_key_here
   SERPAPI_KEY=your_serpapi_key_here
   CALENDARIFIC_API_KEY=your_calendarific_api_key_here
   
   # Azure Blob Storage (for logging)
   AZURE_BLOB_CONNECTION_STRING=your_azure_blob_connection_string
   AZURE_BLOB_ACCOUNT_NAME=holidailogs
   AZURE_BLOB_CONTAINER=holidai-logs
   
   # Email Configuration
   EMAIL_USER=your_email@gmail.com
   EMAIL_PASS=your_email_app_password
   ```

3. **Start the application**
   ```bash
   docker compose up -d
   ```

   This will start all services:
   - PostgreSQL database
   - Qdrant vector database
   - Redis cache
   - MCP system server
   - Frontend application

4. **Access the application**
   
   Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

### Verify Services

Check that all services are running:
```bash
docker compose ps
```

All services should show as "healthy" or "running".

### 📊 Grafana Logging (Optional)

For monitoring and analytics, set up Grafana with Azure Blob Storage:

1. Navigate to the `grafana` folder and create a `.env` file:
   ```env
   AZURE_BLOB_CONNECTION_STRING=your_azure_blob_connection_string
   AZURE_BLOB_ACCOUNT_NAME=holidailogs
   AZURE_BLOB_CONTAINER=holidai-logs
   ```

2. Start Grafana services:
   ```bash
   cd grafana
   docker compose up -d
   ```

3. Access Grafana at `http://localhost:3000` (admin/admin)

## 📝 Usage

1. **Start a conversation**: Enter your travel requirements in natural language
2. **Agent coordination**: Watch as specialized agents work together to plan your trip
3. **Real-time updates**: Monitor agent status and progress in real-time
4. **Review plans**: View and refine your travel itinerary
5. **Book services**: Complete bookings through integrated agent workflows

### Example Queries

- "I want to plan a trip to Paris for 5 days in June"
- "Find me flights from New York to Tokyo and hotels near Shibuya"
- "What are the visa requirements for traveling to Brazil?"
- "Recommend restaurants in Rome near the Colosseum"

## 🧪 Development

### Running Tests

```bash
# Run MCP system tests
cd mcp_system/test
python run_all_tests.py

# Run LangGraph tests
cd langraph/test
python test_langraph.py
```

### Project Structure

```
HolidAI/
├── frontend/          # React frontend application
├── langraph/          # LangGraph orchestration engine
├── mcp_system/        # Model Context Protocol server
├── memory/            # Memory management system
├── stm/               # Short-term memory
├── database/          # Database utilities
└── docker-compose.yml # Container orchestration
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [LangGraph](https://langchain-ai.github.io/langgraph/) for agent orchestration
- [LangChain](https://www.langchain.com/) for LLM framework
- [OpenAI](https://openai.com/) for language models
- [Qdrant](https://qdrant.tech/) for vector database
- All the open-source contributors and libraries that made this project possible

## 📧 Contact

For questions, suggestions, or support, please open an issue on GitHub.

---

<div align="center">

Made with ❤️ by the HolidAI team

**Happy Travels! ✈️🌍**

</div>
