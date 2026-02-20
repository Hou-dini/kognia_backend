from google.adk.models.google_llm import Gemini
from google.genai import types

# Define retry configuration
retry_config = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 502, 503, 504],
)


nexus_model = Gemini(
    model="gemini-2.5-pro",
    retry_options=retry_config
)

specialist_model = Gemini(
    model="gemini-3-flash-preview",
    retry_options=retry_config
)

# Configuration following Gemini 3 guidelines (temperature 1.0, high thinking)
gemini_3_config = types.GenerateContentConfig(
    temperature=1.0,
    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.HIGH)
)

# Legacy model reference
model = specialist_model


# You can also keep your model definition here if you prefer Python-based model instantiation,
# but it's often simpler to define the model directly in the YAML for LlmAgent.
# If you keep it here, ensure it's referenced correctly in YAML or passed to the agent constructor if not using YAML for model.
# For now, we'll keep the model definition here.
