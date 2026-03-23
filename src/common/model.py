import litellm
from google.adk.models.lite_llm import LiteLlm

litellm.drop_params = True

MODEL_NAME = "openai/gpt-5.4"
MODEL = LiteLlm(model=MODEL_NAME, temperature=0.7)

DUMMY_MODEL_NAME = "openai/gpt-4o"
DUMMY_MODEL = LiteLlm(model=DUMMY_MODEL_NAME, temperature=0.7)
