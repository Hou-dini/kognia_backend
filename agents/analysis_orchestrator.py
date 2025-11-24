from google.adk.agents import SequentialAgent

from agents.research_agent import research_agent
from agents.swot_analyzer_agent import swot_analyzer_agent
from agents.report_generator_agent import report_generator_agent


analysis_orchestrator = SequentialAgent(
    name="analysis_orchestrator",
    description="Orchestrates the sequential workflow for brand and competitor"
    " analysis, including research, SWOT analysis, and report generation.",
    sub_agents=[
        research_agent,
        swot_analyzer_agent,
        report_generator_agent,
    ],
)