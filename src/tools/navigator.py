"""Runtime page navigator tool.

This tool uses Playwright to navigate a page via keyboard and collect
accessibility information for each focused element. It expands elements
that expose an "expanded" AX property by pressing Space to reveal
additional paths.

WCAG rules targeted: [2.4.3, 2.4.7, 1.3.3, 2.4.4, 2.4.6, 2.1.1, 2.1.2, 3.2.1, 4.1.2]

@test: .venv/bin/python src/tools/navigator.py shop.reply.com
"""

import asyncio
import logging
import re
import threading
from typing import Any

from playwright.async_api import CDPSession, ElementHandle, Page, async_playwright
from playwright.async_api import Error as PlaywrightError

from tools.base import (
    ActiveElementInfo,
    NavigationCommand,
    NavigatorState,
    Tool,
    ToolExecutionError,
    ToolResult,
    ToolStatus,
)
from tools.consumers import BaseConsumer, FocusVisibleConsumer, OnFocusConsumer
from utils.cdp_helper import get_ax_info_cdp, get_backend_dom_node_id
from utils.screenshots import get_element_screenshot, get_page_screenshot

logger = logging.getLogger(__name__)


class RuntimeNavigatorTool(Tool):
    """Navigate a webpage and collect accessibility info while moving focus."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        # self.headless = self.config.get("headless", True)
        self.headless = self.config.get("headless", False)
        self.wait_for = self.config.get("wait_for", "networkidle")
        self.max_steps = self.config.get("max_steps", 200)
        self.tab_delay_ms = self.config.get("tab_delay_ms", 50)
        self.expand_delay_ms = self.config.get("expand_delay_ms", 1000)
        self.initial_wait_ms = self.config.get("initial_wait_ms", 1000)
        self.consumers: list[BaseConsumer] = self.config.get("consumers") or [
            FocusVisibleConsumer(),
            OnFocusConsumer(),
        ]

    def execute(self, url: str, **kwargs) -> ToolResult:
        """Execute runtime navigation on the given URL."""
        logger.info(f"Starting runtime navigation for {url}")
        try:
            url = self.validate_url(url)

            max_steps = kwargs.get("max_steps", self.max_steps)
            tab_delay_ms = kwargs.get("tab_delay_ms", self.tab_delay_ms)
            expand_delay_ms = kwargs.get("expand_delay_ms", self.expand_delay_ms)
            initial_wait_ms = kwargs.get("initial_wait_ms", self.initial_wait_ms)

            result = self._run_async(
                self._run_navigation_async(
                    url=url,
                    max_steps=max_steps,
                    tab_delay_ms=tab_delay_ms,
                    expand_delay_ms=expand_delay_ms,
                    initial_wait_ms=initial_wait_ms,
                )
            )

            return ToolResult(
                tool_name="runtime-navigator",
                status=ToolStatus.SUCCESS,
                data=result,
                metadata={"url": url},
            )

        except ToolExecutionError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in runtime navigator for {url}")
            return ToolResult(
                tool_name="runtime-navigator",
                status=ToolStatus.FAILURE,
                data={},
                error=str(e),
                metadata={"url": url},
            )

    def _run_async(self, coro):
        """Run an async coroutine safely from sync code."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        result_holder = {}
        error_holder = {}

        def _runner():
            try:
                result_holder["value"] = asyncio.run(coro)
            except Exception as e:
                error_holder["error"] = e

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join()

        if "error" in error_holder:
            raise error_holder["error"]
        return result_holder.get("value")

    async def _run_navigation_async(
        self,
        url: str,
        max_steps: int,
        tab_delay_ms: int,
        expand_delay_ms: int,
        initial_wait_ms: int,
    ) -> dict[str, Any]:

        browser = None
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=self.headless)
                page: Page = await browser.new_page()
                cdp: CDPSession = await page.context.new_cdp_session(page)

                try:
                    await page.goto(url, wait_until=self.wait_for, timeout=10000)
                except PlaywrightError as e:
                    if "Timeout" in str(e):
                        raise ToolExecutionError(f"Page load timeout after {10}s for {url}") from e
                    raise ToolExecutionError(f"Navigation error: {e!s}") from e

                await page.wait_for_timeout(initial_wait_ms)

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
                        prv_active_element=None,
                        cur_active_element=None,
                    ),
                    stop_key=start_element.get_focus_key(),
                )

                return {
                    "page_url": url,
                    "consumer_results": self._finalize_consumers(),
                }

        except ToolExecutionError:
            raise
        except Exception as e:
            logger.exception(f"Playwright execution error for {url}")
            raise ToolExecutionError(f"Playwright error: {e!s}") from e
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass

    async def _navigate_recursive_subtree(
        self,
        page: Page,
        cdp: CDPSession,
        max_steps: int,
        tab_delay_ms: int,
        expand_delay_ms: int,
        prev_state: NavigatorState,
        stop_key: str,
    ):
        path = prev_state.path.copy()
        state = NavigatorState(
            path=path,
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
            self._consume_state(state)

            expanded_value = self._get_expanded_value(cur_active_element.element_ax_info or {})

            if expanded_value is not None and not expanded_value and cur_focus_key not in self.seen_expandable:
                self.seen_expandable.add(cur_focus_key)

                # get new stop key
                await self._only_press_key(page, NavigationCommand.TAB, tab_delay_ms, expand_delay_ms)
                nxt_active_element = await self._capture_active_element(page, cdp)
                nxt_stop_key = nxt_active_element.get_focus_key()
                await self._only_press_key(page, NavigationCommand.SHIFT_TAB, tab_delay_ms, expand_delay_ms)

                # expand and navigate inside expandable
                root_focus_key = cur_active_element.get_focus_key()
                await self._press_key(page, NavigationCommand.SPACE, path, tab_delay_ms, expand_delay_ms)
                self._consume_state(
                    NavigatorState(
                        path=path,
                        cur_active_element=await self._capture_active_element(page, cdp),
                        prv_active_element=None,
                    ),
                    root_focus_key=root_focus_key,
                )

                # navigate inside subtree
                await self._navigate_recursive_subtree(
                    page, cdp, max_steps, tab_delay_ms, expand_delay_ms, state, nxt_stop_key
                )

                # return to current state
                await self._press_key(page, NavigationCommand.ESCAPE, path, tab_delay_ms, expand_delay_ms)
                self._consume_state(
                    NavigatorState(
                        path=path,
                        cur_active_element=await self._capture_active_element(page, cdp),
                        prv_active_element=None,
                    ),
                    root_focus_key=root_focus_key,
                )
                path.pop()  # pop last escape added
                path.pop()  # pop last space added

            # try to move on, if it's not a stop
            await self._press_key(page, NavigationCommand.TAB, path, tab_delay_ms, expand_delay_ms)
            cur_active_element = await self._capture_active_element(page, cdp)
            cur_focus_key = cur_active_element.get_focus_key()

            if cur_focus_key == stop_key:
                await self._only_press_key(page, NavigationCommand.SHIFT_TAB, tab_delay_ms, expand_delay_ms)
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
        page: Page,
        key: NavigationCommand,
        path: list[NavigationCommand],
        tab_delay_ms: int,
        expand_delay_ms: int,
    ) -> None:
        try:
            await self._only_press_key(page, key, tab_delay_ms, expand_delay_ms)
            path.append(key)
        except Exception:
            raise

    async def _only_press_key(
        self, page: Page, key: NavigationCommand, tab_delay_ms: int, expand_delay_ms: int
    ) -> None:
        try:
            await page.keyboard.press(key)
            if "Tab" in key:
                await page.wait_for_timeout(tab_delay_ms)
            else:
                await page.wait_for_timeout(expand_delay_ms)
        except Exception:
            raise


if __name__ == "__main__":
    import json
    import sys

    default_url = "https://shop.reply.com"
    # default_url = "https://apple.com"
    test_url = default_url if len(sys.argv) < 2 else sys.argv[1]

    result = RuntimeNavigatorTool().execute(test_url).to_dict()
    print(json.dumps(result, indent=2, ensure_ascii=False))
