from google.adk.tools.tool_context import ToolContext
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.loop_agent import LoopAgent

from typing import Any, Dict

from common import ContextKey, MODEL


def get_finder_instruction(tool_context: ToolContext) -> str:
    html = tool_context.state.get(ContextKey.DOM_HTML, '')
    report = tool_context.state.get(ContextKey.LOOP_REPORT, '[]')
    wcag_prompt = tool_context.state.get(ContextKey.WCAG_PROMPT, '')
    checker_feedback = tool_context.state.get(ContextKey.LOOP_NOTES, '')
    
    instruction = f"""You are an accessibility issue FINDER for WCAG compliance.

WCAG 2.2 Reference:
{wcag_prompt}

HTML to Analyze:
{html}

Current Report:
{report}

{'Checker Feedback: ' + checker_feedback if checker_feedback else ''}

---
""" + """
TASK:
Find NEW accessibility issues in the focused area that are NOT in current report.

Look for:
1. **Alt text**: Generic ("image"), missing, non-descriptive
2. **Link text**: "click here", "read more", URLs as text
3. **Forms**: Missing labels, placeholder-only, unclear error messages
4. **Headings**: Skipped levels (h1→h3), vague headings, too long
5. **Semantic**: <div> soup instead of semantic HTML, missing landmarks

OUTPUT:
Return ONLY JSON array with FULL UPDATED report (existing + new merged).

[
  {
    "wcag_rule": "1.1.1 - Non-text Content (Level A)",
    "description": "Product image has generic alt='image'",
    "html_snippet": "<img src='product.jpg' alt='image'>",
    "severity": "serious",
    "fix": "Change to: alt='Blue cotton t-shirt with V-neck'",
    "confidence": "high",
    "user_impact": "Blind users cannot identify product",
    "element_count": 1
  }
]

Severity: critical (blocks functionality) | serious (major impairment) | moderate (inconvenience) | minor (best practice)

IMPORTANT:
- Do NOT duplicate existing issues
- Be specific: include element counts, exact locations
- Return ONLY the JSON array
"""
    
    return instruction

def get_checker_instruction(tool_context: ToolContext) -> str:
    html = tool_context.state.get(ContextKey.DOM_HTML, '')
    report = tool_context.state.get(ContextKey.LOOP_REPORT, '[]')
    iteration = tool_context.state.get(ContextKey.LOOP_ITERATION, 0)
    
    instruction = f"""You are a COMPLETENESS CHECKER.

HTML to Analyze:
{html}

Report:
{report}

Iteration (1-based): {iteration + 1}"""+"""

SCOPE (target coverage: 85-0%)
Check these 5 areas and mark each as Covered / Not covered:
1) Images: alt text reviewed?
2) Links: link text / accessible name reviewed?
3) Forms: labels + form structure reviewed?
4) Headings: heading order/hierarchy reviewed?
5) Semantics: landmarks / overall HTML structure reviewed?

DECISION
Call exit_loop() only if:
- At least 3 iterations have completed or no more issues are found in current iteration
- Coverage ≥ 85% (at least 4 of 5 areas covered)
- No clear gaps (e.g., zero form review at all)

Otherwise, if a category is clearly missing:
- Return: "Missing: <category>"
"""
    return instruction


def exit_loop(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Signal the loop agent to stop iterating.
    """
    iteration = tool_context.state.get(ContextKey.LOOP_ITERATION, 0)

    # if iteration < 3:
        # return {"status": "continue", "iteration": iteration, "min_iterations": 3}

    tool_context.actions.escalate = True
    tool_context.actions.skip_summarization = True
    return {"status": "complete", "iteration": iteration}


loop_finder_agent = LlmAgent(
    name="LoopFinderAgent",
    model=MODEL,
    instruction=get_finder_instruction,
    output_key=ContextKey.LOOP_REPORT,
)

loop_checker_agent = LlmAgent(
    name="LoopCompletenessAgent",
    model=MODEL,
    instruction=get_checker_instruction,
    tools=[exit_loop],
    output_key=ContextKey.LOOP_NOTES,
)

loop_agent = LoopAgent(
    name="AccessibilityLoopAgent",
    sub_agents=[loop_finder_agent, loop_checker_agent],
    max_iterations=5,
)
