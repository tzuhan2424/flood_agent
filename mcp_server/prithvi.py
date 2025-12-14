"""
Prithvi Flood Segmentation Client

Interfaces with IBM/NASA Prithvi-EO-2.0 model via HuggingFace Spaces
"""

import os
import shutil
from pathlib import Path
from typing import Tuple


class PrithviClient:
    """Client for Prithvi flood segmentation model"""

    def __init__(self):
        self.space_name = "ibm-nasa-geospatial/Prithvi-EO-2.0-Sen1Floods11-demo"
        self._client = None

    def segment_flood(self, tiff_path: str) -> Tuple[str, str, str]:
        """
        Run flood segmentation on Sentinel-2 imagery.

        Args:
            tiff_path: Path to 6-band Sentinel-2 TIFF file

        Returns:
            Tuple of (original_viz_path, flood_mask_path, overlay_path)
            All paths are temporary files that should be copied/moved
        """
        # Lazy import to avoid loading if not needed
        try:
            from gradio_client import Client, handle_file
        except ImportError:
            raise ImportError(
                "gradio_client not installed. "
                "Install with: pip install gradio-client"
            )

        # Initialize client if needed
        if self._client is None:
            self._client = Client(self.space_name)

        # Run segmentation
        result = self._client.predict(
            data_file=handle_file(tiff_path),
            api_name="/partial"
        )

        # Result is a tuple of 3 temporary file paths
        if not isinstance(result, tuple) or len(result) != 3:
            raise ValueError(
                f"Unexpected result from Prithvi API: {type(result)}"
            )

        original_path, mask_path, overlay_path = result

        # Verify files exist
        for path in [original_path, mask_path, overlay_path]:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Prithvi output not found: {path}")

        return original_path, mask_path, overlay_path

    def calculate_water_coverage(self, mask_path: str) -> dict:
        """
        Calculate water coverage from segmentation mask.

        NOTE: This calculates WATER coverage, not necessarily FLOODING.
        Water can include lakes, rivers, ocean, etc.
        For true flood detection, you need change detection between
        before/after images to identify NEW water areas.

        Args:
            mask_path: Path to water segmentation mask (WebP)

        Returns:
            Dictionary with water coverage statistics
        """
        try:
            from PIL import Image
            import numpy as np
        except ImportError:
            raise ImportError(
                "PIL/numpy not installed. "
                "Install with: pip install pillow numpy"
            )

        # Load mask
        img = Image.open(mask_path)
        arr = np.array(img)

        # Convert to grayscale if RGB
        if len(arr.shape) == 3:
            arr = np.mean(arr, axis=2)

        # Threshold to binary
        threshold = np.max(arr) * 0.5
        water_mask = (arr > threshold).astype(np.uint8)

        # Calculate stats
        water_pixels = int(np.sum(water_mask))
        total_pixels = int(water_mask.size)
        water_pct = (water_pixels / total_pixels * 100) if total_pixels > 0 else 0

        return {
            "water_pixels": water_pixels,
            "total_pixels": total_pixels,
            "water_coverage_pct": round(water_pct, 2),
            "note": "This is water coverage, not flood. Includes lakes, rivers, ocean, etc."
        }
