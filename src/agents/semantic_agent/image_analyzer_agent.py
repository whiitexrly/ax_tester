from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.tool_context import ToolContext

from common import MODEL, ContextKey
from schemas import Report
from tools import ImageAnalyzerTool
from tools.base import ToolResult

IMAGE_ANALYZER_INSTRUCTIONS = """
    Run the tool `analyze_images_in_webpage` with a URL to extract images and alt text from the page,
    and analyze if the alt text is appropriate for the image content.
    Store the result in tool_context.state under the key ContextKey.IMAGE_ANALYZER_REPORT.
    The report issue_list uses fields:
    id, wcag_rule, description, severity, source, confidence, html_snippet, fix, image_url_or_path.
    Return a brief confirmation message indicating how many issues were found.
"""


def analyze_images_in_webpage(tool_context: ToolContext, url: str) -> dict:
    """Analyze images on the given URL for alt text issues and store results in tool_context.state.

    Args:
        tool_context (ToolContext): The context for the tool execution, used to store results.
        url (str): The URL of the webpage to analyze.

    Returns:
        dict: A confirmation message indicating the number of images analyzed and issues found.

    """
    raw: ToolResult = ImageAnalyzerTool().execute(url)
    data = raw.data if isinstance(raw.data, dict) else {}
    issue_list = data.get("issue_list", [])

    report = Report.model_validate(
        {
            "tool_name": raw.tool_name,
            "issue_list": issue_list,
            "total_issues": len(issue_list),
            "page": url,
            "metadata": [
                {"key": "status", "value": raw.status.value},
                {"key": "error", "value": raw.error or ""},
                {"key": "skipped", "value": data.get("skipped", 0)},
            ],
        }
    ).model_dump()
    tool_context.state[ContextKey.IMAGE_ANALYZER_REPORT] = report

    return {
        "status": "success" if raw.status.value == "success" else "failure",
        "message": f"Analyzed {len(issue_list)} image issues on {url}.",
        "state_key": ContextKey.IMAGE_ANALYZER_REPORT,
    }


image_analyzer_agent = LlmAgent(
    name="ImageAnalyzer",
    model=MODEL,
    description="Analyzes images in a webpage and ensure they have consistent alt text.",
    instruction=IMAGE_ANALYZER_INSTRUCTIONS,
    tools=[analyze_images_in_webpage],
)
