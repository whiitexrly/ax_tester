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
    ]

    for report in report_names:
        with open(f"{results_dir}/{report.lower()}.json", "w") as f:
            json.dump(tool_context.state.get(report), f, indent=2, ensure_ascii=False)

    build_excel_report(results_dir, report_names)


saver = LlmAgent(
    name="Saver",
    model=MODEL,
    description="Use tool `run_save`.",
    instruction="Use tool `run_save`.",
    tools=[run_save],
)

root_agent = SequentialAgent(
    name="AccessibilityAgent",
    description="Performs static and semantic analysis on a web page, given an URL",
    sub_agents=[
        static_analysis_agent,
        image_analyzer_agent,
        navigator_agent,
        saver,
    ],
)
