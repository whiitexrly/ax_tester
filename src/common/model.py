from google.adk.models.lite_llm import LiteLlm

MODEL_NAME = "openai/gpt-5.2"
MODEL = LiteLlm(model=MODEL_NAME, temperature=0.7)
