"""Root agent definition for the Pharma R&D & Regulatory Radar demo."""

from google.adk.agents import Agent
from google.adk.tools import google_search

from .prompts import AGENT_DESCRIPTION, SYSTEM_INSTRUCTION

AGENT_NAME: str = "pharma_rd_radar"
MODEL_NAME: str = "gemini-3.8-flash"

root_agent: Agent = Agent(
    name=AGENT_NAME,
    model=MODEL_NAME,
    description=AGENT_DESCRIPTION,
    instruction=SYSTEM_INSTRUCTION,
    tools=[google_search],
)

