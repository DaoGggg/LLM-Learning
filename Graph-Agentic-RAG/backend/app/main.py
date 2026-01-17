"""FastAPI application entry point."""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.config import HOST, PORT, UPLOAD_DIR, BASE_DIR
from app.api.routes import router as api_router
from app.api.project_routes import router as project_router


# Calculate frontend path
FRONTEND_DIR = BASE_DIR.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print(f"Server starting on {HOST}:{PORT}")
    print(f"Upload directory: {UPLOAD_DIR}")
    print(f"Frontend directory: {FRONTEND_DIR}")
    yield
    # Shutdown
    print("Server shutting down")


# Create FastAPI app
app = FastAPI(
    title="Graph RAG Agent API",
    description="A Graph RAG conversation agent with knowledge graph visualization",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes - project_routes first for proper routing
app.include_router(project_router, prefix="/api")
app.include_router(api_router, prefix="/api")


# Serve frontend static files
app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
app.mount("/lib", StaticFiles(directory=str(FRONTEND_DIR / "lib")), name="lib")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Graph RAG Agent"}


# Catch-all route for SPA - must be last
@app.get("/{full_path:path}")
async def serve_frontend(request: Request, full_path: str):
    """Serve the frontend index.html for all non-API routes."""
    # Skip API routes
    if full_path.startswith("api/"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")

    # Serve index.html for root and other paths
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    raise HTTPException(status_code=404, detail="Frontend not found")
