"""Flood Detection Agent - Change Detection Specialist

This agent analyzes water coverage data to detect flooding:
- Compares before/after water coverage percentages
- Classifies flood severity
- Identifies affected areas and zones
"""

from google.adk.agents import LlmAgent

from .prompts import FLOOD_DETECTION_PROMPT


flood_detection_agent = LlmAgent(
    name="FloodDetectionAgent",
    model="gemini-2.0-flash",
    description=(
        "Flood detection specialist. Call this agent with before/after water "
        "coverage data to analyze changes and detect flooding. Provide water "
        "percentages and dates. Returns flood severity and affected areas."
    ),
    instruction=FLOOD_DETECTION_PROMPT,
)
