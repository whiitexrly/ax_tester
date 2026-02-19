from google.adk.agents import SequentialAgent
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.tools.tool_context import ToolContext

from agents.static_agent.axe_core_agent import axe_agent
from agents.static_agent.llm_finder_agent import loop_agent
from agents.static_agent.init_agent import init_agent

import logging

from schemas import StaticReport
from common import ContextKey, MODEL

logger = logging.getLogger(__name__)


def get_merge_agent_instruction(tool_context: ToolContext) -> str:
    import json

    loop_report = tool_context.state.get(ContextKey.LOOP_REPORT, '[]')
    axe_report = tool_context.state.get(ContextKey.AXE_REPORT, {})
    axe_issue_list = []
    if isinstance(axe_report, dict):
        axe_issue_list = axe_report.get("data", {}).get("issue_list", [])
    axe_report_json = json.dumps(axe_issue_list, ensure_ascii=True)

    return f"""
        You are a REPORT MERGER tasked with combining two accessibility issue reports into one comprehensive report.
        Merge axe_report_issue_list and loop_report into a comprehensive unified report.
        Note that axe_report_issue_list is pre-normalized into issue_list schema.
        Make sure to include all issue from axe_report_issue_list and loop_report, but de-duplicate same issue.

        axe_report_issue_list:
        {axe_report_json}

        loop_report:
        {loop_report}
        """ + """

        Merging rules:
        1. De-duplicate by WCAG rule + similar description
        2. If same issue found by both: mark as 'confidence: high'
        3. Preserve all unique issues from both sources
        4. Add 'source' field: 'axe' | 'llm' | 'both'

        Summary must include:
        - total_issues: number of unique issues
        - by_severity: count per severity level
        - by_source: axe_only, llm_only, both
        - by_wcag_level: count per WCAG level (A, AA, AAA)
        - coverage_score: estimated % of issues found (0-100)
        - top_priorities: list of 5 most critical issues to fix first

        Return ONLY the JSON object, no other text.
        Keep html_snippet concise and valid JSON strings.
    """

axe_llm_agent = ParallelAgent(
    name="AxeAndLLMAgent",
    sub_agents=[axe_agent, loop_agent],
    description=(
        "Run axe-core and the LLM loop audit. "
        "Wait for both to complete, then return a brief confirmation."
    ),
)

merge_agent = LlmAgent(
    name="MergeReportsAgent",
    model=MODEL,
    instruction=get_merge_agent_instruction,
    output_schema=StaticReport,
    description="Merge axe-core and LLM loop reports into a unified accessibility report.",
    output_key=ContextKey.STATIC_REPORT,
)

static_analysis_agent = SequentialAgent(
    name="StaticAccessibilityAgent",
    description="Run axe-core and LLM loop audit to generate comprehensive accessibility report.",
    sub_agents=[init_agent, axe_llm_agent, merge_agent],
)
