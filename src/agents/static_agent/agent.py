from google.adk.agents import SequentialAgent
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.parallel_agent import ParallelAgent

from agents.static_agent.axe_core_agent import axe_agent
from agents.static_agent.llm_finder_agent import loop_agent
from agents.static_agent.init_agent import init_agent

from common import ContextKey, MODEL

MERGE_AGENT_INSTRUCTION = """
    Merge axe_report and loop_report into a comprehensive unified report.

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
"""

axe_llm_agent = ParallelAgent(
    name="AxeAndLLMAgent",
    sub_agents=[axe_agent, loop_agent],
    description=(
        "Run axe-core and the LLM loop audit in parallel. "
        "Use the run_axe_core tool and the loop agents. "
        "Wait for both to complete, then return a brief confirmation."
    ),
)

merge_agent = LlmAgent(
    name="MergeReportsAgent",
    model=MODEL,
    instruction=MERGE_AGENT_INSTRUCTION,
    description="Merge axe-core and LLM loop reports into a unified accessibility report.",
    output_key=ContextKey.MERGED_REPORT,
)


static_analysis_agent = SequentialAgent(
    name="StaticAccessibilityAgent",
    description="Run axe-core and LLM loop audit to generate comprehensive accessibility report.",
    sub_agents=[init_agent, axe_llm_agent, merge_agent],
)
