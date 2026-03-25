"""ADK entrypoint for the ax-tester agent.

This file exposes root_agent for ADK discovery while keeping the implementation
inside src/agents.
"""

from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.tools.tool_context import ToolContext

from agents.navigation_agent import navigator_agent
from agents.semantic_agent import image_analyzer_agent
from agents.static_agent import static_analysis_agent
from common import FINAL_REPORT_KEYS, MODEL, ContextKey
from utils.browser_session import BROWSER_SESSION
from utils.report_excel import build_excel_report
from utils.report_pptx import build_pptx_report

ROOT_AGENT_INSTRUCTION = """
You are the root orchestrator for the accessibility workflow.

Available tools:
- `initialize_session`: creates a fresh shared browser session.
- `navigate_to_page(url)`: opens the requested page in the shared browser.
- `is_initialized`: verify whether the browser and page are initialized.

Available sub-agent:
- `AccessibilityTesterAgent`: runs the full analysis pipeline on the current page.


Execution policy:
1. Extract the target URL from the user message.
2. If no URL is provided, ask one concise follow-up question requesting it, then stop.
3. Ensure an active session exists:
   - If `is_initialized` is not true, call `initialize_session`.
4. Call `navigate_to_page` with the requested URL.
5. Before running analysis, ask the user to confirm the visible browser page is the intended one.
6. Exception: if the user explicitly asks to run the test immediately without additional approval, skip the confirmation step.
7. Transfer to `AccessibilityTesterAgent` exactly once for that request.
8. Return a short completion message including the final URL.

Reliability rules:
- If navigation fails because the browser session is unavailable, call `initialize_session` and retry `navigate_to_page` once.
- Do not run unrelated tools or extra analysis passes.
- If a step fails, report which step failed and ask only for the minimum information needed to continue.
"""


async def initialize_session(tool_context: ToolContext) -> dict[str, str]:
    """Initialize a fresh shared browser session."""
    await BROWSER_SESSION.create_session()

    return {
        "status": "initialized",
        "browser_initialized": True,
        "url": BROWSER_SESSION.page.url,
    }


async def navigate_to_page(tool_context: ToolContext, url: str) -> dict[str, str]:
    """Navigate the shared browser session to a target URL."""
    await BROWSER_SESSION.goto(url=url)

    return {"status": "success", "url": BROWSER_SESSION.page.url}


async def is_initialized(tool_context: ToolContext) -> bool:
    """Return whether the shared browser session is ready for navigation/testing."""
    return BROWSER_SESSION.is_initialized()


def run_save(tool_context: ToolContext):
    import json
    import os
    from datetime import datetime

    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    results_dir = f"ax_tester/results/{date_str}"
    os.makedirs(results_dir, exist_ok=True)

    all_issues: list[dict] = []
    for report_name in FINAL_REPORT_KEYS:
        report_data = tool_context.state.get(report_name, {})
        with open(f"{results_dir}/{report_name.lower()}.json", "w", encoding="utf-8") as file:
            json.dump(report_data, file, indent=2, ensure_ascii=False)

        issue_list = report_data.get("issue_list", []) if isinstance(report_data, dict) else []
        issue_list = [issue for issue in issue_list if issue.get("severity", "") != "minor"]
        all_issues.extend(issue_list)

    aggregate_report = {
        "tool_name": "ax_tester",
        "total_issues": len(all_issues),
        "page": tool_context.state.get(ContextKey.STATIC_REPORT, {}).get("page", ""),
        "issue_list": all_issues,
        "metadata": [],
    }
    with open(f"{results_dir}/ax_report.json", "w", encoding="utf-8") as file:
        json.dump(aggregate_report, file, indent=2, ensure_ascii=False)

    build_excel_report(results_dir)
    build_pptx_report(results_dir)


saver = LlmAgent(
    name="Saver",
    model=MODEL,
    description="Save results in local repository",
    instruction="Use tool `run_save`.",
    tools=[run_save],
)

tester_agent = SequentialAgent(
    name="AccessibilityTesterAgent",
    description="Performs static, semantic and dynamic analysis on the current open page",
    sub_agents=[
        static_analysis_agent,
        image_analyzer_agent,
        navigator_agent,
        saver,
    ],
)

root_agent = LlmAgent(
    name="RootAgent",
    model=MODEL,
    description="",
    instruction=ROOT_AGENT_INSTRUCTION,
    sub_agents=[tester_agent],
    tools=[initialize_session, is_initialized, navigate_to_page],
)
