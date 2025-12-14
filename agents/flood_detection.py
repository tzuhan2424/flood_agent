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
        "Flood detection specialist with statistical analysis tools. "
        "Call this agent with time series water coverage data to detect "
        "flood anomalies using statistical methods, or provide before/after "
        "data for simple change detection. Requires at least 3 data points "
        "for statistical analysis."
    ),
    instruction=FLOOD_DETECTION_PROMPT,
    tools=[calculate_flood_statistics],  # Add the statistical tool
)
