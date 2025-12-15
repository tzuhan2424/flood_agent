"""
Flood Detection MCP Server

Exposes Sentinel Hub search as an MCP tool for AI agents.
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
import rasterio
from rasterio.transform import from_bounds

from fastmcp import FastMCP
from .sentinel import SentinelHubClient
from .prithvi import PrithviClient
from .nwps import NWPSClient

# Initialize MCP server
mcp = FastMCP("Flood Detection Tools")

# Initialize clients
sentinel_client = SentinelHubClient()
prithvi_client = PrithviClient()
nwps_client = NWPSClient()

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
    max_cloud_cover: float = 10.0,
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
                        Default: 10% (recommended for flood detection)
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
    output_prefix: str = "",
    parent_dir: str = "",
    subfolder_name: str = "",
    width: int = 1024,
    height: int = 1024,
    include_gauges: bool = True
) -> dict:
    """
    Fetch Sentinel-2 imagery and run Prithvi water segmentation.

    This tool performs the complete water detection pipeline:
    1. Validates cloud coverage and selects best date (within ±5 days if needed)
    2. Fetches Sentinel-2 satellite imagery from Sentinel Hub
    3. Runs IBM/NASA Prithvi AI water segmentation
    4. Optionally fetches NWPS gauge data for the area (ground truth)
    5. Saves results (water mask, overlay, original viz, gauge data) to outputs/
    6. Returns file paths, metadata, and statistics

    IMPORTANT: This detects WATER, not necessarily FLOODING.
    The mask includes lakes, rivers, ocean, and other water bodies.
    For true flood detection, you need change detection (before/after comparison).

    GAUGE DATA: By default, this tool also fetches current water level readings
    from NWPS gauges in the area. This provides ground truth measurements to
    complement the satellite imagery. Set include_gauges=False to skip this.

    CLOUD COVERAGE: The tool automatically checks cloud coverage for the requested
    date. If cloud coverage exceeds 10%, it will select the nearest date within
    ±5 days that has acceptable cloud coverage (<10%). The response includes both
    the requested date and actual date used, along with a flag indicating if
    substitution occurred.

    Args:
        bbox: Bounding box as [min_lon, min_lat, max_lon, max_lat]
              Example: [-83.05, 29.12, -82.95, 29.18] for Cedar Key, FL
        date: Date to fetch imagery (YYYY-MM-DD format)
              Example: "2024-09-19"
        image_id: Optional image ID from search results (for reference)
        output_prefix: Optional prefix for output files (default: uses date)
        parent_dir: Optional parent directory name (default: auto-generated)
                   Use this to group related images (e.g., before/after) in one folder
        subfolder_name: Optional subfolder within parent_dir (e.g., "before", "after")
                       Creates: outputs/{parent_dir}/{subfolder_name}/
        width: Image width in pixels (default: 1024, max: 2500)
               Higher = more detail but slower. 1024x1024 recommended for most use cases.
        height: Image height in pixels (default: 1024, max: 2500)
                Higher = more detail but slower. 1024x1024 recommended for most use cases.

    Returns:
        Dictionary containing:
        - status: "success" or "error"
        - date: Actual date used for imagery (may differ from requested)
        - requested_date: Original requested date
        - date_substitution: Boolean flag if different date was selected
        - cloud_coverage: Cloud coverage percentage of selected image
        - files: Paths to output files (relative and absolute)
        - metadata: Georeference information (bounds, transform, CRS)
        - stats: Water coverage statistics (not flood-specific!)
        - bbox: Input bounding box

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

    # Generate output directory structure
    from datetime import datetime as dt
    import sys

    if parent_dir:
        # Use provided parent directory
        base_dir = OUTPUTS_DIR / parent_dir
    else:
        # Auto-generate parent directory with timestamp
        if not output_prefix:
            output_prefix = date.replace("-", "")
        parent_dir = f"{output_prefix}_{dt.now().strftime('%H%M%S')}"
        base_dir = OUTPUTS_DIR / parent_dir

    # Add subfolder if specified (e.g., "before", "after")
    if subfolder_name:
        run_dir = base_dir / subfolder_name
        run_id = f"{parent_dir}/{subfolder_name}"
    else:
        run_dir = base_dir
        run_id = parent_dir

    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {run_dir.absolute()}", file=sys.stderr)

    try:
        # Step 0: Validate cloud coverage and find best date if needed
        from datetime import datetime, timedelta

        # Parse the requested date
        requested_date = datetime.strptime(date, "%Y-%m-%d")

        # Search for images in a ±5 day window around requested date
        search_start = (requested_date - timedelta(days=5)).strftime("%Y-%m-%d")
        search_end = (requested_date + timedelta(days=5)).strftime("%Y-%m-%d")

        print(f"Checking cloud coverage for {date} (searching {search_start} to {search_end})...", file=sys.stderr)

        search_results = sentinel_client.search_images(
            start_date=search_start,
            end_date=search_end,
            bbox=bbox,
            max_cloud_cover=100.0,  # Get all images first
            limit=50,
            sample_strategy="all"
        )

        # Find best date with cloud coverage < 10%
        best_date = None
        best_cloud = None
        min_date_diff = float('inf')

        for img in search_results.get("images", []):
            # Extract just the date part (format: "2024-09-27T16:15:26Z" -> "2024-09-27")
            img_date_str = img["date"].split("T")[0]
            img_date = datetime.strptime(img_date_str, "%Y-%m-%d")
            img_cloud = img["cloud_cover"]  # Fixed: was "cloud_coverage"
            date_diff = abs((img_date - requested_date).days)

            # Prefer images with cloud < 10%
            if img_cloud < 10.0:
                if date_diff < min_date_diff:
                    best_date = img_date_str  # Use date string without time
                    best_cloud = img_cloud
                    min_date_diff = date_diff

        # If no images with < 10% cloud, use the requested date anyway but warn
        if best_date is None:
            print(f"WARNING: No images with <10% cloud found. Using requested date {date}.", file=sys.stderr)
            actual_date = date
            actual_cloud = "unknown"
        elif best_date != date:
            print(f"INFO: Requested date {date} has high cloud coverage.", file=sys.stderr)
            print(f"INFO: Using nearby date {best_date} with {best_cloud:.1f}% cloud instead.", file=sys.stderr)
            actual_date = best_date
            actual_cloud = best_cloud
        else:
            print(f"INFO: Date {date} has acceptable cloud coverage ({best_cloud:.1f}%).", file=sys.stderr)
            actual_date = date
            actual_cloud = best_cloud

        # Step 1: Fetch Sentinel-2 imagery using the selected date
        print(f"Fetching Sentinel-2 imagery for {actual_date} ({width}x{height})...", file=sys.stderr)
        image_data = sentinel_client.fetch_image(
            bbox=bbox,
            date=actual_date,
            width=width,
            height=height
        )

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

        # Step 6: Fetch gauge data if requested
        gauge_info = None
        if include_gauges:
            print(f"Fetching gauge data for bbox...", file=sys.stderr)
            try:
                # Search for gauges in the bbox
                gauges_in_bbox = nwps_client.search_gauges_by_bbox(bbox, limit=10)

                if gauges_in_bbox:
                    print(f"  Found {len(gauges_in_bbox)} gauges, getting historical data for {actual_date}...", file=sys.stderr)

                    # Get historical data for the specific date being analyzed
                    gauge_data = []
                    for gauge in gauges_in_bbox:
                        try:
                            # Fetch historical data for the analysis date (not current status!)
                            hist_data = nwps_client.get_historical_data(
                                gauge['lid'],
                                actual_date,  # Same day
                                actual_date   # Same day
                            )

                            if hist_data.get('source') in ['usgs', 'noaa']:
                                # Extract the reading closest to noon on the requested date
                                values = hist_data.get('values', [])
                                if values:
                                    # Get metadata for flood categories
                                    metadata = nwps_client.get_gauge_metadata(gauge['lid'])
                                    flood_cats = metadata.get('flood', {}).get('categories', {})

                                    # Find PEAK (maximum) value for the day
                                    peak_val = None
                                    max_stage = -999

                                    for val in values:
                                        try:
                                            stage = float(val.get('v', val.get('value', -999)))
                                            if stage > max_stage:
                                                max_stage = stage
                                                peak_val = val
                                        except:
                                            continue

                                    if peak_val:
                                        stage_ft = float(peak_val.get('v', peak_val.get('value', -999)))

                                        # Determine flood category
                                        flood_status = nwps_client._classify_flood_level(stage_ft, {
                                            'action': flood_cats.get('action', {}).get('stage'),
                                            'minor': flood_cats.get('minor', {}).get('stage'),
                                            'moderate': flood_cats.get('moderate', {}).get('stage'),
                                            'major': flood_cats.get('major', {}).get('stage')
                                        })

                                        gauge_info = {
                                            'lid': gauge['lid'],
                                            'name': metadata.get('name'),
                                            'location': {
                                                'latitude': metadata.get('latitude'),
                                                'longitude': metadata.get('longitude')
                                            },
                                            'observation_date': actual_date,
                                            'peak_observation': {
                                                'stage_ft': stage_ft,
                                                'valid_time': peak_val.get('t', peak_val.get('dateTime')),
                                                'source': hist_data['source']
                                            },
                                            'flood_categories': {
                                                'action': flood_cats.get('action', {}).get('stage'),
                                                'minor': flood_cats.get('minor', {}).get('stage'),
                                                'moderate': flood_cats.get('moderate', {}).get('stage'),
                                                'major': flood_cats.get('major', {}).get('stage')
                                            },
                                            'flood_status': flood_status
                                        }
                                        gauge_data.append(gauge_info)
                                        print(f"    ✓ {gauge['lid']}: {stage_ft:.2f} ft ({flood_status['current_category']})", file=sys.stderr)
                                else:
                                    print(f"    ✗ {gauge['lid']}: No data available for {actual_date}", file=sys.stderr)
                            else:
                                print(f"    ✗ {gauge['lid']}: {hist_data.get('message', 'Data unavailable')}", file=sys.stderr)

                        except Exception as e:
                            print(f"    ✗ {gauge['lid']}: {str(e)}", file=sys.stderr)

                    # Save gauge data to JSON
                    if gauge_data:
                        import json
                        gauge_file = run_dir / "gauge_data.json"
                        with open(gauge_file, 'w') as f:
                            json.dump({
                                "bbox": bbox,
                                "analysis_date": actual_date,  # Date being analyzed
                                "query_time": datetime.now().isoformat(),  # When this query was made
                                "total_gauges": len(gauge_data),
                                "gauges": gauge_data
                            }, f, indent=2)

                        print(f"  Saved gauge data: {gauge_file.absolute()}", file=sys.stderr)

                        gauge_info = {
                            "total_found": len(gauge_data),
                            "file": "gauge_data.json",
                            "absolute_path": str(gauge_file.absolute()),
                            "data": gauge_data  # Include actual gauge data in response
                        }
                else:
                    print(f"  No gauges found in bbox", file=sys.stderr)
                    gauge_info = {
                        "total_found": 0,
                        "message": "No gauges found in the specified area"
                    }

            except Exception as e:
                print(f"  ⚠ Failed to fetch gauge data: {str(e)}", file=sys.stderr)
                gauge_info = {
                    "error": str(e),
                    "message": "Gauge data unavailable, but satellite processing succeeded"
                }

        # Prepare response with organized paths
        response = {
            "status": "success",
            "image_id": image_id,
            "date": actual_date,  # Use actual date fetched (may differ from requested)
            "requested_date": date,  # Original requested date
            "date_substitution": actual_date != date,  # Flag if different date was used
            "cloud_coverage": actual_cloud if isinstance(actual_cloud, (int, float)) else None,
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

        # Add gauge data if available
        if gauge_info:
            response["gauges"] = gauge_info

        return response

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "bbox": bbox,
            "date": date
        }

@mcp.tool
async def get_time_series_water(
    bbox: list[float],
    start_date: str,
    end_date: str,
    max_images: int = 10,
    max_cloud_cover: float = 10.0,
    segment_water: bool = True
) -> dict:
    """
    Get time series of water coverage for change detection and flood analysis.

    This tool finds the best available images over a time period and
    optionally segments water coverage for each date. Essential for
    detecting flood changes (before/after comparison).

    IMPORTANT: Gauge data is automatically included for each date!
    Each date folder will contain both satellite imagery and gauge_data.json.

    Args:
        bbox: Bounding box as [min_lon, min_lat, max_lon, max_lat]
        start_date: Start date (YYYY-MM-DD), e.g., "2024-09-01"
        end_date: End date (YYYY-MM-DD), e.g., "2024-09-30"
        max_images: Maximum number of images to return (default: 10)
        max_cloud_cover: Maximum cloud coverage % (default: 10.0, recommended for flood detection)
        segment_water: If True, runs segmentation on each image (slower but complete)
                      If False, just returns available dates (faster)

    Returns:
        Dictionary containing:
        - dates: List of selected dates
        - total_found: Total images found
        - images_processed: Number of images processed
        - segmented: Whether water segmentation was performed
        - time_series: List of results for each date (if segmented)
            - Each date includes: water_coverage_pct, files, metadata, stats
            - Each date includes: gauges (gauge data automatically included)

    Example:
        # Get time series for Hurricane Helene impact
        result = get_time_series_water(
            bbox=[-83.05, 29.12, -82.95, 29.18],
            start_date="2024-09-01",  # Before hurricane
            end_date="2024-09-30",    # After hurricane
            max_images=5,
            segment_water=True
        )
        # Returns water coverage for 5 dates, showing how flooding changed
    """
    import sys

    # Validate inputs
    if len(bbox) != 4:
        raise ValueError("bbox must have exactly 4 values")

    # Step 1: Search for available images
    print(f"Searching for time series: {start_date} to {end_date}...", file=sys.stderr)

    search_results = sentinel_client.search_images(
        start_date=start_date,
        end_date=end_date,
        bbox=bbox,
        limit=max_images * 3,  # Fetch more to filter
        max_cloud_cover=max_cloud_cover,
        sample_strategy="evenly_spaced"  # Distribute across time range
    )

    selected_dates = search_results["dates"][:max_images]

    if not segment_water:
        # Fast mode: just return dates
        return {
            "status": "success",
            "dates": selected_dates,
            "total_found": search_results["total_found"],
            "images_processed": 0,
            "segmented": False,
            "message": f"Found {len(selected_dates)} dates. Use segment_water=True to process."
        }

    # Step 2: Create parent directory for this time series request
    from datetime import datetime as dt
    series_id = f"timeseries_{start_date.replace('-', '')}_to_{end_date.replace('-', '')}_{dt.now().strftime('%H%M%S')}"
    series_dir = OUTPUTS_DIR / series_id
    series_dir.mkdir(parents=True, exist_ok=True)

    print(f"Time series output directory: {series_dir.absolute()}", file=sys.stderr)
    print(f"Segmenting water for {len(selected_dates)} dates...", file=sys.stderr)

    time_series = []
    for i, date in enumerate(selected_dates):
        print(f"Processing {i+1}/{len(selected_dates)}: {date}...", file=sys.stderr)

        # Create subfolder for this date within the series directory
        date_dir = series_dir / date.replace('-', '')
        date_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Fetch and save imagery
            image_data = sentinel_client.fetch_image(bbox=bbox, date=date)
            tiff_path = date_dir / "sentinel_image.tif"
            with open(tiff_path, "wb") as f:
                f.write(image_data)

            # Run segmentation
            original_path, mask_path, overlay_path = prithvi_client.segment_flood(str(tiff_path))

            # Save outputs
            import shutil
            shutil.copy(mask_path, date_dir / "water_mask.webp")
            shutil.copy(overlay_path, date_dir / "overlay.webp")
            shutil.copy(original_path, date_dir / "original_viz.webp")

            # Calculate stats
            stats = prithvi_client.calculate_water_coverage(str(date_dir / "water_mask.webp"))

            # Get metadata
            with rasterio.open(tiff_path) as src:
                metadata = {
                    "bounds": [src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top],
                    "transform": list(src.transform),
                    "crs": "EPSG:4326"
                }

            # Fetch gauge data for this date
            gauge_info = None
            try:
                print(f"    Fetching gauge data for {date}...", file=sys.stderr)
                gauges_in_bbox = nwps_client.search_gauges_by_bbox(bbox, limit=10)

                if gauges_in_bbox:
                    gauge_data_list = []
                    for gauge in gauges_in_bbox:
                        try:
                            # Get historical data for this specific date
                            hist_data = nwps_client.get_historical_data(gauge['lid'], date, date)

                            if hist_data.get('source') in ['usgs', 'noaa'] and hist_data.get('values'):
                                # Get metadata
                                metadata = nwps_client.get_gauge_metadata(gauge['lid'])
                                flood_cats = metadata.get('flood', {}).get('categories', {})

                                # Find PEAK (maximum) value for the day
                                values = hist_data['values']
                                peak_val = None
                                max_stage = -999

                                for val in values:
                                    try:
                                        stage = float(val.get('v', val.get('value', -999)))
                                        if stage > max_stage:
                                            max_stage = stage
                                            peak_val = val
                                    except:
                                        continue

                                if peak_val:
                                    stage_ft = float(peak_val.get('v', peak_val.get('value', -999)))
                                    flood_status = nwps_client._classify_flood_level(stage_ft, {
                                        'action': flood_cats.get('action', {}).get('stage'),
                                        'minor': flood_cats.get('minor', {}).get('stage'),
                                        'moderate': flood_cats.get('moderate', {}).get('stage'),
                                        'major': flood_cats.get('major', {}).get('stage')
                                    })

                                    gauge_info_item = {
                                        'lid': gauge['lid'],
                                        'name': metadata.get('name'),
                                        'location': {'latitude': metadata.get('latitude'), 'longitude': metadata.get('longitude')},
                                        'observation_date': date,
                                        'peak_observation': {
                                            'stage_ft': stage_ft,
                                            'valid_time': peak_val.get('t', peak_val.get('dateTime')),
                                            'source': hist_data['source']
                                        },
                                        'flood_categories': {
                                            'action': flood_cats.get('action', {}).get('stage'),
                                            'minor': flood_cats.get('minor', {}).get('stage'),
                                            'moderate': flood_cats.get('moderate', {}).get('stage'),
                                            'major': flood_cats.get('major', {}).get('stage')
                                        },
                                        'flood_status': flood_status
                                    }
                                    gauge_data_list.append(gauge_info_item)
                        except Exception as e:
                            print(f"      ✗ {gauge['lid']}: {str(e)}", file=sys.stderr)

                    if gauge_data_list:
                        import json
                        gauge_file = date_dir / "gauge_data.json"
                        with open(gauge_file, 'w') as f:
                            json.dump({
                                "bbox": bbox,
                                "date": date,
                                "query_time": datetime.now().isoformat(),
                                "total_gauges": len(gauge_data_list),
                                "gauges": gauge_data_list
                            }, f, indent=2)

                        gauge_info = {
                            "total_found": len(gauge_data_list),
                            "file": "gauge_data.json",
                            "data": gauge_data_list  # Include actual gauge data in response
                        }
                        print(f"    ✓ Saved gauge data: {len(gauge_data_list)} gauge(s)", file=sys.stderr)
            except Exception as e:
                print(f"    ⚠ Failed to fetch gauge data: {str(e)}", file=sys.stderr)

            result = {
                "date": date,
                "water_coverage_pct": stats["water_coverage_pct"],
                "output_directory": str(date_dir.absolute()),
                "files": {
                    "water_mask": str((date_dir / "water_mask.webp").absolute()),
                    "overlay": str((date_dir / "overlay.webp").absolute())
                },
                "metadata": metadata,
                "stats": stats
            }

            # Add gauge info if available
            if gauge_info:
                result["gauges"] = gauge_info

            time_series.append(result)

        except Exception as e:
            print(f"Failed to process {date}: {e}", file=sys.stderr)
            time_series.append({
                "date": date,
                "error": str(e)
            })

    return {
        "status": "success",
        "series_id": series_id,
        "output_directory": str(series_dir.absolute()),
        "dates": selected_dates,
        "total_found": search_results["total_found"],
        "images_processed": len(time_series),
        "segmented": True,
        "time_series": time_series,
        "summary": {
            "start_date": start_date,
            "end_date": end_date,
            "bbox": bbox
        }
    }

# DISABLED - SAR incompatible with Prithvi segmentation
"""
@mcp.tool
async def fetch_sar_image(
    bbox: list[float],
    date: str,
    output_prefix: str = ""
) -> dict:

    Fetch Sentinel-1 SAR (radar) imagery that works through clouds.

    SAR (Synthetic Aperture Radar) uses radar instead of optical light,
    allowing it to see through clouds, smoke, and darkness. Essential for
    monitoring floods during active storms when optical imagery is obscured.

    Args:
        bbox: Bounding box as [min_lon, min_lat, max_lon, max_lat]
        date: Date to fetch (YYYY-MM-DD format)
        output_prefix: Optional prefix for output files

    Returns:
        Dictionary containing:
        - status: "success" or "error"
        - files: Paths to SAR imagery
        - metadata: Georeference information
        - date: Input date
        - sensor: "sentinel-1-sar"

    Example:
        # Get SAR image during Hurricane Helene (works through clouds!)
        result = fetch_sar_image(
            bbox=[-83.05, 29.12, -82.95, 29.18],
            date="2024-09-27"  # During hurricane
        )
        # Returns SAR imagery that can detect flooding despite cloud cover

    import sys
    from datetime import datetime as dt

    # Validate inputs
    if len(bbox) != 4:
        raise ValueError("bbox must have exactly 4 values")

    # Generate output prefix and create run-specific directory
    if not output_prefix:
        output_prefix = f"sar_{date.replace('-', '')}"

    run_id = f"{output_prefix}_{dt.now().strftime('%H%M%S')}"
    run_dir = OUTPUTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"Output directory: {run_dir.absolute()}", file=sys.stderr)

    try:
        # Fetch Sentinel-1 SAR imagery
        print(f"Fetching Sentinel-1 SAR for {date}...", file=sys.stderr)
        sar_data = sentinel_client.fetch_sar_image(bbox=bbox, date=date)

        # Save SAR TIFF
        tiff_filename = "sar_image.tif"
        tiff_path = run_dir / tiff_filename
        with open(tiff_path, "wb") as f:
            f.write(sar_data)

        print(f"Saved SAR image: {tiff_path.absolute()}", file=sys.stderr)

        # Extract metadata
        with rasterio.open(tiff_path) as src:
            transform_matrix = list(src.transform)
            bounds = src.bounds
            metadata = {
                "bounds": [bounds.left, bounds.bottom, bounds.right, bounds.top],
                "transform": transform_matrix,
                "crs": "EPSG:4326",
                "width": src.width,
                "height": src.height,
                "bands": src.count,
                "band_descriptions": ["VV", "VH"]
            }

        return {
            "status": "success",
            "sensor": "sentinel-1-sar",
            "date": date,
            "bbox": bbox,
            "run_id": run_id,
            "output_directory": str(run_dir.absolute()),
            "files": {
                "sar_image": tiff_filename,
                "absolute_paths": {
                    "directory": str(run_dir.absolute()),
                    "sar_image": str(tiff_path.absolute())
                }
            },
            "metadata": metadata,
            "note": "SAR imagery works through clouds. VV and VH polarizations included."
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "bbox": bbox,
            "date": date
        }
"""

@mcp.tool
async def get_current_datetime() -> dict:
    """
    Get the current date and time.

    Use this tool when you need to know the current date for queries like
    "what's the water level NOW" or "current flooding status".

    Returns:
        Dictionary containing:
        - date: Current date in YYYY-MM-DD format
        - datetime: Full timestamp in ISO format
        - timestamp: Unix timestamp
        - timezone: UTC

    Example:
        # Get current date for real-time queries
        now = get_current_datetime()
        # Returns: {"date": "2025-12-14", "datetime": "2025-12-14T21:30:00Z", ...}
    """
    now = datetime.utcnow()

    return {
        "date": now.strftime("%Y-%m-%d"),
        "datetime": now.isoformat() + "Z",
        "timestamp": now.timestamp(),
        "timezone": "UTC",
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "hour": now.hour,
        "minute": now.minute
    }

@mcp.tool
async def search_gauges(
    bbox: list[float],
    limit: int = 20
) -> dict:
    """
    Search for NWPS water gauges in a geographic area.

    Use this to discover available stream/river gauges for flood monitoring.
    Returns gauge locations and IDs that can be used with other gauge tools.

    Args:
        bbox: Bounding box as [min_lon, min_lat, max_lon, max_lat]
              Example: [-74.02, 40.70, -73.97, 40.75] for Lower Manhattan
        limit: Maximum number of gauges to return (default: 20)

    Returns:
        Dictionary containing:
        - total_found: Number of gauges in the area
        - returned: Number of gauges actually returned
        - gauges: List of gauge dictionaries with:
            - lid: Gauge ID (NWSLI) - use this with other gauge tools
            - name: Human-readable gauge name
            - latitude, longitude: Location coordinates
            - usgsId: USGS site ID (if available, for historical data)

    Example:
        # Find gauges in NYC area
        result = search_gauges(bbox=[-74.02, 40.70, -73.97, 40.75])
        # Returns: {"total_found": 5, "gauges": [{"lid": "BATN6", ...}, ...]}
    """
    import sys

    # Validate inputs
    if len(bbox) != 4:
        raise ValueError("bbox must have exactly 4 values [min_lon, min_lat, max_lon, max_lat]")

    print(f"Searching for gauges in bbox: {bbox}...", file=sys.stderr)

    try:
        gauges = nwps_client.search_gauges_by_bbox(bbox, limit=limit)

        print(f"Found {len(gauges)} gauges", file=sys.stderr)

        return {
            "status": "success",
            "total_found": len(gauges),
            "returned": len(gauges),
            "bbox": bbox,
            "gauges": gauges
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "bbox": bbox
        }

@mcp.tool
async def get_gauge_status(
    gauge_ids: list[str],
    include_forecast: bool = True
) -> dict:
    """
    Get current water level and flood status for gauge(s).

    Returns real-time observations, flood category thresholds, and forecasts.
    Essential for immediate flood risk assessment without satellite imagery.

    Args:
        gauge_ids: List of gauge IDs (NWSLI) to query
                  Example: ["BATN6", "LOLT2"]
        include_forecast: Include forecast data (default: True)

    Returns:
        Dictionary containing:
        - total_queried: Number of gauges requested
        - successful: Number of gauges successfully queried
        - gauges: List of gauge status dictionaries with:
            - lid: Gauge ID
            - name: Gauge name
            - location: {latitude, longitude}
            - current_observation: Latest reading
                - stage_ft: Water level in feet
                - flow_cfs: Flow rate in cubic feet per second (if available)
                - valid_time: Timestamp of reading
            - flood_categories: Thresholds for flood levels
                - action: Action stage in feet
                - minor: Minor flood stage
                - moderate: Moderate flood stage
                - major: Major flood stage
            - flood_status: Current status analysis
                - current_category: "normal", "action", "minor", "moderate", "major"
                - above_action: Boolean
                - feet_to_action, feet_to_minor, etc.: Distance to each level
            - forecast: Forecast information (if include_forecast=True)
                - peak_stage: Expected peak water level
                - peak_time: When peak expected
                - trend: "rising", "falling", or "steady"

    Example:
        # Check current status of NYC gauge
        status = get_gauge_status(gauge_ids=["BATN6"])
        # Returns current reading, flood status, and forecast

        # Check if flooding
        if status['gauges'][0]['flood_status']['current_category'] == 'major':
            print("Major flooding detected!")
    """
    import sys

    if not gauge_ids:
        raise ValueError("gauge_ids must contain at least one gauge ID")

    print(f"Getting status for {len(gauge_ids)} gauge(s)...", file=sys.stderr)

    results = []
    errors = []

    for gauge_id in gauge_ids:
        try:
            status = nwps_client.get_flood_status(gauge_id)

            # Remove forecast if not requested
            if not include_forecast:
                status.pop('forecast', None)

            results.append(status)
            print(f"  ✓ {gauge_id}: {status['flood_status']['current_category']}", file=sys.stderr)

        except Exception as e:
            error_msg = f"{gauge_id}: {str(e)}"
            errors.append(error_msg)
            print(f"  ✗ {error_msg}", file=sys.stderr)

    return {
        "status": "success" if results else "error",
        "total_queried": len(gauge_ids),
        "successful": len(results),
        "failed": len(errors),
        "gauges": results,
        "errors": errors if errors else None
    }

@mcp.tool
async def get_gauge_timeseries(
    gauge_id: str,
    start_date: str,
    end_date: str
) -> dict:
    """
    Get historical water level data for change detection and analysis.

    Fetches historical data from USGS (river gauges) or NOAA Tides & Currents
    (coastal gauges). Useful for comparing current conditions to historical baseline
    or analyzing past flood events.

    Args:
        gauge_id: Gauge ID (NWSLI) - e.g., "LOLT2", "BATN6"
        start_date: Start date in YYYY-MM-DD format (e.g., "2024-01-01")
        end_date: End date in YYYY-MM-DD format (e.g., "2024-01-07")

    Returns:
        Dictionary containing:
        - status: "success" or "error"
        - source: "usgs", "noaa", or "unavailable"
        - gauge_id: Input gauge ID
        - period: {start, end} dates
        - data: Historical time series data
            For USGS: Multiple series (stage, flow) with values and statistics
            For NOAA: Single series (water level) with values and statistics
        - statistics: Peak, mean, min, max values

    Example:
        # Get historical data for river gauge
        hist = get_gauge_timeseries(
            gauge_id="LOLT2",
            start_date="2024-01-01",
            end_date="2024-01-07"
        )
        # Returns USGS data with stage and flow measurements

        # Get historical data for coastal gauge
        hist = get_gauge_timeseries(
            gauge_id="BATN6",
            start_date="2024-09-15",
            end_date="2024-09-20"
        )
        # Returns NOAA water level data
    """
    import sys

    print(f"Fetching historical data for {gauge_id} ({start_date} to {end_date})...", file=sys.stderr)

    try:
        result = nwps_client.get_historical_data(gauge_id, start_date, end_date)

        source = result.get('source', 'unknown')
        print(f"  Data source: {source.upper()}", file=sys.stderr)

        if 'error' in result:
            print(f"  ✗ Error: {result['error']}", file=sys.stderr)
            return {
                "status": "error",
                **result
            }
        elif source == 'unavailable':
            print(f"  ⚠ Historical data not available", file=sys.stderr)
            return {
                "status": "unavailable",
                **result
            }
        else:
            # Count data points
            if source == 'usgs':
                total_points = sum(s.get('data_points', 0) for s in result.get('time_series', []))
            else:  # noaa
                total_points = result.get('data_points', 0)

            print(f"  ✓ Retrieved {total_points} data points", file=sys.stderr)

            return {
                "status": "success",
                **result
            }

    except Exception as e:
        print(f"  ✗ Error: {str(e)}", file=sys.stderr)
        return {
            "status": "error",
            "gauge_id": gauge_id,
            "error": str(e)
        }

if __name__ == "__main__":
    mcp.run()
