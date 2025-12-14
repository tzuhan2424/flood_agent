"""
Sentinel Hub API Client - Search Only

Clean implementation based on test/test_sentinel_hub.py
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Sentinel Hub URLs
TOKEN_URL = "https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token"
CATALOG_URL = "https://services.sentinel-hub.com/api/v1/catalog/1.0.0/search"

class SentinelHubClient:
    """Simple Sentinel Hub client for catalog search only"""

    def __init__(self):
        self.client_id = os.getenv("SENTINEL_HUB_CLIENT_ID")
        self.client_secret = os.getenv("SENTINEL_HUB_CLIENT_SECRET")
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

        if not self.client_id or not self.client_secret:
            raise ValueError("Missing Sentinel Hub credentials in .env")

    def _get_token(self) -> str:
        """
        Get OAuth2 access token (with caching).

        Based on test/test_sentinel_hub.py:30-58
        """
        # Return cached token if valid
        if self._token and self._token_expiry:
            if datetime.now() < self._token_expiry:
                return self._token

        # Request new token
        response = requests.post(
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret
            },
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        self._token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)

        return self._token

    def search_images(
        self,
        start_date: str,
        end_date: str,
        bbox: list[float],
        limit: int = 10,
        max_cloud_cover: float = 100.0,
        sample_strategy: str = "lowest_cloud"
    ) -> dict:
        """
        Search Sentinel-2 catalog for available images with smart sampling.

        Based on test/test_sentinel_hub.py:60-99

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            bbox: [min_lon, min_lat, max_lon, max_lat]
            limit: Maximum number of results to return
            max_cloud_cover: Maximum cloud coverage % (0-100)
            sample_strategy: How to sample results if more than limit found
                - "lowest_cloud": Pick images with lowest cloud cover (default)
                - "evenly_spaced": Distribute evenly across date range
                - "most_recent": Latest images first
                - "oldest_first": Earliest images first
                - "all": Return all results (up to 100 max)

        Returns:
            {
                "total_found": 47,
                "returned": 10,
                "sampled": true,
                "sample_strategy": "lowest_cloud",
                "dates": ["2024-09-05", "2024-09-12", ...],
                "images": [
                    {
                        "id": "S2A_MSIL1C_20240905...",
                        "date": "2024-09-05T15:23:45Z",
                        "cloud_cover": 12.5,
                        "bbox": [-83.05, 29.12, -82.95, 29.18]
                    },
                    ...
                ]
            }
        """
        token = self._get_token()

        # Build datetime range
        datetime_range = f"{start_date}T00:00:00Z/{end_date}T23:59:59Z"

        # Search payload
        # Note: Filter by cloud cover client-side, not in query (causes 400 error)
        # Fetch more results than needed for sampling (max 100)
        fetch_limit = 100 if sample_strategy == "all" else min(limit * 5, 100)

        payload = {
            "bbox": bbox,
            "datetime": datetime_range,
            "collections": ["sentinel-2-l1c"],
            "limit": fetch_limit
        }

        response = requests.post(
            CATALOG_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=15
        )

        # Better error handling with details
        if not response.ok:
            error_detail = response.text
            raise Exception(
                f"Sentinel Hub API error ({response.status_code}): {error_detail}"
            )

        response.raise_for_status()

        results = response.json()
        features = results.get("features", [])

        # Extract ALL matching images (with cloud cover filtering)
        all_images = []

        for feature in features:
            props = feature.get("properties", {})
            image_date = props.get("datetime", "")
            cloud_cover = props.get("eo:cloud_cover", 0)

            # Filter by cloud cover client-side
            if cloud_cover > max_cloud_cover:
                continue

            all_images.append({
                "id": feature.get("id", ""),
                "date": image_date,
                "cloud_cover": cloud_cover,
                "bbox": bbox
            })

        total_found = len(all_images)

        # Apply sampling strategy
        if sample_strategy == "all":
            sampled_images = all_images[:100]  # Hard cap at 100
        elif len(all_images) <= limit:
            sampled_images = all_images
        else:
            sampled_images = self._apply_sampling(all_images, limit, sample_strategy)

        # Extract unique dates from sampled results
        dates = set()
        for img in sampled_images:
            date_str = img["date"].split("T")[0] if img["date"] else ""
            if date_str:
                dates.add(date_str)

        return {
            "total_found": total_found,
            "returned": len(sampled_images),
            "sampled": len(sampled_images) < total_found,
            "sample_strategy": sample_strategy,
            "dates": sorted(list(dates)),
            "images": sampled_images
        }

    def _apply_sampling(self, images: list, limit: int, strategy: str) -> list:
        """Apply sampling strategy to reduce image list"""

        if strategy == "lowest_cloud":
            # Sort by cloud cover, take top N
            sorted_imgs = sorted(images, key=lambda x: x["cloud_cover"])
            return sorted_imgs[:limit]

        elif strategy == "evenly_spaced":
            # Distribute evenly across the list (assumes chronological)
            if len(images) <= limit:
                return images
            step = len(images) / limit
            indices = [int(i * step) for i in range(limit)]
            return [images[i] for i in indices]

        elif strategy == "most_recent":
            # Sort by date descending, take first N
            sorted_imgs = sorted(images, key=lambda x: x["date"], reverse=True)
            return sorted_imgs[:limit]

        elif strategy == "oldest_first":
            # Sort by date ascending, take first N
            sorted_imgs = sorted(images, key=lambda x: x["date"])
            return sorted_imgs[:limit]

        else:
            # Default: just take first N
            return images[:limit]
