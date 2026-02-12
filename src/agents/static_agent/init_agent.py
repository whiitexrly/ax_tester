from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.tool_context import ToolContext

from common import ContextKey, MODEL

from typing import Dict, Any
from pathlib import Path

import urllib.request

REPO_ROOT = Path(__file__).resolve().parents[2]

INIT_AGENT_INSTRUCTION = """
    Initialize state and DOM in parallel.
    Call init_loop_state once.
    If the user specified a WCAG level set, call set_wcag_level with A, AA, or AAA.
    Call load_dom_html with the target URL and store dom_html.
    Return only a short confirmation string.
    Make sure to call all the functions once with the correct arguments.
    Moreove, standardize the URL input by stripping whitespace and ensuring it starts with http:// or https://
"""

def init_loop_state(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Initialize loop-related state in the agent context.

    Creates empty placeholders for the LLM loop report and loop notes.
    """
    tool_context.state[ContextKey.LOOP_REPORT] = "[]"
    tool_context.state[ContextKey.LOOP_NOTES] = ""
    tool_context.state[ContextKey.WCAG_LEVEL] = 2
    return {"status": "initialized"}


def set_wcag_level(tool_context: ToolContext, level: str = 'AA') -> Dict[str, Any]:
    """
    Set the active WCAG level set for the loop audit.

    Accepts: A (Level A only), AA (A + AA), AAA (A + AA + AAA).
    """
    normalized = level.strip().upper()
    if normalized not in ['A', 'AA', 'AAA']:
        raise ValueError("wcag level must be one of: A, AA, AAA")
    tool_context.state[ContextKey.WCAG_LEVEL] = len(normalized)
    
    return {"status": "set", "wcag_level_set": normalized}


def load_dom_html(url: str, tool_context: ToolContext, timeout: int = 30) -> Dict[str, Any]:
    """
    Fetch the HTML DOM for a URL and store it in agent state.

    Returns a small status payload with the number of bytes loaded.
    """
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "adk-accessibility-agent/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    raw_html = raw.decode("utf-8", errors="replace")

    tool_context.state[ContextKey.DOM_HTML] = raw_html
    return {"status": "loaded", "bytes": len(raw)}


init_agent = LlmAgent(
    name="InitAgent",
    model=MODEL,
    instruction=INIT_AGENT_INSTRUCTION,
    tools=[init_loop_state, set_wcag_level, load_dom_html],
)