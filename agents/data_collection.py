"""Data Collection Agent - Satellite Imagery Specialist

This agent handles all satellite imagery operations:
- Searching for available Sentinel-2 imagery
- Fetching and segmenting water areas
- Time series analysis
- SAR imagery for cloudy conditions
"""

from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from mcp import StdioServerParameters

from .prompts import DATA_COLLECTION_PROMPT

# Path to MCP server
PROJECT_ROOT = Path(__file__).parent.parent


def create_data_collection_agent() -> LlmAgent:
    """Create the data collection agent with MCP tools.

    Returns a configured LlmAgent with access to satellite imagery tools.
    """
    # MCP tools for this agent - connects to our FastMCP server
    from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams

    mcp_toolset = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="python",
                args=["-m", "mcp_server.server"],
                cwd=str(PROJECT_ROOT),
            ),
            timeout=300.0,  # 5 minutes timeout for Prithvi segmentation
        ),
        tool_filter=[
            "search_sentinel_images",
            "segment_flood_area",
            "get_time_series_water",
            "fetch_sar_image",
        ],
    )

    return LlmAgent(
        name="DataCollectionAgent",
        model="gemini-2.0-flash",
        description=(
            "Satellite imagery specialist. Call this agent to search for, fetch, "
            "and segment satellite imagery for flood detection. Provide location "
            "(bbox or place name) and date range. Returns water masks and coverage statistics."
        ),
        instruction=DATA_COLLECTION_PROMPT,
        tools=[mcp_toolset],
    )


# Create the agent instance
data_collection_agent = create_data_collection_agent()
