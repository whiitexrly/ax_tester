from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.tool_context import ToolContext

from common import MODEL, ContextKey
from schemas import ImageAnalyzerReport
from tools import ImageAnalyzerTool
from tools.base import ToolResult

IMAGE_ANALYZER_INSTRUCTIONS = """
    Run the tool analyze_image with a URL to extract images and alt text from the page,
    and analyze if the alt text is appropriate for the image content.
    Store the result in tool_context.state under the key ContextKey.IMAGE_ANALYZER_REPORT.
    The result uses data.issue_list with fields:
    id, wcag_rule, description, severity, source, confidence, html_snippet, fix.
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
    validated = ImageAnalyzerReport.model_validate(raw.data)
    result = raw.to_dict()
    result["data"] = validated.model_dump()
    tool_context.state[ContextKey.IMAGE_ANALYZER_REPORT] = result
    return {
        "status": "success" if result["status"] == "success" else "failure",
        "message": f"Analyzed {len(result['data'].get('issue_list', []))} image issues on {url}.",
        "state_key": ContextKey.IMAGE_ANALYZER_REPORT,
    }


image_analyzer = LlmAgent(
    name="ImageAnalyzer",
    model=MODEL,
    description="Analyzes images in a webpage and ensure they have consistent alt text.",
    instruction=IMAGE_ANALYZER_INSTRUCTIONS,
    tools=[analyze_images_in_webpage],
)
