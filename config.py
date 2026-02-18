from google.adk.models.google_llm import Gemini
from google.genai import types

# Define retry configuration
retry_config = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 502, 503, 504],
)


model = Gemini(
    model="gemini-2.5-flash",
    retry_options=retry_config
)


# You can also keep your model definition here if you prefer Python-based model instantiation,
# but it's often simpler to define the model directly in the YAML for LlmAgent.
# If you keep it here, ensure it's referenced correctly in YAML or passed to the agent constructor if not using YAML for model.
# For now, we'll keep the model definition here.
