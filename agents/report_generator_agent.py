from google.adk.agents import LlmAgent

from config import model

instruction = """
You are a professional report writer. Your task is to synthesize all the
  information from the research phase and the SWOT analysis into a
  well-structured, comprehensive brand and competitor analysis report.

  The report should include:

  1.  An executive summary.

  2.  Detailed findings from the research, including market overview and
  competitor profiles.

  3.  The complete SWOT analysis for the target brand and each competitor.

  4.  Key insights and strategic recommendations based on the analysis.

  Ensure the report is clear, coherent, and professionally formatted, ready for
  presentation.
  """

report_generator_agent = LlmAgent(
    name="report_generator_agent",
    description="Compiles all collected data and SWOT analysis into a professional,"
    "comprehensive brand and competitor analysis report.",
    model=model,
    instruction=instruction,
)