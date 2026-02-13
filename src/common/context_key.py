from enum import StrEnum

class ContextKey(StrEnum):
    DOM_HTML = "dom_html"
    LOOP_REPORT = "loop_report"
    LOOP_NOTES = "loop_notes"
    LOOP_ITERATION = "loop_iteration"
    AXE_REPORT = "axe_report"
    MERGED_REPORT = "merged_report"
    FINAL_REPORT = "final_report"
    WCAG_PROMPT = "wcag_prompt"
