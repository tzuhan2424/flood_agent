"""ADK session management"""
from google.adk.sessions import InMemorySessionService, Session
from typing import Optional
import uuid


class SessionManager:
    """
    Manages ADK sessions for chat continuity.

    Each chat session has:
    - Unique session_id
    - ADK session state (conversation history)
    - User context
    """

    def __init__(self):
        self.adk_session_service = InMemorySessionService()
        self.sessions: dict[str, Session] = {}

    async def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        user_id: str = "web_user"
    ) -> Session:
        """Get existing session or create new one"""
        # If session_id provided and exists, return it
        if session_id and session_id in self.sessions:
            return self.sessions[session_id]

        # Create new session_id if not provided
        if not session_id:
            session_id = f"session_{uuid.uuid4().hex[:12]}"

        # Create new ADK session
        session = await self.adk_session_service.create_session(
            state={},
            app_name="flood_detection_web",
            user_id=user_id
        )

        # Store with our session_id
        self.sessions[session_id] = session

        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get existing session by ID"""
        return self.sessions.get(session_id)

    def get_session_id_by_adk_session(self, adk_session_id: str) -> Optional[str]:
        """Get our session_id from ADK session_id"""
        for sid, session in self.sessions.items():
            if session.id == adk_session_id:
                return sid
        return None


# Singleton instance
session_manager = SessionManager()
