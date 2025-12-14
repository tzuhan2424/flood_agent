"""Geocoding tool for converting place names to coordinates

Uses OpenStreetMap Nominatim API (free, no API key required)
"""

import requests


def geocode_location(
    place_name: str,
    bbox_size_km: float = 5.0
) -> dict:
    """
    Convert a place name to coordinates and bounding box.

    Uses OpenStreetMap Nominatim geocoding API to find the coordinates
    of a place name, then calculates an appropriate bounding box.

    Args:
        place_name: Name of the place (e.g., "Brooklyn, NY", "Cedar Key, FL")
        bbox_size_km: Size of bounding box in kilometers (default: 5km for focused analysis)
                     For cities, 10-15km
                     For neighborhoods/towns, 5-8km (recommended)
                     For specific areas, 2-5km

    Returns:
        Dictionary containing:
        - lat: Latitude of the center point
        - lon: Longitude of the center point
        - bbox: Bounding box as [min_lon, min_lat, max_lon, max_lat] (list format for APIs)
        - bbox_dict: Bounding box as {west, south, east, north} (dict format for readability)
        - display_name: Full formatted address from geocoder
        - place_type: Type of location (city, town, suburb, etc.)

    Example:
        result = geocode_location("Brooklyn, NY", bbox_size_km=15)
        # Returns: {
        #   "lat": 40.6782,
        #   "lon": -73.9442,
        #   "bbox": [-74.05, 40.57, -73.83, 40.79],
        #   "bbox_dict": {"west": -74.05, "south": 40.57, "east": -73.83, "north": 40.79},
        #   "display_name": "Brooklyn, Kings County, New York, USA",
        #   "place_type": "suburb"
        # }
    """
    # Nominatim API endpoint
    url = "https://nominatim.openstreetmap.org/search"

    # Parameters for the request
    params = {
        "q": place_name,
        "format": "json",
        "limit": 1,
        "addressdetails": 1
    }

    # Required user agent for Nominatim
    headers = {
        "User-Agent": "FloodDetectionAgent/1.0"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        results = response.json()

        if not results:
            return {
                "error": f"Location not found: {place_name}",
                "suggestion": "Try being more specific (e.g., 'Brooklyn, New York' instead of 'Brooklyn')"
            }

        result = results[0]

        # Extract coordinates
        lat = float(result["lat"])
        lon = float(result["lon"])

        # Calculate bbox from center point
        # Approximate: 1 degree latitude ≈ 111 km
        # 1 degree longitude ≈ 111 km * cos(latitude)
        import math

        lat_offset = (bbox_size_km / 2) / 111.0
        lon_offset = (bbox_size_km / 2) / (111.0 * math.cos(math.radians(lat)))

        bbox = [
            lon - lon_offset,  # min_lon
            lat - lat_offset,  # min_lat
            lon + lon_offset,  # max_lon
            lat + lat_offset   # max_lat
        ]

        # Round to reasonable precision
        bbox_list = [round(x, 4) for x in bbox]

        # Also provide bbox in dict format for clarity
        bbox_dict = {
            'west': bbox_list[0],   # min_lon
            'south': bbox_list[1],  # min_lat
            'east': bbox_list[2],   # max_lon
            'north': bbox_list[3]   # max_lat
        }

        return {
            "status": "success",
            "place_name": place_name,
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "bbox": bbox_list,  # List format: [min_lon, min_lat, max_lon, max_lat] for Sentinel Hub API
            "bbox_dict": bbox_dict,  # Dict format: {west, south, east, north} for readability
            "display_name": result.get("display_name", ""),
            "place_type": result.get("type", "unknown"),
            "osm_type": result.get("osm_type", ""),
            "bbox_size_km": bbox_size_km
        }

    except requests.RequestException as e:
        return {
            "error": f"Geocoding request failed: {str(e)}",
            "suggestion": "Check your internet connection or try again later"
        }
    except Exception as e:
        return {
            "error": f"Geocoding error: {str(e)}"
        }
