"""Root agent definition for the Pharma R&D & Regulatory Radar demo."""

import os

from google.adk.agents import Agent
from google.adk.models import Gemini
from google.adk.tools import google_search

from .prompts import AGENT_DESCRIPTION, SYSTEM_INSTRUCTION

AGENT_NAME: str = "pharma_rd_radar"
MODEL_NAME: str = "gemini-3.8-flash"
VERTEX_MODEL_LOCATION: str = "global"


def _build_gemini_model() -> Gemini:
    """Route Gemini 3.x calls to 'global' on Vertex AI while preserving local AI Studio."""
    use_vertex_ai: bool = any(
        os.getenv(env_var, "").strip().lower() in {"1", "true", "yes"}
        for env_var in ("GOOGLE_GENAI_USE_ENTERPRISE", "GOOGLE_GENAI_USE_VERTEXAI")
    )
    if use_vertex_ai:
        return Gemini(
            model=MODEL_NAME,
            client_kwargs={"location": VERTEX_MODEL_LOCATION},
        )
    return Gemini(model=MODEL_NAME)


root_agent: Agent = Agent(
    name=AGENT_NAME,
    model=_build_gemini_model(),
    description=AGENT_DESCRIPTION,
    instruction=SYSTEM_INSTRUCTION,
    tools=[google_search],
)
