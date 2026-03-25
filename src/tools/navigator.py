"""Runtime page navigator tool.

This tool uses Playwright to navigate a page via keyboard and collect
accessibility information for each focused element. It expands elements
that expose an "expanded" AX property by pressing Space to reveal
additional paths.

WCAG rules targeted: [2.4.3, 2.4.7, 1.3.3, 2.4.4, 2.4.6, 2.1.1, 2.1.2, 3.2.1, 4.1.2]

@test: .venv/bin/python src/tools/navigator.py shop.reply.com
"""

import logging
import re
from typing import Any

from playwright.async_api import CDPSession, ElementHandle, Page

from tools.base import (
    ActiveElementInfo,
    NavigatorState,
    Tool,
    ToolExecutionError,
    ToolResult,
    ToolStatus,
)
from tools.consumers import BaseConsumer, build_default_navigator_consumers
from utils.browser_session import BROWSER_SESSION, NavigationCommand
from utils.cdp_helper import get_ax_info_cdp, get_backend_dom_node_id
from utils.screenshots import get_element_screenshot, get_page_screenshot

logger = logging.getLogger(__name__)


class RuntimeNavigatorTool(Tool):
    """Navigate a webpage and collect accessibility info while moving focus."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.max_steps = self.config.get("max_steps", 200)
        self.tab_delay_ms = self.config.get("tab_delay_ms", 50)
        self.expand_delay_ms = self.config.get("expand_delay_ms", 1000)
        self.initial_wait_ms = self.config.get("initial_wait_ms", 5000)
        self.consumers: list[BaseConsumer] = self.config.get("consumers") or build_default_navigator_consumers()

    async def execute(self, **kwargs) -> ToolResult:
        """Execute runtime navigation on the current page in `BROWSER_SESSION`."""
        page_url = BROWSER_SESSION.page.url if BROWSER_SESSION.is_initialized() else ""
        logger.info(f"Starting runtime navigation on current page {page_url}")

        try:
            max_steps = kwargs.get("max_steps", self.max_steps)
            tab_delay_ms = kwargs.get("tab_delay_ms", self.tab_delay_ms)
            expand_delay_ms = kwargs.get("expand_delay_ms", self.expand_delay_ms)
            initial_wait_ms = kwargs.get("initial_wait_ms", self.initial_wait_ms)

            result = await self._run_navigation_async(
                max_steps=max_steps,
                tab_delay_ms=tab_delay_ms,
                expand_delay_ms=expand_delay_ms,
                initial_wait_ms=initial_wait_ms,
            )

            return ToolResult(
                tool_name="runtime-navigator",
                status=ToolStatus.SUCCESS,
                data=result,
                metadata={"url": result.get("page_url", page_url)},
            )

        except ToolExecutionError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in runtime navigator for {page_url}")
            return ToolResult(
                tool_name="runtime-navigator",
                status=ToolStatus.FAILURE,
                data={},
                error=str(e),
                metadata={"url": page_url},
            )

    async def _run_navigation_async(
        self,
        max_steps: int,
        tab_delay_ms: int,
        expand_delay_ms: int,
        initial_wait_ms: int,
    ) -> dict[str, Any]:
        try:
            if not BROWSER_SESSION.is_initialized():
                raise ToolExecutionError(
                    "Browser session not initialized. Initialize and navigate with root tools before runtime navigation."
                )

            await BROWSER_SESSION.page.wait_for_timeout(initial_wait_ms)

            page: Page = BROWSER_SESSION.page
            cdp: CDPSession = await page.context.new_cdp_session(page)

            # build default states before recursive function
            self.seen_expandable = set()
            start_element = await self._capture_active_element(page, cdp)
            if not start_element:
                raise ToolExecutionError("No active element detected after initial load.")

            await self._navigate_recursive_subtree(
                page=page,
                cdp=cdp,
                max_steps=max_steps,
                tab_delay_ms=tab_delay_ms,
                expand_delay_ms=expand_delay_ms,
                prev_state=NavigatorState(
                    path=[],
                    root_element=None,
                    prv_active_element=None,
                    cur_active_element=None,
                ),
                stop_key=start_element.get_focus_key(),
            )

            return {
                "page_url": page.url,
                "consumer_results": self._finalize_consumers(),
            }

        except ToolExecutionError:
            raise
        except Exception as e:
            current_url = BROWSER_SESSION.page.url if BROWSER_SESSION.is_initialized() else "<unknown>"
            logger.exception(f"Playwright execution error for {current_url}")
            raise ToolExecutionError(f"Playwright error: {e!s}") from e

    async def _navigate_recursive_subtree(
        self,
        page: Page,
        cdp: CDPSession,
        max_steps: int,
        tab_delay_ms: int,
        expand_delay_ms: int,
        prev_state: NavigatorState,
        stop_key: str,
        **kwargs,
    ):
        path = prev_state.path.copy()
        state = NavigatorState(
            path=path,
            root_element=prev_state.cur_active_element,
            prv_active_element=prev_state.prv_active_element,
            cur_active_element=prev_state.cur_active_element,
        )

        cur_active_element = await self._capture_active_element(page, cdp)

        cur_focus_key = cur_active_element.get_focus_key()
        for _step in range(1, max_steps + 1):
            # get info of current active element
            state.path = path
            state.prv_active_element = state.cur_active_element
            state.cur_active_element = cur_active_element

            # consume current state
            self._consume_state(state, **kwargs)

            expanded_value = self._get_expanded_value(cur_active_element.element_ax_info or {})

            if expanded_value is not None and not expanded_value and cur_focus_key not in self.seen_expandable:
                self.seen_expandable.add(cur_focus_key)

                # get new stop key
                await BROWSER_SESSION.press_key(NavigationCommand.TAB, tab_delay_ms, expand_delay_ms)
                nxt_active_element = await self._capture_active_element(page, cdp)
                nxt_stop_key = nxt_active_element.get_focus_key()
                await BROWSER_SESSION.press_key(NavigationCommand.SHIFT_TAB, tab_delay_ms, expand_delay_ms)

                # expand and navigate inside expandable
                new_root_focus_key = cur_active_element.get_focus_key()
                await self._press_key(NavigationCommand.SPACE, path, tab_delay_ms, expand_delay_ms)
                await self._navigate_recursive_subtree(
                    page=page,
                    cdp=cdp,
                    max_steps=max_steps,
                    tab_delay_ms=tab_delay_ms,
                    expand_delay_ms=expand_delay_ms,
                    prev_state=state,
                    stop_key=nxt_stop_key,
                    root_focus_key=new_root_focus_key,
                )

                path.pop()  # pop last space added

            # try to move on, if it's not a stop
            await self._press_key(NavigationCommand.TAB, path, tab_delay_ms, expand_delay_ms)
            cur_active_element = await self._capture_active_element(page, cdp)
            cur_focus_key = cur_active_element.get_focus_key()

            # return to previous element, escape and consume state
            if cur_focus_key == stop_key:
                await self._press_key(NavigationCommand.SHIFT_TAB, path, tab_delay_ms, expand_delay_ms)
                await self._press_key(NavigationCommand.ESCAPE, path, tab_delay_ms, expand_delay_ms)
                self._consume_state(
                    NavigatorState(
                        path=path,
                        root_element=state.root_element,
                        prv_active_element=state.cur_active_element,
                        cur_active_element=await self._capture_active_element(page, cdp),
                    ),
                    root_focus_key=kwargs.get("root_focus_key"),
                )
                return

    async def _capture_active_element(self, page: Page, cdp: CDPSession) -> ActiveElementInfo | None:
        handle = await page.evaluate_handle("() => document.activeElement")
        element: ElementHandle = handle.as_element()
        if not element:
            await handle.dispose()
            return None

        try:
            outer_html = await element.evaluate("el => el.outerHTML")
            outer_html = re.sub(r"\s+", " ", outer_html).strip()[:400]
            tag = await element.evaluate("el => el.tagName")
            href = await element.evaluate("el => el.getAttribute('href')")

            backend_dom_node_id = await get_backend_dom_node_id(cdp, element)
            ax_info = await get_ax_info_cdp(cdp, element)
            element_screenshot = await get_element_screenshot(page, element)
            page_screenshot = await get_page_screenshot(page)

            return ActiveElementInfo(
                backend_dom_node_id=backend_dom_node_id,
                page_screenshot=page_screenshot,
                element_screenshot=element_screenshot,
                element_ax_info=ax_info,
                element_out_html=outer_html,
                element_html_tag=tag,
                element_href=href,
                page_url=page.url,
                page_title=await page.title(),
                context_page_count=len(page.context.pages),
            )
        finally:
            await element.dispose()

    def _consume_state(self, state: NavigatorState, **kwargs) -> None:
        """Dispatch state to registered consumers."""
        for consumer in self.consumers:
            try:
                consumer.consume(state, **kwargs)
            except Exception:
                logger.exception(f"Consumer {consumer.name} failed to consume state")

    def _finalize_consumers(self) -> list[dict[str, Any]]:
        """Collect results from registered consumers."""
        results: list[dict[str, Any]] = []
        for consumer in self.consumers:
            try:
                results.append({"report_key": consumer.report_key, "result": consumer.finalize()})
            except Exception:
                logger.exception(f"Consumer {consumer.name} finalize error")
        return results

    def _get_expanded_value(self, ax_info: dict[str, Any]) -> bool | None:
        props = ax_info.get("properties") or {}
        if "expanded" not in props:
            return None
        value = props.get("expanded")
        if isinstance(value, bool):
            return value
        return None

    async def _press_key(
        self,
        key: NavigationCommand,
        path: list[NavigationCommand],
        tab_delay_ms: int,
        expand_delay_ms: int,
    ) -> None:
        await BROWSER_SESSION.press_key(key, tab_delay_ms, expand_delay_ms)
        path.append(key)


if __name__ == "__main__":
    import asyncio
    import json
    import sys

    default_url = "https://shop.reply.com"
    # default_url = "https://apple.com"
    test_url = default_url if len(sys.argv) < 2 else sys.argv[1]

    async def _run() -> None:
        url = test_url if test_url.startswith(("http://", "https://")) else f"https://{test_url}"
        await BROWSER_SESSION.create_session()
        await BROWSER_SESSION.goto(url)
        try:
            result = (await RuntimeNavigatorTool().execute()).to_dict()
            print(json.dumps(result, indent=2, ensure_ascii=False))
        finally:
            await BROWSER_SESSION.close_session()

    asyncio.run(_run())
