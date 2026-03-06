from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.tool_context import ToolContext

from common import MODEL
from schemas import Report
from tools import RuntimeNavigatorTool

RUNTIME_NAVIGATOR_INSTRUCTIONS = """
    Run the tool analyze_runtime_navigation with a URL to perform runtime navigation.
    Store each consumer report in tool_context.state under its own report key.
    Return a brief confirmation message with the number of issues found by consumers.
"""


def analyze_runtime_navigation(
    tool_context: ToolContext,
    url: str,
    headless: bool = True,
    max_steps: int = 200,
) -> dict:
    """Run runtime navigation and store results in agent state."""

    result: dict = (
        RuntimeNavigatorTool(
            {
                # "headless": headless,
                "headless": False,
                "max_steps": max_steps,
            }
        )
        .execute(url)
        .to_dict()
    )

    consumer_results = result.get("data", {}).get("consumer_results", []) or []
    updated_keys = []
    for consumer_result in consumer_results:
        report_key = consumer_result.get("report_key")
        if not report_key:
            continue
        report_dict = Report.model_validate(
            {
                "tool_name": consumer_result.get("result", {}).get("name"),
                "issue_list": consumer_result.get("result", {}).get("issue_list"),
                "total_issues": len(consumer_result.get("result", {}).get("issue_list")),
                "page": url,
                "metadata": [
                    {"key": "checked", "value": consumer_result.get("result").get("checked")},
                ],
            }
        ).model_dump()

        tool_context.state[report_key] = report_dict
        updated_keys.append(report_key)

    return {
        "status": "success" if result["status"] == "success" else "failure",
        "message": f"Runtime navigation completed on {url}. Updated reports: {updated_keys}.",
    }


navigator_agent = LlmAgent(
    name="RuntimeNavigator",
    model=MODEL,
    description="Runs runtime navigation and aggregates consumer findings.",
    instruction=RUNTIME_NAVIGATOR_INSTRUCTIONS,
    tools=[analyze_runtime_navigation],
)
