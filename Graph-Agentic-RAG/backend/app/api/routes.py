"""API routes for the Graph RAG Agent."""
import json
import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.api.models import ChatRequest, ChatResponse
from app.services.document_processor import processor
from app.services.graph_builder import graph_builder
from app.services.project_manager import project_manager
from app.services.agent import invoke_agent


router = APIRouter()


def get_current_graph():
    """Get current project's graph."""
    graph = project_manager.get_current_project()
    if graph is None:
        raise HTTPException(status_code=400, detail="请先选择或创建一个项目")
    return graph


# File upload endpoint
@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a document file (PDF, DOC, DOCX, or TXT)."""
    # Check if project is selected
    graph = get_current_graph()
    if not graph:
        raise HTTPException(status_code=400, detail="请先选择或创建一个项目")

    # Validate file extension
    ext = file.filename.split('.')[-1].lower()
    if ext not in ["pdf", "doc", "docx", "txt"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Only PDF, DOC, DOCX, and TXT files are supported."
        )

    try:
        # Read file content
        content = await file.read()

        # Save file
        file_path = processor.save_uploaded_file(content, file.filename)

        # Build knowledge graph
        def progress_callback(current: int, total: int, message: str):
            print(f"Progress: {message}")

        graph_data = await graph_builder.build_graph_from_file(
            file_path,
            file.filename,
            progress_callback
        )

        return {
            "success": True,
            "file_name": file.filename,
            "message": f"Successfully processed {file.filename}",
            "graph_stats": graph.get_statistics()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


# Chat endpoints
@router.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a chat message to the agent."""
    try:
        from langchain_core.messages import HumanMessage, AIMessage
        history = []
        if request.history:
            for msg in request.history:
                if msg.get("role") == "user":
                    history.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    history.append(AIMessage(content=msg.get("content", "")))

        # Get response from agent
        result = await invoke_agent(request.message, history)

        return {
            "response": result["response"],
            "used_graph": result.get("used_graph", False),
            "retrieved_entities": result.get("retrieved_entities", []),
            "retrieval_chain": result.get("retrieval_chain", []),
            "route_decision": result.get("route_decision", "")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


async def _chunk_text(text: str, chunk_size: int = 30):
    """Split text into chunks for streaming."""
    import re
    if not text:
        return

    # Split by sentences
    sentences = re.split(r'(?<=[。！？.!?])\s*', text)
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) > chunk_size:
            if current_chunk:
                yield current_chunk
            current_chunk = sentence
        else:
            current_chunk += sentence

    if current_chunk:
        yield current_chunk


async def stream_chat_endpoint(question: str, history_data: list):
    """Stream chat response using SSE."""
    from langchain_core.messages import HumanMessage, AIMessage

    # Convert history
    history = []
    for msg in history_data:
        if msg.get("role") == "user":
            history.append(HumanMessage(content=msg.get("content", "")))
        elif msg.get("role") == "assistant":
            history.append(AIMessage(content=msg.get("content", "")))

    try:
        # Run agent to get full response with retrieval info
        result = await invoke_agent(question, history)
        response_text = result.get("response", "")
        used_graph = result.get("used_graph", False)
        retrieved_entities = result.get("retrieved_entities", [])
        retrieval_chain = result.get("retrieval_chain", [])

        # Stream response text chunks
        async for chunk in _chunk_text(response_text, 30):
            yield chunk
            await asyncio.sleep(0.05)  # Small delay for streaming effect

        # Send completion with retrieval info as JSON
        import json
        complete_data = json.dumps({
            "response": response_text,
            "used_graph": used_graph,
            "retrieved_entities": retrieved_entities,
            "retrieval_chain": retrieval_chain
        })
        yield f"[COMPLETE]{complete_data}"

    except Exception as e:
        yield f"[ERROR]{str(e)}"


# SSE streaming chat endpoint
@router.get("/chat/stream")
async def stream_chat(question: str, history: str = "[]"):
    """SSE endpoint for streaming chat."""
    import json
    try:
        history_data = json.loads(history)
    except:
        history_data = []

    return EventSourceResponse(
        stream_chat_endpoint(question, history_data),
        media_type="text/event-stream"
    )
