"""
NWPS (National Water Prediction Service) API Client

Provides access to NOAA water gauge data including:
- Gauge search by bounding box
- Current observations and forecasts
- Flood category thresholds
- Historical data (USGS or NOAA Tides & Currents)

Reference: https://api.water.noaa.gov/nwps/v1/docs/
"""

import requests
from datetime import datetime
from typing import Optional


class NWPSClient:
    """Client for NOAA National Water Prediction Service API"""

    BASE_URL = "https://api.water.noaa.gov/nwps/v1"
    USGS_BASE_URL = "https://waterservices.usgs.gov/nwis/iv/"
    NOAA_TIDES_BASE_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

    def __init__(self):
        """Initialize NWPS client (no authentication required)"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'FloodDetectionAgent/1.0'
        })

    def search_gauges_by_bbox(self, bbox: list[float], limit: int = 100) -> list[dict]:
        """
        Search for gauges within a bounding box.

        Args:
            bbox: Bounding box as [min_lon, min_lat, max_lon, max_lat]
            limit: Maximum number of results (not enforced by API, used for local filtering)

        Returns:
            List of gauge dictionaries with:
            - lid: Gauge ID (NWSLI)
            - name: Gauge name
            - latitude, longitude: Location
            - usgsId: USGS site ID (if available)

        Example:
            gauges = client.search_gauges_by_bbox([-74.02, 40.70, -73.97, 40.75])
            # Returns gauges in NYC area
        """
        if len(bbox) != 4:
            raise ValueError("bbox must have exactly 4 values [min_lon, min_lat, max_lon, max_lat]")

        min_lon, min_lat, max_lon, max_lat = bbox

        url = f"{self.BASE_URL}/gauges"
        params = {
            "bbox.xmin": min_lon,
            "bbox.ymin": min_lat,
            "bbox.xmax": max_lon,
            "bbox.ymax": max_lat,
            "srid": "EPSG_4326"  # Standard WGS84 lat/lon
        }

        try:
            response = self.session.get(url, params=params, timeout=20)
            response.raise_for_status()

            data = response.json()
            gauges = data.get("gauges", [])

            # Apply limit if specified
            if limit and len(gauges) > limit:
                gauges = gauges[:limit]

            return gauges

        except requests.exceptions.Timeout:
            raise Exception(f"NWPS API request timed out after 20 seconds")
        except requests.exceptions.RequestException as e:
            raise Exception(f"NWPS API request failed: {str(e)}")

    def get_gauge_metadata(self, gauge_id: str) -> dict:
        """
        Get detailed metadata for a gauge.

        Args:
            gauge_id: Gauge ID (NWSLI), e.g., "BATN6" or "LOLT2"

        Returns:
            Dictionary with:
            - lid, name: Gauge identifier and name
            - latitude, longitude: Location
            - flood: Flood category thresholds
                - categories: {action, minor, moderate, major}
                    - Each has 'stage' value in feet
            - usgsId: USGS site ID (for historical data, if available)

        Example:
            metadata = client.get_gauge_metadata("BATN6")
            # Returns flood categories, location, etc.
        """
        url = f"{self.BASE_URL}/gauges/{gauge_id}"

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise Exception(f"Gauge '{gauge_id}' not found in NWPS system")
            raise Exception(f"Failed to get gauge metadata: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"NWPS API request failed: {str(e)}")

    def get_gauge_stageflow(self, gauge_id: str) -> dict:
        """
        Get current observations and forecasts for a gauge.

        Args:
            gauge_id: Gauge ID (NWSLI)

        Returns:
            Dictionary with:
            - observed: Recent observations
                - data: List of {validTime, primary (stage), secondary (flow)}
                - primaryUnits: Units for stage (typically "ft")
                - secondaryUnits: Units for flow (typically "cfs")
            - forecast: Forecast data
                - data: List of {validTime, primary, secondary}
                - primaryUnits, secondaryUnits

        Example:
            stageflow = client.get_gauge_stageflow("BATN6")
            latest = stageflow['observed']['data'][-1]
            current_stage = latest['primary']  # Stage in feet
        """
        url = f"{self.BASE_URL}/gauges/{gauge_id}/stageflow"

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise Exception(f"Stage/flow data not found for gauge '{gauge_id}'")
            raise Exception(f"Failed to get stage/flow data: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"NWPS API request failed: {str(e)}")

    def get_flood_status(self, gauge_id: str) -> dict:
        """
        Get current flood status by combining metadata and observations.

        Args:
            gauge_id: Gauge ID (NWSLI)

        Returns:
            Dictionary with:
            - lid, name, location: Gauge info
            - current_observation: Latest reading
                - stage_ft: Current stage in feet
                - flow_cfs: Current flow in cfs (if available)
                - valid_time: Timestamp
            - flood_categories: Thresholds (action/minor/moderate/major)
            - flood_status: Analysis
                - current_category: "normal", "action", "minor", "moderate", "major"
                - above_action: Boolean
                - feet_to_action, feet_to_minor, etc.
            - forecast: Forecast info (if available)
                - peak_stage: Expected peak
                - peak_time: When peak expected
                - trend: "rising", "falling", "steady"

        Example:
            status = client.get_flood_status("BATN6")
            if status['flood_status']['current_category'] == 'major':
                print("Major flooding!")
        """
        # Get metadata for flood categories
        metadata = self.get_gauge_metadata(gauge_id)

        # Get current observations and forecasts
        stageflow = self.get_gauge_stageflow(gauge_id)

        # Extract current observation
        obs_data = stageflow.get('observed', {}).get('data', [])
        current_obs = None
        current_stage = None
        current_flow = None

        if obs_data:
            last_obs = obs_data[-1]
            current_stage = last_obs.get('primary')
            current_flow = last_obs.get('secondary')
            current_obs = {
                'stage_ft': current_stage,
                'flow_cfs': current_flow,
                'valid_time': last_obs.get('validTime')
            }

        # Extract flood categories
        flood = metadata.get('flood', {})
        categories = flood.get('categories', {})
        flood_categories = {
            'action': categories.get('action', {}).get('stage'),
            'minor': categories.get('minor', {}).get('stage'),
            'moderate': categories.get('moderate', {}).get('stage'),
            'major': categories.get('major', {}).get('stage')
        }

        # Determine flood status
        flood_status = self._classify_flood_level(current_stage, flood_categories)

        # Extract forecast
        forecast_data = stageflow.get('forecast', {}).get('data', [])
        forecast_info = None

        if forecast_data:
            # Find peak in forecast
            peak = max(forecast_data, key=lambda x: x.get('primary', 0))

            # Determine trend
            trend = "steady"
            if current_stage and peak.get('primary'):
                if peak['primary'] > current_stage + 0.1:
                    trend = "rising"
                elif peak['primary'] < current_stage - 0.1:
                    trend = "falling"

            forecast_info = {
                'peak_stage': peak.get('primary'),
                'peak_time': peak.get('validTime'),
                'trend': trend,
                'available': True
            }
        else:
            forecast_info = {'available': False}

        return {
            'lid': metadata.get('lid'),
            'name': metadata.get('name'),
            'location': {
                'latitude': metadata.get('latitude'),
                'longitude': metadata.get('longitude')
            },
            'current_observation': current_obs,
            'flood_categories': flood_categories,
            'flood_status': flood_status,
            'forecast': forecast_info
        }

    def _classify_flood_level(self, current_stage: Optional[float], categories: dict) -> dict:
        """
        Classify flood level based on current stage and thresholds.

        Args:
            current_stage: Current stage in feet (or None)
            categories: Flood category thresholds

        Returns:
            Dictionary with classification info
        """
        if current_stage is None:
            return {
                'current_category': 'unknown',
                'above_action': False,
                'message': 'No current stage data available'
            }

        action = categories.get('action')
        minor = categories.get('minor')
        moderate = categories.get('moderate')
        major = categories.get('major')

        # Determine category
        category = 'normal'
        if major and current_stage >= major:
            category = 'major'
        elif moderate and current_stage >= moderate:
            category = 'moderate'
        elif minor and current_stage >= minor:
            category = 'minor'
        elif action and current_stage >= action:
            category = 'action'

        # Calculate feet to each level
        result = {
            'current_category': category,
            'above_action': action and current_stage >= action if action else False
        }

        if action:
            result['feet_to_action'] = round(action - current_stage, 2)
        if minor:
            result['feet_to_minor'] = round(minor - current_stage, 2)
        if moderate:
            result['feet_to_moderate'] = round(moderate - current_stage, 2)
        if major:
            result['feet_to_major'] = round(major - current_stage, 2)

        return result

    def _find_noaa_station_by_location(self, latitude: float, longitude: float, max_distance_km: float = 5.0) -> Optional[str]:
        """
        Find the nearest NOAA station to a given location.

        Args:
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
            max_distance_km: Maximum search radius in kilometers

        Returns:
            NOAA station ID if found within radius, None otherwise
        """
        # NOAA metadata endpoint for station search
        # We'll search in a bounding box around the point
        import math
        lat_delta = max_distance_km / 111.0  # Roughly 111 km per degree latitude
        lon_delta = max_distance_km / (111.0 * abs(math.cos(math.radians(latitude))))

        # Build bounding box
        min_lat = latitude - lat_delta
        max_lat = latitude + lat_delta
        min_lon = longitude - lon_delta
        max_lon = longitude + lon_delta

        # NOAA stations endpoint
        url = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
        params = {
            "type": "waterlevels",  # Only water level stations
            "units": "english"
        }

        try:
            response = self.session.get(url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()

            stations = data.get('stations', [])

            # Filter by bounding box and find closest
            closest_station = None
            min_distance = float('inf')

            for station in stations:
                try:
                    st_lat = float(station.get('lat', 0))
                    st_lon = float(station.get('lng', 0))

                    # Check if in bounding box
                    if not (min_lat <= st_lat <= max_lat and min_lon <= st_lon <= max_lon):
                        continue

                    # Calculate distance (Haversine formula)
                    dlat = math.radians(st_lat - latitude)
                    dlon = math.radians(st_lon - longitude)
                    a = math.sin(dlat/2)**2 + math.cos(math.radians(latitude)) * \
                        math.cos(math.radians(st_lat)) * math.sin(dlon/2)**2
                    c = 2 * math.asin(math.sqrt(a))
                    distance_km = 6371 * c  # Earth radius in km

                    if distance_km < min_distance and distance_km <= max_distance_km:
                        min_distance = distance_km
                        closest_station = station.get('id')
                except (ValueError, TypeError):
                    continue

            return closest_station

        except Exception as e:
            print(f"Failed to search NOAA stations: {e}")
            return None

    def get_historical_data(self, gauge_id: str, start_date: str, end_date: str) -> dict:
        """
        Get historical water level data (two-tier approach).

        This method intelligently routes to either USGS or NOAA APIs based on gauge type:
        - River/stream gauges: USGS Water Services (if usgsId available)
        - Coastal/tidal gauges: NOAA Tides & Currents (auto-discovered by location)

        Args:
            gauge_id: Gauge ID (NWSLI)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Dictionary with:
            - source: "usgs", "noaa", or "unavailable"
            - gauge_id: Input gauge ID
            - data: Time series data
            - statistics: Peak values, means, etc.

        Example:
            hist = client.get_historical_data("LOLT2", "2024-01-01", "2024-01-07")
            # Returns USGS data for river gauge

            hist = client.get_historical_data("CKYF1", "2024-01-01", "2024-01-07")
            # Auto-discovers NOAA station 8727520 for Cedar Key
        """
        # Step 1: Get metadata to check for USGS ID
        try:
            import sys
            print(f"[NWPS] get_historical_data called for {gauge_id}, {start_date} to {end_date}", file=sys.stderr)

            metadata = self.get_gauge_metadata(gauge_id)
            usgs_id = metadata.get('usgsId')
            print(f"[NWPS] usgsId = '{usgs_id}' (empty={not usgs_id})", file=sys.stderr)

            # Step 2: Try USGS first if ID available
            if usgs_id:
                print(f"[NWPS] Using USGS for {gauge_id}", file=sys.stderr)
                return self._fetch_usgs_historical(usgs_id, gauge_id, start_date, end_date)

            # Step 3: For coastal/tidal gauges, auto-discover NOAA station by location
            latitude = metadata.get('latitude')
            longitude = metadata.get('longitude')

            if latitude and longitude:
                print(f"[NWPS] Searching for NOAA station near {gauge_id} ({latitude}, {longitude})...", file=sys.stderr)
                noaa_station = self._find_noaa_station_by_location(latitude, longitude)

                if noaa_station:
                    print(f"[NWPS] Found NOAA station {noaa_station} for {gauge_id}", file=sys.stderr)
                    return self._fetch_noaa_historical(noaa_station, gauge_id, start_date, end_date)

            return {
                'source': 'unavailable',
                'gauge_id': gauge_id,
                'message': f'Unable to retrieve historical gauge data for {gauge_id}. The gauge is not mapped to a NOAA station, and no USGS ID is available. Historical data is therefore unavailable.',
                'suggestion': 'For coastal gauges, you can find the NOAA station ID at https://tidesandcurrents.noaa.gov/'
            }

        except Exception as e:
            return {
                'source': 'error',
                'gauge_id': gauge_id,
                'error': str(e)
            }

    def _fetch_usgs_historical(self, usgs_id: str, gauge_id: str, start_date: str, end_date: str) -> dict:
        """Fetch historical data from USGS Water Services"""
        params = {
            "format": "json",
            "sites": usgs_id,
            "startDT": start_date,  # YYYY-MM-DD format
            "endDT": end_date,
            "parameterCd": "00065,00060",  # 00065=Stage, 00060=Flow
            "siteStatus": "all"
        }

        try:
            response = self.session.get(self.USGS_BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            time_series = data.get('value', {}).get('timeSeries', [])

            if not time_series:
                return {
                    'source': 'usgs',
                    'gauge_id': gauge_id,
                    'usgs_id': usgs_id,
                    'data': [],
                    'message': 'No USGS data available for this period'
                }

            # Parse time series
            parsed_series = []
            for series in time_series:
                variable = series.get('variable', {})
                var_name = variable.get('variableName')
                unit = variable.get('unit', {}).get('unitCode')
                values = series.get('values', [])[0].get('value', [])

                if values:
                    # Calculate statistics
                    numeric_values = [float(v['value']) for v in values]
                    peak_val = max(values, key=lambda x: float(x['value']))

                    parsed_series.append({
                        'parameter': var_name,
                        'unit': unit,
                        'data_points': len(values),
                        'values': values,
                        'statistics': {
                            'peak': float(peak_val['value']),
                            'peak_time': peak_val['dateTime'],
                            'mean': sum(numeric_values) / len(numeric_values),
                            'min': min(numeric_values),
                            'max': max(numeric_values)
                        }
                    })

            return {
                'source': 'usgs',
                'gauge_id': gauge_id,
                'usgs_id': usgs_id,
                'period': {'start': start_date, 'end': end_date},
                'time_series': parsed_series
            }

        except Exception as e:
            return {
                'source': 'usgs',
                'gauge_id': gauge_id,
                'usgs_id': usgs_id,
                'error': f'USGS request failed: {str(e)}'
            }

    def _fetch_noaa_historical(self, station_id: str, gauge_id: str, start_date: str, end_date: str) -> dict:
        """Fetch historical data from NOAA Tides & Currents"""
        # Convert YYYY-MM-DD to YYYYMMDD (NOAA format)
        begin_date = start_date.replace("-", "")
        end_date_formatted = end_date.replace("-", "")

        params = {
            "begin_date": begin_date,
            "end_date": end_date_formatted,
            "station": station_id,
            "product": "water_level",
            "datum": "MLLW",  # Mean Lower Low Water
            "units": "english",  # Feet
            "time_zone": "gmt",
            "application": "FloodDetectionAgent",
            "format": "json"
        }

        try:
            response = self.session.get(self.NOAA_TIDES_BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if 'error' in data:
                return {
                    'source': 'noaa',
                    'gauge_id': gauge_id,
                    'station_id': station_id,
                    'error': data['error'].get('message', 'Unknown NOAA API error')
                }

            values = data.get('data', [])

            if not values:
                return {
                    'source': 'noaa',
                    'gauge_id': gauge_id,
                    'station_id': station_id,
                    'data': [],
                    'message': 'No NOAA data available for this period'
                }

            # Parse and calculate statistics
            numeric_values = [float(v['v']) for v in values if v['v']]
            peak_val = max(values, key=lambda x: float(x['v']) if x['v'] else -9999)

            return {
                'source': 'noaa',
                'gauge_id': gauge_id,
                'station_id': station_id,
                'period': {'start': start_date, 'end': end_date},
                'parameter': 'Water Level (MLLW)',
                'unit': 'feet',
                'data_points': len(values),
                'values': values,
                'statistics': {
                    'peak': float(peak_val['v']),
                    'peak_time': peak_val['t'],
                    'mean': sum(numeric_values) / len(numeric_values),
                    'min': min(numeric_values),
                    'max': max(numeric_values)
                }
            }

        except Exception as e:
            return {
                'source': 'noaa',
                'gauge_id': gauge_id,
                'station_id': station_id,
                'error': f'NOAA request failed: {str(e)}'
            }
