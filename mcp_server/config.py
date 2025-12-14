"""Configuration for MCP server"""

import os
from pathlib import Path

# Sentinel Hub
SENTINEL_HUB_CLIENT_ID = os.getenv("SENTINEL_HUB_CLIENT_ID")
SENTINEL_HUB_CLIENT_SECRET = os.getenv("SENTINEL_HUB_CLIENT_SECRET")

# Default locations
DEFAULT_BBOX_CEDAR_KEY = [-83.05, 29.12, -82.95, 29.18]
DEFAULT_BBOX_NYC = [-74.02, 40.70, -73.97, 40.75]

# Output
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)
