from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.tool_context import ToolContext

from common import MODEL, ContextKey
from tools import AxeCoreTool


def run_axe_core(
    tool_context: ToolContext,
    url: str,
    timeout: int = 30,
    rules: list[str] | None = None,
    headless: bool = True,
) -> dict:
    """Run axe-core on the target URL and store the full report in agent state.

    Args:
        tool_context (ToolContext): The context for the tool execution, used to store results.
        url (str): The URL of the webpage to analyze.
        timeout (int): Maximum time in seconds to wait for axe-core to complete. (options: default 30)
        rules (List[str], optional): Specific axe-core rules to run. If None, all rules are run. (options: default None)
        headless (bool): Whether to run the browser in headless mode. (options: default True)

    Returns:
        dict: A confirmation message indicating that axe-core has completed and where the report is stored in the agent state.

    """
    result = (
        AxeCoreTool(
            {
                "timeout": timeout,
                "rules": rules,
                "headless": headless,
            }
        )
        .execute(url)
        .to_dict()
    )

    tool_context.state[ContextKey.AXE_REPORT] = result
    return {"status": "axe_completed", "state_key": ContextKey.AXE_REPORT, "url_analyzed": url}


axe_agent = LlmAgent(
    name="RunAxeAgent",
    model=MODEL,
    instruction=("Run axe-core for the target URL. Call run_axe_core once and return a brief confirmation."),
    tools=[run_axe_core],
)
