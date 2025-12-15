"""WebSocket connection manager for real-time updates"""
import asyncio
import json
from typing import Dict
from fastapi import WebSocket
from datetime import datetime


class WebSocketManager:
    """
    Manages WebSocket connections for real-time agent updates.

    Supports:
    - Per-session subscriptions
    - Broadcast to all clients in a session
    - Connection cleanup
    """

    def __init__(self):
        # session_id -> list of websockets
        self.active_connections: Dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()

        async with self._lock:
            if session_id not in self.active_connections:
                self.active_connections[session_id] = []

            self.active_connections[session_id].append(websocket)

        # Send connection acknowledgment
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat()
        })

    def disconnect(self, websocket: WebSocket, session_id: str):
        """Remove a WebSocket connection"""
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)

            # Clean up empty sessions
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def broadcast(self, session_id: str, message: dict):
        """
        Broadcast a message to all clients in a session.

        Args:
            session_id: Session to broadcast to
            message: Event dictionary to send
        """
        if session_id not in self.active_connections:
            print(f"[WS Manager] No connections for session {session_id}")
            return

        print(f"[WS Manager] Broadcasting to {len(self.active_connections[session_id])} client(s)")
        print(f"[WS Manager] Message type: {message.get('type')}")

        dead_connections = []

        for websocket in self.active_connections[session_id]:
            try:
                await websocket.send_json(message)
                print(f"[WS Manager] Message sent successfully")
            except Exception as e:
                print(f"[WS Manager] Error sending message: {e}")
                dead_connections.append(websocket)

        # Clean up dead connections
        for websocket in dead_connections:
            self.disconnect(websocket, session_id)

    def get_connection_count(self, session_id: str = None) -> int:
        """Get number of active connections for a session or total"""
        if session_id:
            return len(self.active_connections.get(session_id, []))
        return sum(len(conns) for conns in self.active_connections.values())


# Singleton instance
ws_manager = WebSocketManager()
