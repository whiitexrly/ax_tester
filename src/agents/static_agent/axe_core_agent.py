from google.adk.tools.tool_context import ToolContext
from google.adk.agents.llm_agent import LlmAgent

from typing import List, Optional

from tools import AxeCoreTool
from common import ContextKey, MODEL

def run_axe_core(
    url: str,
    tool_context: ToolContext,
    timeout: int = 30,
    rules: Optional[List[str]] = None,
    headless: bool = True,
) -> dict:
    """
    Run axe-core on the target URL and store the full report in agent state.

    Returns the serialized tool result from axe_core_tool.
    """

    result = AxeCoreTool({
        "timeout": timeout,
        "rules": rules,
        "headless": headless,
    }).execute(url).to_dict()
    
    tool_context.state[ContextKey.AXE_REPORT] = result
    return {"status": "axe_completed", "state_name": ContextKey.AXE_REPORT, "url_analyzed": url}

axe_agent = LlmAgent(
    name="RunAxeAgent",
    model=MODEL,
    instruction=(
        "Run axe-core for the target URL. "
        "Call run_axe_core once and return a brief confirmation."
    ),
    tools=[run_axe_core],
)