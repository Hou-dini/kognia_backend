import os
from google.genai import types

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools import google_search, AgentTool, preload_memory


GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_GENAI_USE_VERTEXAI= os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() == "true"


retry_config = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 502, 503, 504],
)



model = Gemini(
    model="gemini-2.5-flash",
    retry_options=retry_config,
)

market_research_agent = LlmAgent(
        name="Market_Research_Specialist",
        model=model,
        tools=[
            google_search,
            ],
        instruction= """
        You are a specialist researcher. 

        Your task is to gather relevant market research information based on the user's prompt.
        1. Use the Google Search tool to find up-to-date information.
        2. Summarize the findings clearly and concisely.
        """,
        output_key= "research_findings",
    )

research_tool = AgentTool(
    agent=market_research_agent,
)

root_agent = LlmAgent(
    name="Research_Manager_Agent",
    model=model,
    tools=[
        research_tool,
        preload_memory,
    ],
    instruction="""
    You are a senior research manager.

    You receive requests from users to conduct market research.
    1. For each request, delegate the research task to the Market Research Specialist agent.
    2. Collect the research findings and compile a final report.
    3. Ensure the report is clear, concise, and addresses the user's prompt.
    4. Return the final report to the user.
    """,
)

