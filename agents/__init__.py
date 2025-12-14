"""Flood Detection Multi-Agent System

Uses Coordinator + AgentTool pattern:
- Orchestrator decides which specialist agents to call
- Agents wrapped as tools via AgentTool
- Dynamic routing based on query intent

Architecture:
    User Query
        │
        ▼
    Orchestrator (root_agent)
        │── DataCollectionAgent (satellite imagery via MCP)
        │── FloodDetectionAgent (change detection analysis)
        └── ImpactAssessmentAgent (damage & evacuation)

Usage:
    # ADK Web UI
    cd flood_agent
    adk web

    # ADK CLI
    adk run agents

    # Programmatic
    from agents import root_agent
"""

from .agent import root_agent

__all__ = ["root_agent"]
