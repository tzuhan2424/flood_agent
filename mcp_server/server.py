"""
Flood Detection MCP Server

Exposes Sentinel Hub search as an MCP tool for AI agents.
"""

from fastmcp import FastMCP
from .sentinel import SentinelHubClient

# Initialize MCP server
mcp = FastMCP("Flood Detection Tools")

# Initialize Sentinel client
sentinel_client = SentinelHubClient()

@mcp.tool
async def search_sentinel_images(
    start_date: str,
    end_date: str,
    bbox: list[float],
    max_cloud_cover: float = 30.0,
    limit: int = 10,
    sample_strategy: str = "lowest_cloud"
) -> dict:
    """
    Search Sentinel Hub for available Sentinel-2 satellite images with smart sampling.

    Use this tool to discover what satellite imagery is available for
    a given location and time period. When many images are found, use
    sample_strategy to intelligently select the most relevant ones.

    Args:
        start_date: Start date in YYYY-MM-DD format (e.g., "2024-09-01")
        end_date: End date in YYYY-MM-DD format (e.g., "2024-09-30")
        bbox: Bounding box as [min_lon, min_lat, max_lon, max_lat]
              Example: [-83.05, 29.12, -82.95, 29.18] for Cedar Key, FL
        max_cloud_cover: Maximum acceptable cloud coverage (0-100%)
                        Default: 30%
        limit: Maximum number of results to return (default: 10)
        sample_strategy: How to sample if more results found than limit
            - "lowest_cloud": Pick images with lowest cloud cover (default)
            - "evenly_spaced": Distribute evenly across date range
            - "most_recent": Latest images first
            - "oldest_first": Earliest images first
            - "all": Return all results (up to 100 max)

    Returns:
        Dictionary containing:
        - total_found: Total number of matching images
        - returned: Number of images actually returned
        - sampled: Boolean indicating if sampling was applied
        - sample_strategy: The strategy used
        - dates: List of unique dates with available imagery
        - images: Detailed list of each image with metadata

    Example:
        # For a large time range, use evenly_spaced sampling
        result = search_sentinel_images(
            start_date="2024-01-01",
            end_date="2024-12-31",
            bbox=[-83.05, 29.12, -82.95, 29.18],
            max_cloud_cover=20.0,
            limit=12,
            sample_strategy="evenly_spaced"
        )
        # Returns: {"total_found": 47, "returned": 12, "sampled": true, ...}

        # For best quality images, use lowest_cloud
        result = search_sentinel_images(
            start_date="2024-09-01",
            end_date="2024-09-30",
            bbox=[-83.05, 29.12, -82.95, 29.18],
            sample_strategy="lowest_cloud"
        )
    """
    # Validate inputs
    if not (4 == len(bbox)):
        raise ValueError("bbox must have exactly 4 values [min_lon, min_lat, max_lon, max_lat]")

    if not (0 <= max_cloud_cover <= 100):
        raise ValueError("max_cloud_cover must be between 0 and 100")

    # Call Sentinel Hub API
    results = sentinel_client.search_images(
        start_date=start_date,
        end_date=end_date,
        bbox=bbox,
        limit=limit,
        max_cloud_cover=max_cloud_cover,
        sample_strategy=sample_strategy
    )

    return results

if __name__ == "__main__":
    mcp.run()
