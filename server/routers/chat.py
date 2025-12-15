"""Chat API endpoints"""
from fastapi import APIRouter, HTTPException
from pathlib import Path
import asyncio

from ..models import ChatMessage, ChatResponse
from ..session_manager import session_manager
from ..adk_wrapper import ADKEventCapture
from ..websocket_manager import ws_manager
from ..config import settings

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Create ADK event capture instance
adk_capture = ADKEventCapture(ws_manager, settings.outputs_dir)


@router.post("/message", response_model=ChatResponse)
async def send_message(msg: ChatMessage):
    """
    Send a chat message and start agent execution.

    The agent runs in the background and streams updates via WebSocket.
    """
    try:
        # Get or create session
        session = await session_manager.get_or_create_session(
            session_id=msg.session_id,
            user_id="web_user"
        )

        # Get our session_id (might be newly created)
        our_session_id = msg.session_id
        if not our_session_id:
            # Find our session_id by ADK session
            our_session_id = session_manager.get_session_id_by_adk_session(session.id)

        if not our_session_id:
            # Fallback: use ADK session id
            our_session_id = session.id

        # Start agent execution as an async task (not background task)
        asyncio.create_task(
            run_agent_background(
                session_id=session.id,
                our_session_id=our_session_id,
                message=msg.message
            )
        )

        return ChatResponse(
            session_id=our_session_id,
            status="started",
            message="Agent is processing your request..."
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def run_agent_background(session_id: str, our_session_id: str, message: str):
    """Run agent and broadcast events"""
    import os
    from dotenv import load_dotenv
    from google.adk.runners import Runner
    from agents import root_agent  # Import from flood_agent/agents

    # Ensure environment variables are loaded
    load_dotenv()

    # Verify API key is available
    if not os.getenv('GEMINI_API_KEY'):
        raise ValueError("GEMINI_API_KEY not found in environment")

    runner = Runner(
        app_name="flood_detection_web",
        agent=root_agent,
        session_service=session_manager.adk_session_service
    )

    try:
        # Run the agent - events are broadcast via WebSocket internally
        await adk_capture.run_agent(
            runner=runner,
            session_id=session_id,
            user_id="web_user",
            message=message,
            ws_session_id=our_session_id  # Pass the frontend session ID for WebSocket broadcasting
        )

    except Exception as e:
        # Error is already broadcast by adk_capture
        print(f"Agent error: {e}")
        import traceback
        traceback.print_exc()


@router.get("/sessions/{session_id}/status")
async def get_session_status(session_id: str):
    """Get session status"""
    session = session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "adk_session_id": session.id,
        "active": True,
        "ws_connections": ws_manager.get_connection_count(session_id)
    }
