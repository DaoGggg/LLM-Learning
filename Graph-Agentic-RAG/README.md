# Graph RAG Agent System

A knowledge graph-based conversation agent system with document upload, graph visualization, and intelligent chat capabilities.

## Features

- **Document Upload**: Support for PDF, DOC, and DOCX files
- **Knowledge Graph Construction**: Automatic entity and relation extraction using LLM
- **Graph Visualization**: Interactive visualization with ECharts
- **Intelligent Chat**: LangGraph-based agent that decides when to use knowledge graph
- **Simple UI**: Clean and intuitive interface

## Tech Stack

- **Backend**: Python, FastAPI, LangChain, LangGraph v1.0
- **Database**: NetworkX (in-memory graph storage)
- **LLM**: MiniMax API
- **Frontend**: Plain HTML/JS, ECharts

## Project Structure

```
Graph-Agentic-RAG/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── config.py         # Configuration
│   │   ├── api/
│   │   │   ├── routes.py     # API endpoints
│   │   │   └── models.py     # Pydantic models
│   │   ├── services/
│   │   │   ├── document_processor.py  # PDF/DOC processing
│   │   │   ├── graph_builder.py       # Graph construction
│   │   │   ├── graph_manager.py       # NetworkX management
│   │   │   ├── llm_service.py         # LLM API calls
│   │   │   └── agent.py               # LangGraph agent
│   │   └── utils/
│   │       └── prompts.py    # Prompt templates
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── api.js
│       ├── chat.js
│       └── graph.js
├── data/uploads/
└── README.md
```

## Installation

1. Clone the repository
2. Install backend dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your MiniMax API key
   ```

## Usage

1. Start the backend server:
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

2. Open frontend in browser:
   - Open `frontend/index.html` in a web browser
   - Or use a simple HTTP server:
     ```bash
     cd frontend
     python -m http.server 8080
     ```
   - Then visit `http://localhost:8080`

3. Usage flow:
   - Upload a PDF or DOCX document
   - Wait for knowledge graph construction
   - View the graph visualization
   - Chat with the agent about the document

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload` | POST | Upload document file |
| `/api/graph` | GET | Get graph data |
| `/api/graph/stats` | GET | Get graph statistics |
| `/api/graph/entity/search` | GET | Search entities |
| `/api/chat` | POST | Send chat message |
| `/api/chat/stream` | WebSocket | Stream chat response |

## Configuration

Edit `backend/.env` to configure:

```env
MINIMAX_API_KEY=your_api_key
MINIMAX_API_URL=https://api.minimax.chat/v1/text/chatcompletion_v2
MINIMAX_MODEL=abab6.5s-chat
HOST=0.0.0.0
PORT=8000
```
