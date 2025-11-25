from google.adk.agents import SequentialAgent

from agents.research_agent import research_agent
from agents.swot_analyzer_agent import swot_analyzer_agent
from agents.report_generator_agent import report_generator_agent


analysis_orchestrator = SequentialAgent(
    name="research_orchestrator",
    description="Orchestrates market research and competitor analysis workflows.",
)