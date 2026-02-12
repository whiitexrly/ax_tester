from google.adk.tools.tool_context import ToolContext
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.loop_agent import LoopAgent

from typing import Any, Dict
from pathlib import Path

from common import ContextKey, MODEL

def exit_loop(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Signal the loop agent to stop iterating.
    """
    tool_context.actions.end_of_agent = True
    tool_context.actions.skip_summarization = True
    return {"status": "complete"}

REPO_ROOT = Path(__file__).resolve().parents[2]
WCAG_PROMPT_PATH = REPO_ROOT / "prompts" / "wcag.yml"
WCAG_PROMPT_CONTENT = WCAG_PROMPT_PATH.read_text(encoding="utf-8")

LOOP_FINDER_AGENT_INSTRUCTION = f"""
    You are the loop auditor. Analyze dom_html and loop_report in toolcontext 
    to find all possible accessibility issues based on WCAG 2.2 criteria.
    Here are the WCAG criteria and common issue types to check for:
    \n{WCAG_PROMPT_CONTENT}\n
    Return ONLY a JSON array representing the UPDATED FULL report 
    (merge existing + new). Each item must include: wcag_rule 
    (SC id + title + level), description (include user impact and fix), 
    html (evidence snippet), severity (critical|serious|moderate|minor). 
    Do not include criteria outside the selected level set.
"""

LOOP_COMPLETENESS_INSTRUCTION = """
    Assess whether loop_report covers all major accessibility issues inferable from dom_html.

    Check coverage of all WCAG criteria relevant to the selected level set, and common issues like missing alt text, link text, form labels, heading structure, etc.

    Decision criteria:
    - If significant gaps remain: return "Missing: [specific category]"

    Examples of when to exit:
    - "All major element types covered, edge cases may remain" → exit_loop()
    - "Images, links, headings, forms all analyzed" → exit_loop()

    Examples of when to continue:
    - "Missing: form input label analysis"
    - "Missing: link text review in footer section"
    - "Missing: heading hierarchy validation"

    Return ONLY one of:
    1. Call exit_loop() if complete
    2. Single sentence starting with "Missing:" if incomplete
"""

loop_finder_agent = LlmAgent(
    name="LoopFinderAgent",
    model=MODEL,
    instruction=LOOP_FINDER_AGENT_INSTRUCTION,
    output_key=ContextKey.LOOP_REPORT,
)

loop_completeness_agent = LlmAgent(
    name="LoopCompletenessAgent",
    model=MODEL,
    instruction=LOOP_COMPLETENESS_INSTRUCTION,
    tools=[exit_loop],
    output_key=ContextKey.LOOP_NOTES,
)

loop_agent = LoopAgent(
    name="AccessibilityLoopAgent",
    sub_agents=[loop_finder_agent, loop_completeness_agent],
    max_iterations=5,
)