from typing import Any

from common import ContextKey
from schemas import Issue
from tools.base import ActiveElementInfo, NavigationCommand, NavigatorState
from tools.consumers.base import BaseConsumer


class OnFocusConsumer(BaseConsumer):
    """Detect WCAG 3.2.1 violations caused by focus transitions."""

    name = "on-focus-consumer"
    report_key = ContextKey.ON_FOCUS_REPORT

    def __init__(self):
        self._issues: list[dict[str, Any]] = []
        self._steps = 0

    def consume(self, state: NavigatorState, **kwargs) -> None:
        self._steps += 1
        current: ActiveElementInfo | None = state.cur_active_element
        previous: ActiveElementInfo | None = state.prv_active_element

        if not current or not state.path:
            return

        issue: dict[str, Any] | None = None
        if len(state.path) != 0:
            transition_key = state.path[-1]
        else:
            transition_key = None

        if transition_key.value in (NavigationCommand.TAB, NavigationCommand.SHIFT_TAB):
            issue = self._build_issue_tab(previous, current)
        elif transition_key.value in (NavigationCommand.ESCAPE, NavigationCommand.SPACE):
            root_focus_key: str | None = kwargs.get("root_focus_key")
            if root_focus_key is None:
                return
            issue = self._build_issue_space_escape(transition_key, current, root_focus_key)

        if issue is not None:
            self._issues.append(issue)

    def finalize(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "issue_list": self._issues,
            "checked": self._steps,
        }

    def _build_issue_tab(
        self, previous: ActiveElementInfo | None, current: ActiveElementInfo
    ) -> dict[str, Any] | None:
        if previous is None:
            return None

        prev_url = (previous.page_url or "").strip()
        cur_url = (current.page_url or "").strip()
        prev_title = (previous.page_title or "").strip()
        cur_title = (current.page_title or "").strip()
        prev_pages = previous.context_page_count
        cur_pages = current.context_page_count

        # opening a new tab/window on focus
        if prev_pages is not None and cur_pages is not None and cur_pages > prev_pages:
            return Issue(
                id=f"on-focus-new-window-{current.backend_dom_node_id or 'unknown'}-{self._steps}",
                wcag_rule="3.2.1 - On Focus (Level A)",
                description="Focusing this element opens a new window/tab without explicit user activation.",
                severity="critical",
                source="llm/on_focus_analyzer",
                confidence="high",
                html_snippet=current.element_out_html or "",
                fix="Remove side effects from focus handlers and require explicit activation (Enter/Space/click).",
            ).model_dump()

        # url change from focus alone is unexpected context change
        if prev_url and cur_url and prev_url != cur_url:
            return Issue(
                id=f"on-focus-url-change-{current.backend_dom_node_id or 'unknown'}-{self._steps}",
                wcag_rule="3.2.1 - On Focus (Level A)",
                description="Focusing this element changes the page URL/context unexpectedly.",
                severity="serious",
                source="llm/on_focus_analyzer",
                confidence="high",
                html_snippet=current.element_out_html or "",
                fix="Do not trigger navigation on focus; trigger changes only after explicit user action.",
            ).model_dump()

        # title jump may indicate large in-page context switch
        if prev_url == cur_url and prev_title and cur_title and prev_title != cur_title:
            return Issue(
                id=f"on-focus-title-change-{current.backend_dom_node_id or 'unknown'}-{self._steps}",
                wcag_rule="3.2.1 - On Focus (Level A)",
                description="Focusing this element causes a significant context/title change.",
                severity="moderate",
                source="llm/on_focus_analyzer",
                confidence="medium",
                html_snippet=current.element_out_html or "",
                fix="Avoid context changes on focus; update content only after explicit confirmation.",
            ).model_dump()

        return None

    def _build_issue_space_escape(
        self,
        transition_key: NavigationCommand,
        current: ActiveElementInfo,
        root_focus_key: str,
    ) -> dict[str, Any] | None:

        if current.get_focus_key() == root_focus_key:
            return None

        if transition_key == NavigationCommand.SPACE:
            return Issue(
                id=f"on-focus-space-move-{current.backend_dom_node_id or 'unknown'}-{self._steps}",
                wcag_rule="3.2.1 - On Focus (Level A)",
                description="Pressing Space on an expandable moved focus away from the triggering element.",
                severity="serious",
                source="llm/on_focus_analyzer",
                confidence="high",
                html_snippet=current.element_out_html or "",
                fix="Keep focus on the control that expanded content; do not move focus automatically on Space.",
            ).model_dump()

        if transition_key == NavigationCommand.ESCAPE:
            return Issue(
                id=f"on-focus-escape-not-return-root-{current.backend_dom_node_id or 'unknown'}-{self._steps}",
                wcag_rule="3.2.1 - On Focus (Level A)",
                description="Pressing Escape did not return focus to the root element that opened the expandable content.",
                severity="serious",
                source="llm/on_focus_analyzer",
                confidence="high",
                html_snippet=current.element_out_html or "",
                fix="On Escape, restore focus to the control that opened the expandable region/dialog.",
            ).model_dump()

        return None
