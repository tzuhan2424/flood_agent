"""Orchestrator Agent - Routes queries to specialist agents

This is the main entry point (root_agent) for the flood detection system.
It coordinates the specialist agents using the AgentTool pattern:
- DataCollectionAgent: Satellite imagery operations
- FloodDetectionAgent: Change detection analysis
- ImpactAssessmentAgent: Damage and evacuation planning
"""

from google.adk.agents import LlmAgent
from google.adk.tools import agent_tool

from .data_collection import data_collection_agent
from .flood_detection import flood_detection_agent
from .impact_assessment import impact_assessment_agent
from .geocoding import geocode_location
from .prompts import ORCHESTRATOR_PROMPT


# Wrap specialist agents as tools using AgentTool
data_tool = agent_tool.AgentTool(agent=data_collection_agent)
flood_tool = agent_tool.AgentTool(agent=flood_detection_agent)
impact_tool = agent_tool.AgentTool(agent=impact_assessment_agent)

# Main Orchestrator Agent - this is the root_agent for ADK
root_agent = LlmAgent(
    name="FloodAnalysisOrchestrator",
    model="gemini-2.0-flash",
    description="Intelligent flood analysis coordinator that routes queries to specialist agents",
    instruction=ORCHESTRATOR_PROMPT,
    tools=[
        geocode_location,  # Geocoding tool for place name → coordinates
        data_tool,         # DataCollectionAgent as tool
        flood_tool,        # FloodDetectionAgent as tool
        impact_tool,       # ImpactAssessmentAgent as tool
    ],
)
