"""WebSocket endpoint for real-time updates"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..websocket_manager import ws_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket connection for real-time agent updates.

    Receives events:
    - agent_thought: Agent reasoning
    - tool_start/progress/complete: Tool execution
    - image_ready: New images available
    - gauge_data: Gauge readings
    - complete: Agent finished
    """
    await ws_manager.connect(websocket, session_id)

    try:
        # Keep connection alive and listen for client messages
        while True:
            data = await websocket.receive_json()

            # Handle client messages (e.g., heartbeat, subscription updates)
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, session_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket, session_id)


@router.get("/ws/stats")
async def websocket_stats():
    """Get WebSocket connection statistics"""
    return {
        "total_connections": ws_manager.get_connection_count(),
        "sessions": len(ws_manager.active_connections)
    }
