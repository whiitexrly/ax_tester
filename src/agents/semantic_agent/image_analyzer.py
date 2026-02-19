from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.tool_context import ToolContext

from common import ContextKey, MODEL
from tools import ImageAnalyzerTool
from tools.base import ToolResult


IMAGE_ANALYZER_INSTRUCTIONS = """
    Run the tool analyze_image with a URL to extract images and alt text from the page, 
    and analyze if the alt text is appropriate for the image content. 
    Store the result in tool_context.state under the key ContextKey.IMAGE_ANALYZER_REPORT.
    The result should be a list of issues found, where each issue includes the image URL,
    alt text, and a brief description of any problems detected (e.g., missing alt text, 
    alt text not matching image content). Return a brief confirmation message indicating 
    how many images were analyzed and how many issues were found.
"""

def analyze_images_in_webpage(tool_context: ToolContext, url: str) -> dict:
    """
    Analyze images on the given URL for alt text issues and store results in tool_context.state.

    Args:
        tool_context (ToolContext): The context for the tool execution, used to store results.
        url (str): The URL of the webpage to analyze.

    Returns:
        dict: A confirmation message indicating the number of images analyzed and issues found.
    """
    result: ToolResult = ImageAnalyzerTool().execute(url).to_dict()
    tool_context.state[ContextKey.IMAGE_ANALYZER_REPORT] = result
    return {
        "status": "success" if result['status'] == "success" else "failure",
        "message": f"Analyzed {len(result['data'].get('issue_list', []))} image issues on {url}.",
        "state_key": ContextKey.IMAGE_ANALYZER_REPORT
    }


image_analyzer = LlmAgent(
    name="ImageAnalyzer",
    model=MODEL,
    description="Analyzes images in a webpage and ensure they have consistent alt text.",
    instruction=IMAGE_ANALYZER_INSTRUCTIONS,
    tools=[analyze_images_in_webpage],
)