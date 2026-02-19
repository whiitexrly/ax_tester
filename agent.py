"""
ADK entrypoint for the ax-tester agent.

This file exposes root_agent for ADK discovery while keeping the implementation
inside src/agent/agent.py.
"""
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.tool_context import ToolContext

from common import MODEL, ContextKey

from agents.static_agent import static_analysis_agent
from agents.semantic_agent.image_analyzer import image_analyzer


def run_save(tool_context: ToolContext):

    from datetime import datetime
    import os
    import json

    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    results_dir = f"ax_tester/results/{date_str}"
    os.makedirs(results_dir, exist_ok=True)

    with open(f"{results_dir}/static_report.json", "w") as f:
        json.dump(tool_context.state.get(ContextKey.STATIC_REPORT), f, indent=2, ensure_ascii=False)

    with open(f"{results_dir}/image_analyzer_report.json", "w") as f:
        json.dump(tool_context.state.get(ContextKey.IMAGE_ANALYZER_REPORT), f, indent=2, ensure_ascii=False)

saver = LlmAgent(
    name='Saver',
    model=MODEL,
    description='use tool `save_results` to save data in file',
    tools=[run_save]
)

root_agent = SequentialAgent(
    name="AccessibilityAgent",
    description="Performs static and semantic analysis on a web page, given an URL",
    sub_agents=[static_analysis_agent, image_analyzer, saver]
)

# root_agent = image_analyzer
# root_agent = static_analysis_agent
