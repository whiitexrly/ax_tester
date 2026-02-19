from typing import Any, Dict, List

import litellm

def call_llm(model: str, temperature: float, messages: List[Dict[str, Any]]) -> str:
    resp = litellm.completion( model=model, messages=messages, temperature=temperature,)

    if isinstance(resp, str):
        return resp
    if hasattr(resp, "choices") and resp.choices:
        choice = resp.choices[0]
        if hasattr(choice, "message") and isinstance(choice.message, dict):
            return choice.message.get("content", "")
        if hasattr(choice, "message") and hasattr(choice.message, "content"):
            return choice.message.content
        if hasattr(choice, "text"):
            return choice.text
    if isinstance(resp, dict):
        choices = resp.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            return message.get("content", "") or choices[0].get("text", "")
    return ""