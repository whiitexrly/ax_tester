from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.tool_context import ToolContext

from common import MODEL
from schemas import Report
from tools import RuntimeNavigatorTool
from tools.base import ToolResult


async def analyze_runtime_navigation(
    tool_context: ToolContext,
    max_steps: int = 200,
) -> dict:
    """Run runtime navigation on the current page and store results in agent state."""
    raw_result: ToolResult = await RuntimeNavigatorTool({"max_steps": max_steps}).execute()
    result: dict = raw_result.to_dict()
    page_url = result.get("data", {}).get("page_url", "")

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
                "page": page_url,
                "metadata": [
                    {"key": "checked", "value": consumer_result.get("result").get("checked")},
                ],
            }
        ).model_dump()

        tool_context.state[report_key] = report_dict
        updated_keys.append(report_key)

    return {
        "status": "success" if result["status"] == "success" else "failure",
        "message": f"Runtime navigation completed on {page_url}. Updated reports: {updated_keys}.",
    }


navigator_agent = LlmAgent(
    name="RuntimeNavigatorAgent",
    model=MODEL,
    description="Runs runtime navigation and aggregates consumer findings.",
    instruction="Call `analyze_runtime_navigation` once and return a brief confirmation.",
    tools=[analyze_runtime_navigation],
)
