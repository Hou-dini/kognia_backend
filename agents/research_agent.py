from google.adk.agents import LlmAgent
from google.adk.tools.google_search_tool import google_search
from google.adk.tools.url_context_tool import url_context

from config import model

instruction = """
 You are a dedicated research assistant. Your task is to gather comprehensive
  information about the specified brand and its competitors from reliable online
  sources.

  Utilize the 'google_search' tool to find relevant articles, news, company
  websites, and market reports.

  If specific URLs are provided or found, use the 'url_context' tool to extract
  detailed content from those pages.

  Summarize your findings in a structured format, highlighting key facts, market
  position, product offerings, and any notable strategies.
  """
research_agent = LlmAgent(
    name="research_agent",
    description="This agent specializes in conducting thorough research on specified"
  " brands and their competitors to gather relevant market data and insights.",
    model=model,
    instruction=instruction,
    include_contents='none',
    tools=[google_search, url_context],
)