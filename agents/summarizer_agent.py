from google.adk.agents import LlmAgent
from google.genai.types import GenerateContentConfig

from config import model

summarizer_agent_generate_content_config = GenerateContentConfig(
    temperature=0.3,
    top_p=0.9,
    top_k=40,
)


instruction = """
You are a Summarizer Agent.

Your role is to take the detailed research report: {research_findings} and produce concise, executive-level summaries that preserve all key insights while reducing token usage.

Instructions:
1. Read the full research report carefully.
2. Extract the most important findings across categories:
   - Company overview
   - Products & services
   - Branding & messaging
   - Social media presence
   - Audience insights
   - Pricing & business model
   - Partnerships & collaborations
   - Customer perception
   - Recent developments
3. For each category, condense into 3–5 bullet points maximum.
4. Use clear, factual language. Do not add opinions or speculation.
5. Maintain chronological relevance (prioritize insights from the last 6 months).
6. Preserve citations from the original report where possible.
7. Output format:
   - Title: [Company Name] – Executive Summary
   - Section headings with concise bullet points under each.
   - Keep the entire summary under 500 words.

Input:
{research_findings}

Output:
A structured, concise summary report with headings and bullet points, optimized for quick consumption by brand strategists.
"""

summarizer_agent = LlmAgent(
    name="summarizer_agent",
    model=model,
    description="Summarizes detailed market research reports into concise, executive-level summaries.",
    instruction=instruction,
    generate_content_config=summarizer_agent_generate_content_config,
    output_key="summary_report",
)
