from google.adk.agents import LlmAgent

from config import model


instruction = """
You are a strategic SWOT analysis expert. Based on the research findings
  provided by the 'research_agent', meticulously identify and categorize the
  Strengths, Weaknesses, Opportunities, and Threats for the target brand and its
  key competitors.

  Provide clear, concise points for each category, supported by evidence from
  the research data.

  Structure your output logically, making it easy to understand the strategic
  implications for each entity.
    """
swot_analyzer_agent = LlmAgent(
    name="swot_analyzer_agent",
    model=model,
    description="Analyzes the research data to identify strengths, weaknesses,"
    "opportunities, and threats for the target brand and its competitors.",
    include_contents='none',
    instruction=instruction,
)