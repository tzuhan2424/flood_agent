"""Flood Detection Agent - Change Detection Specialist

This agent analyzes water coverage data to detect flooding:
- Compares before/after water coverage percentages
- Classifies flood severity
- Identifies affected areas and zones
- Statistical anomaly detection for time series data
"""

import numpy as np
from google.adk.agents import LlmAgent

from .prompts import FLOOD_DETECTION_PROMPT


def analyze_gauge_flood_status(gauge_data: list[dict]) -> dict:
    """Analyze gauge readings to determine flood status.

    Checks if water gauges indicate flooding based on flood category thresholds.
    This provides ground truth validation for satellite-based flood detection.

    Args:
        gauge_data: List of gauge status dictionaries. Each must contain:
            - "lid" (str): Gauge ID
            - "name" (str): Gauge name
            - "current_observation" (dict): Latest reading with "stage_ft"
            - "flood_categories" (dict): Thresholds for action/minor/moderate/major
            - "flood_status" (dict): Status with "current_category"

    Returns:
        Dictionary containing:
            - "total_gauges": Number of gauges analyzed
            - "gauges_at_flood": Number of gauges at or above action stage
            - "highest_severity": Worst flood category detected (normal/action/minor/moderate/major)
            - "flooding_gauges": List of gauges showing flooding with details
            - "flood_detected": Boolean indicating if any flooding detected

    Example:
        gauge_data = [
            {
                "lid": "BATN6",
                "name": "The Battery, NY",
                "current_observation": {"stage_ft": 8.2},
                "flood_categories": {"action": 6.5, "minor": 7.5, "moderate": 9.5, "major": 11.5},
                "flood_status": {"current_category": "moderate"}
            }
        ]
        result = analyze_gauge_flood_status(gauge_data)
        # Returns: {"flood_detected": True, "highest_severity": "moderate", ...}
    """
    if not gauge_data:
        return {
            "total_gauges": 0,
            "gauges_at_flood": 0,
            "highest_severity": "no_data",
            "flooding_gauges": [],
            "flood_detected": False,
            "message": "No gauge data provided"
        }

    severity_order = ["normal", "action", "minor", "moderate", "major"]
    flooding_gauges = []
    highest_severity_idx = 0

    for gauge in gauge_data:
        flood_status = gauge.get("flood_status", {})
        category = flood_status.get("current_category", "unknown")

        # Check if at or above action stage
        if category in severity_order and severity_order.index(category) > 0:
            obs = gauge.get("current_observation", {})
            flooding_gauges.append({
                "lid": gauge.get("lid"),
                "name": gauge.get("name"),
                "current_stage": obs.get("stage_ft"),
                "flood_category": category,
                "severity_level": severity_order.index(category)
            })

            # Track highest severity
            severity_idx = severity_order.index(category)
            if severity_idx > highest_severity_idx:
                highest_severity_idx = severity_idx

    highest_severity = severity_order[highest_severity_idx]

    return {
        "total_gauges": len(gauge_data),
        "gauges_at_flood": len(flooding_gauges),
        "highest_severity": highest_severity,
        "flooding_gauges": flooding_gauges,
        "flood_detected": len(flooding_gauges) > 0,
        "message": f"Analyzed {len(gauge_data)} gauge(s). {len(flooding_gauges)} showing flooding." if gauge_data else "No gauge data"
    }


def calculate_flood_statistics(time_series: list[dict]) -> dict:
    """Calculate statistical baseline and identify flood outliers using z-score analysis.

    Analyzes water coverage time series to detect anomalous flood events within the query period.
    Uses intra-period outlier detection: compares each date against the mean and standard
    deviation of the provided time series. Requires at least 3 data points; 5+ recommended
    for reliable statistics.

    Args:
        time_series: List of water coverage measurements. Each item must be a dict with:
            - "date" (str): Date in format "YYYY-MM-DD"
            - "water_pct" (float): Water coverage percentage (0-100)

    Returns:
        Dictionary containing:
            - "baseline": Statistics for the period (mean, std deviation, sample size)
            - "outliers": List of detected flood events with z-scores and severity
            - "flood_detected": Boolean indicating if any outliers were found
            - "warning": Warning message if sample size is too small (n<5)
            - "error": Error message if insufficient data (n<3)
    """
    if len(time_series) < 3:
        return {
            "error": "Insufficient data",
            "message": f"Need at least 3 data points, got {len(time_series)}"
        }

    # Extract water percentages
    water_pcts = np.array([item["water_pct"] for item in time_series])

    # Calculate statistics
    mean = float(np.mean(water_pcts))
    std = float(np.std(water_pcts, ddof=1))  # Sample std deviation

    # Warning for small sample size
    warning = None
    if len(time_series) < 5:
        warning = f"Small sample size (n={len(time_series)}). Statistics may be unreliable."

    # Identify outliers
    outliers = []
    for item in time_series:
        water_pct = item["water_pct"]
        z_score = (water_pct - mean) / std if std > 0 else 0

        # Threshold: 2σ for significant, 3σ for extreme
        if z_score > 2.0:
            severity = "extreme" if z_score > 3.0 else "significant"
            outliers.append({
                "date": item["date"],
                "water_pct": round(water_pct, 2),
                "z_score": round(z_score, 2),
                "deviation_pct": round(water_pct - mean, 2),
                "severity": severity
            })

    # Sort outliers by z-score (worst first)
    outliers.sort(key=lambda x: x["z_score"], reverse=True)

    return {
        "baseline": {
            "mean_water_pct": round(mean, 2),
            "std_water_pct": round(std, 2),
            "sample_size": len(time_series)
        },
        "outliers": outliers,
        "flood_detected": len(outliers) > 0,
        "warning": warning
    }


flood_detection_agent = LlmAgent(
    name="FloodDetectionAgent",
    model="gemini-2.0-flash",
    description=(
        "Flood detection specialist with satellite and gauge analysis tools. "
        "Call this agent with: (1) time series water coverage data for statistical analysis, "
        "(2) before/after data for change detection, and/or (3) gauge data for ground truth validation. "
        "Combines satellite imagery analysis with real-time gauge readings for comprehensive flood assessment. "
        "Always analyze BOTH satellite and gauge data when available for accurate flood determination."
    ),
    instruction=FLOOD_DETECTION_PROMPT,
    tools=[
        calculate_flood_statistics,  # Satellite water coverage analysis
        analyze_gauge_flood_status,  # Gauge reading analysis
    ],
)
