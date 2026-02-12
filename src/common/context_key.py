from enum import StrEnum

class ContextKey(StrEnum):
    DOM_HTML = "dom_html"
    LOOP_REPORT = "loop_report"
    LOOP_NOTES = "loop_notes"
    AXE_REPORT = "axe_report"
    MERGED_REPORT = "merged_report"
    WCAG_LEVEL = "wcag_level_set"
