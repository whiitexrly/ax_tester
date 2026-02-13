from google.adk.agents import SequentialAgent
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.tools.tool_context import ToolContext

import json

from agents.static_agent.axe_core_agent import axe_agent
from agents.static_agent.llm_finder_agent import loop_agent
from agents.static_agent.init_agent import init_agent

from tools import json_formatter

from common import ContextKey, MODEL


def get_merge_agent_instruction(tool_context: ToolContext) -> str:
    loop_report = tool_context.state.get(ContextKey.LOOP_REPORT, '[]')
    axe_report = tool_context.state.get(ContextKey.AXE_REPORT, '[]')
    axe_report_json = json.dumps(axe_report, ensure_ascii=True)

    instruction = f"""You are a REPORT MERGER tasked with combining two accessibility issue reports into one comprehensive report.
Merge axe_report and loop_report into a comprehensive unified report.
Note that axe_report violations contains all violations under 'node' for the same issue.
Make sure to include all issue from axe_report and loop_report, but de-duplicate same issue.

axe_report:
{axe_report_json}

loop_report:
{loop_report}
""" + """

Output JSON structure:
{
"issues": [...],        // De-duplicated combined issues from axe and llm
"summary": {...}        // Statistics and insights
}

Merging rules:
1. De-duplicate by WCAG rule + similar description
2. If same issue found by both: mark as 'confidence: high'
3. Preserve all unique issues from both sources
4. Add 'source' field: 'axe' | 'llm' | 'both'

Merged item format:
{
"id": "unique-id",
"wcag_rule": "1.1.1 - Non-text Content (Level A)",
"description": "...",
"severity": "critical|serious|moderate|minor",
"source": "axe|llm|both",
"confidence": "high|medium|low",
"html_snippet": "...",
"fix": "..."
}

Summary must include:
- total_issues: number of unique issues
- by_severity: count per severity level
- by_source: axe_only, llm_only, both
- by_wcag_level: count per WCAG level (A, AA, AAA)
- coverage_score: estimated % of issues found (0-100)
- top_priorities: list of 5 most critical issues to fix first

Return ONLY the JSON object, no other text.
Make sure to add back slash \ in html snippets to avoid json parsing issues.
"""
    return instruction

def json_formatter_tool(tool_context: ToolContext) -> dict:
    """
    Tool to format the merged report into clean validated JSON.
    """
    merged_report = tool_context.state.get(ContextKey.MERGED_REPORT, "")
    formatted_report = json_formatter(str(merged_report))
    tool_context.state[ContextKey.FINAL_REPORT] = formatted_report
    return {"formatted_report": formatted_report}

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
    description="Merge axe-core and LLM loop reports into a unified accessibility report.",
    output_key=ContextKey.MERGED_REPORT,
)

json_formatter_agent = LlmAgent(
    name="JsonFormatterAgent",
    model=MODEL,
    instruction="You are a JSON FORMATTER. Format the merged report into clean validated JSON using the json_formatter_tool",
    tools=[json_formatter_tool],
    output_key=ContextKey.FINAL_REPORT,
)

static_analysis_agent = SequentialAgent(
    name="StaticAccessibilityAgent",
    description="Run axe-core and LLM loop audit to generate comprehensive accessibility report.",
    sub_agents=[init_agent, axe_llm_agent, merge_agent, json_formatter_agent],
)
