"""FastAPI application entry point"""
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

# Load environment variables first
load_dotenv()

from .config import settings
from .routers import chat, outputs, websocket

# Create FastAPI app
app = FastAPI(
    title="Flood Agent API",
    description="Real-time flood detection with multi-agent system",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins + ["*"],  # Allow all for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router)
app.include_router(outputs.router)
app.include_router(websocket.router)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "flood-agent-api",
        "version": "1.0.0"
    }


@app.get("/api/config")
async def get_config():
    """Get server configuration"""
    return {
        "host": settings.host,
        "port": settings.port,
        "ws_endpoint": f"ws://{settings.host}:{settings.port}/ws/{{session_id}}"
    }


# Serve frontend static files
# This must be last to not override API routes
if settings.frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(settings.frontend_dir), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
