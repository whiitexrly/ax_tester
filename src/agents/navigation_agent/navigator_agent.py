from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.tool_context import ToolContext

from common import MODEL
from tools import RuntimeNavigatorTool
from tools.base import ToolResult

RUNTIME_NAVIGATOR_INSTRUCTIONS = """
    Run the tool analyze_runtime_navigation with a URL to perform runtime navigation.
    Store the result in tool_context.state under the key ContextKey.RUNTIME_NAVIGATION_REPORT.
    Return a brief confirmation message with the number of issues found by consumers.
"""


def analyze_runtime_navigation(
    tool_context: ToolContext,
    url: str,
    headless: bool = True,
    max_steps: int = 200,
) -> dict:
    """Run runtime navigation and store results in agent state."""

    result: ToolResult = (
        RuntimeNavigatorTool(
            {
                "headless": headless,
                "max_steps": max_steps,
            }
        )
        .execute(url)
        .to_dict()
    )

    consumer_results = result.get("data", {}).get("consumer_results", []) or []
    for item in consumer_results:
        issues = item.get("result").get("issue_list")
        key = item.get("report_key")
        tool_context.state[key] = issues

    return {
        "status": "success" if result["status"] == "success" else "failure",
        "message": f"Runtime navigation completed on {url}.",
    }


navigator_agent = LlmAgent(
    name="RuntimeNavigator",
    model=MODEL,
    description="Runs runtime navigation and aggregates consumer findings.",
    instruction=RUNTIME_NAVIGATOR_INSTRUCTIONS,
    tools=[analyze_runtime_navigation],
)
