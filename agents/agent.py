from google.adk.agents import LlmAgent

from config import model
from agents.analysis_orchestrator import analysis_orchestrator


instruction = """
  You are the central BrandSpark agent. Your primary role is to understand user
  requests for brand and competitor analysis, and then delegate the execution to
  the 'analysis_orchestrator' sub-agent to perform the full workflow, which
  includes research, SWOT analysis, and report generation.

  Do not perform analysis yourself; always use the 'transfer_to_agent' tool to
  pass the user's request to the 'analysis_orchestrator' for processing.
  """

root_agent = LlmAgent(
    name="brandspark_agent",
    description="The main agent for BrandSpark," 
    "responsible for initiating brand and competitor analysis workflows.",
    model=model,
    instruction=instruction,
    sub_agents=[analysis_orchestrator],
)


