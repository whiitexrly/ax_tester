from enum import StrEnum


class ContextKey(StrEnum):
    # utils
    DOM_HTML = "dom_html"
    WCAG_PROMPT = "wcag_prompt"

    # temp storage
    LOOP_REPORT = "loop_report"
    LOOP_NOTES = "loop_notes"
    LOOP_ITERATION = "loop_iteration"
    AXE_REPORT = "axe_report"
    MERGED_REPORT = "merged_report"

    # final outcomes:
    STATIC_REPORT = "static_report"
    IMAGE_ANALYZER_REPORT = "image_analyzer_report"
