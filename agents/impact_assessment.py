"""Impact Assessment Agent - Damage Analysis Specialist

This agent provides flood impact analysis:
- Building impact estimation
- Economic damage calculation
- Evacuation planning and routes
- Emergency response recommendations
"""

from google.adk.agents import LlmAgent

from .prompts import IMPACT_ASSESSMENT_PROMPT


impact_assessment_agent = LlmAgent(
    name="ImpactAssessmentAgent",
    model="gemini-2.0-flash",
    description=(
        "Impact assessment specialist. Call this agent with flood severity "
        "and affected areas to estimate damage, affected buildings, economic "
        "impact, and evacuation recommendations."
    ),
    instruction=IMPACT_ASSESSMENT_PROMPT,
)
