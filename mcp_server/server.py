"""
Flood Detection MCP Server

Exposes Sentinel Hub search as an MCP tool for AI agents.
"""

import os
import shutil
from pathlib import Path
import rasterio
from rasterio.transform import from_bounds

from fastmcp import FastMCP
from .sentinel import SentinelHubClient
from .prithvi import PrithviClient

# Initialize MCP server
mcp = FastMCP("Flood Detection Tools")

# Initialize clients
sentinel_client = SentinelHubClient()
prithvi_client = PrithviClient()

# Ensure outputs directory exists (use absolute path)
# Get the directory where this script is located, then go up one level to project root
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

try:
    OUTPUTS_DIR.mkdir(exist_ok=True)
except OSError as e:
    # If we can't create in project root, use a temp directory
    import tempfile
    OUTPUTS_DIR = Path(tempfile.gettempdir()) / "flood_agent_outputs"
    OUTPUTS_DIR.mkdir(exist_ok=True)
    print(f"Warning: Using temp directory for outputs: {OUTPUTS_DIR}", file=__import__('sys').stderr)

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

@mcp.tool
async def segment_flood_area(
    bbox: list[float],
    date: str,
    image_id: str = "",
    output_prefix: str = ""
) -> dict:
    """
    Fetch Sentinel-2 imagery and run Prithvi water segmentation.

    This tool performs the complete water detection pipeline:
    1. Fetches Sentinel-2 satellite imagery from Sentinel Hub
    2. Runs IBM/NASA Prithvi AI water segmentation
    3. Saves results (water mask, overlay, original viz) to outputs/
    4. Returns file paths, metadata, and statistics

    IMPORTANT: This detects WATER, not necessarily FLOODING.
    The mask includes lakes, rivers, ocean, and other water bodies.
    For true flood detection, you need change detection (before/after comparison).

    Args:
        bbox: Bounding box as [min_lon, min_lat, max_lon, max_lat]
              Example: [-83.05, 29.12, -82.95, 29.18] for Cedar Key, FL
        date: Date to fetch imagery (YYYY-MM-DD format)
              Example: "2024-09-19"
        image_id: Optional image ID from search results (for reference)
        output_prefix: Optional prefix for output files (default: uses date)

    Returns:
        Dictionary containing:
        - status: "success" or "error"
        - files: Paths to output files (relative and absolute)
        - metadata: Georeference information (bounds, transform, CRS)
        - stats: Water coverage statistics (not flood-specific!)
        - bbox: Input bounding box
        - date: Input date

    Example:
        # First, search for available imagery
        search_result = search_sentinel_images(
            start_date="2024-09-01",
            end_date="2024-09-30",
            bbox=[-83.05, 29.12, -82.95, 29.18],
            max_cloud_cover=20.0
        )

        # Then segment water areas
        result = segment_flood_area(
            bbox=[-83.05, 29.12, -82.95, 29.18],
            date="2024-09-19",
            image_id=search_result['images'][0]['id']
        )

        # Result includes:
        # - Water mask image path
        # - Statistics: {"water_coverage_pct": 15.4, ...}
        # - Metadata for georeferencing
        # - Note: Water includes ALL water (lakes, rivers, ocean, potential floods)
    """
    # Validate inputs
    if len(bbox) != 4:
        raise ValueError("bbox must have exactly 4 values [min_lon, min_lat, max_lon, max_lat]")

    # Generate output prefix and create run-specific directory
    if not output_prefix:
        output_prefix = date.replace("-", "")

    # Create subdirectory for this run: outputs/YYYYMMDD_run/
    from datetime import datetime as dt
    run_id = f"{output_prefix}_{dt.now().strftime('%H%M%S')}"
    run_dir = OUTPUTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    import sys
    print(f"Output directory: {run_dir.absolute()}", file=sys.stderr)

    try:
        # Step 1: Fetch Sentinel-2 imagery
        print(f"Fetching Sentinel-2 imagery for {date}...", file=sys.stderr)
        image_data = sentinel_client.fetch_image(bbox=bbox, date=date)

        # Save TIFF to run directory
        tiff_filename = "sentinel_image.tif"
        tiff_path = run_dir / tiff_filename
        with open(tiff_path, "wb") as f:
            f.write(image_data)

        print(f"Saved Sentinel image: {tiff_path.absolute()}", file=sys.stderr)

        # Step 2: Run Prithvi segmentation
        print(f"Running Prithvi water segmentation...", file=sys.stderr)
        original_path, mask_path, overlay_path = prithvi_client.segment_flood(str(tiff_path))

        # Step 3: Save segmentation outputs to run directory
        output_files = {
            "original_viz": "original_viz.webp",
            "water_mask": "water_mask.webp",
            "overlay": "overlay.webp"
        }

        saved_paths = {}
        for key, filename in output_files.items():
            dest = run_dir / filename
            if key == "original_viz":
                shutil.copy(original_path, dest)
            elif key == "water_mask":
                shutil.copy(mask_path, dest)
            elif key == "overlay":
                shutil.copy(overlay_path, dest)
            saved_paths[key] = str(dest.absolute())
            print(f"Saved {key}: {dest.absolute()}", file=sys.stderr)

        # Step 4: Calculate water coverage statistics
        stats = prithvi_client.calculate_water_coverage(str(run_dir / output_files["water_mask"]))

        # Step 5: Extract georeferencing metadata
        with rasterio.open(tiff_path) as src:
            transform_matrix = list(src.transform)
            bounds = src.bounds
            metadata = {
                "bounds": [bounds.left, bounds.bottom, bounds.right, bounds.top],
                "transform": transform_matrix,
                "crs": "EPSG:4326",
                "width": src.width,
                "height": src.height
            }

        # Prepare response with organized paths
        return {
            "status": "success",
            "image_id": image_id,
            "date": date,
            "bbox": bbox,
            "run_id": run_id,
            "output_directory": str(run_dir.absolute()),
            "files": {
                "sentinel_image": tiff_filename,
                "water_mask": output_files["water_mask"],
                "overlay": output_files["overlay"],
                "original_viz": output_files["original_viz"],
                "absolute_paths": {
                    "directory": str(run_dir.absolute()),
                    "sentinel_image": str((run_dir / tiff_filename).absolute()),
                    "water_mask": str((run_dir / output_files["water_mask"]).absolute()),
                    "overlay": str((run_dir / output_files["overlay"]).absolute()),
                    "original_viz": str((run_dir / output_files["original_viz"]).absolute())
                }
            },
            "metadata": metadata,
            "stats": stats
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "bbox": bbox,
            "date": date
        }

if __name__ == "__main__":
    mcp.run()
