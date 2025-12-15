"""API request/response models"""
from pydantic import BaseModel, Field
from typing import Optional, Literal, Any
from datetime import datetime


# Chat API models
class ChatMessage(BaseModel):
    """User chat message"""
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat API response"""
    session_id: str
    status: Literal["started", "error"]
    message: str


# WebSocket event models
class AgentThought(BaseModel):
    """Agent reasoning event"""
    type: Literal["agent_thought"] = "agent_thought"
    timestamp: datetime
    agent_name: str  # "FloodAnalysisOrchestrator", "DataCollectionAgent", etc.
    thought: str
    reasoning: Optional[str] = None


class ToolExecution(BaseModel):
    """Tool execution event"""
    type: Literal["tool_start", "tool_progress", "tool_complete", "tool_error"]
    timestamp: datetime
    tool_name: str  # "search_sentinel_images", "segment_flood_area", etc.
    status: str
    progress: Optional[float] = None  # 0-100 for progress bar
    result: Optional[Any] = None
    error: Optional[str] = None


class DataUpdate(BaseModel):
    """New data available event"""
    type: Literal["image_ready", "gauge_data", "analysis_complete"]
    timestamp: datetime
    run_id: str
    data: dict  # Image paths, gauge readings, etc.


class AgentComplete(BaseModel):
    """Agent execution complete"""
    type: Literal["complete"]
    timestamp: datetime
    session_id: str
    final_message: str


class AgentError(BaseModel):
    """Agent execution error"""
    type: Literal["error"]
    timestamp: datetime
    session_id: str
    error: str
