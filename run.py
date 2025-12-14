"""Run the flood detection orchestrator programmatically

Usage:
    python run.py

This script demonstrates how to run the multi-agent system outside of ADK CLI.
"""

import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def main():
    """Run the flood analysis orchestrator with a sample query."""
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    from agents import root_agent

    # Create session service
    session_service = InMemorySessionService()

    # Create a session
    session = await session_service.create_session(
        state={},
        app_name="flood_detection",
        user_id="demo_user"
    )

    # Create runner
    runner = Runner(
        app_name="flood_detection",
        agent=root_agent,
        session_service=session_service,
    )

    # Example query
    query = "What was the impact of Hurricane Helene on Cedar Key, Florida?"
    content = types.Content(role="user", parts=[types.Part(text=query)])

    print(f"Query: {query}\n")
    print("=" * 60)
    print("Orchestrator analyzing query and routing to specialists...\n")

    # Run the agent
    async for event in runner.run_async(
        session_id=session.id,
        user_id=session.user_id,
        new_message=content
    ):
        if hasattr(event, 'content') and event.content:
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    print(f"[{event.author}]: {part.text}\n")


if __name__ == "__main__":
    asyncio.run(main())
