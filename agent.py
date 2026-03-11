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
from common import MODEL, ContextKey
from utils.report_excel import build_excel_report
from utils.report_pptx import build_pptx_report


def run_save(tool_context: ToolContext):
    import json
    import os
    from datetime import datetime

    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    results_dir = f"ax_tester/results/{date_str}"
    os.makedirs(results_dir, exist_ok=True)

    report_names = [
        ContextKey.STATIC_REPORT,
        ContextKey.IMAGE_ANALYZER_REPORT,
        ContextKey.FOCUS_VISIBLE_REPORT,
        ContextKey.ON_FOCUS_REPORT,
        ContextKey.NO_KEYBOARD_TRAP_REPORT,
    ]

    all_issues: list[dict] = []
    for report_name in report_names:
        report_data = tool_context.state.get(report_name, {})
        issue_list = report_data.get("issue_list", []) if isinstance(report_data, dict) else []
        all_issues.extend(issue_list)

        with open(f"{results_dir}/{report_name.lower()}.json", "w", encoding="utf-8") as file:
            json.dump(report_data, file, indent=2, ensure_ascii=False)

    aggregate_report = {
        "tool_name": "ax_tester",
        "total_issues": len(all_issues),
        "page": tool_context.state.get(ContextKey.STATIC_REPORT, {}).get("page", ""),
        "issue_list": all_issues,
        "metadata": [],
    }
    with open(f"{results_dir}/report.json", "w", encoding="utf-8") as file:
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

root_agent = SequentialAgent(
    name="AccessibilityAgent",
    description="Performs static, semantic and dynamic analysis on a web page, given an URL",
    sub_agents=[
        static_analysis_agent,
        image_analyzer_agent,
        navigator_agent,
        saver,
    ],
)
