"""Axe-Core accessibility testing tool integration

This tool uses Playwright to load a webpage and inject axe-core
to perform automated accessibility testing.

@test: .venv/bin/python src/tools/axe_core_tool.py shop.reply.com
"""

import asyncio
import json
import logging
import threading
from pathlib import Path
from typing import Any

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from schemas import Issue
from tools.base import Tool, ToolExecutionError, ToolResult, ToolStatus

logger = logging.getLogger(__name__)


class AxeCoreTool(Tool):
    """Axe-Core static accessibility analyzer

    Executes axe-core rules on a webpage and returns WCAG violations.

    Configuration:
        timeout: Page load timeout in seconds (default: 30)
        headless: Run browser in headless mode (default: True)
        wait_for: Wait condition before running axe (default: 'networkidle')
        rules: Specific axe rules to run (default: all)
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.timeout = self.config.get("timeout", 30)
        self.headless = self.config.get("headless", True)
        self.wait_for = self.config.get("wait_for", "networkidle")
        self.rules = self.config.get("rules", None)  # None = all rules
        self.axe_source = self._load_axe_source()

    def _load_axe_source(self) -> str:
        """Load axe-core JavaScript source from node_modules

        Returns:
            Axe-core source code as string

        Raises:
            ToolExecutionError: If axe-core source not found

        """
        try:
            # get path to axe-core
            js_dir = Path(__file__).parent.parent.parent
            axe_path = js_dir / "node_modules" / "axe-core" / "axe.min.js"

            if not axe_path.exists():
                raise FileNotFoundError(f"Axe-core not found at {axe_path}. Run: npm i")

            with open(axe_path, encoding="utf-8") as f:
                return f.read()

        except Exception as e:
            logger.error(f"Failed to load axe-core source: {e}")
            raise ToolExecutionError(f"Cannot load axe-core: {e!s}") from e

    def execute(self, url: str, **kwargs) -> ToolResult:
        """Execute axe-core analysis on the given URL

        Args:
            url: Target URL to test
            **kwargs: Additional options (timeout, rules, etc.)

        Returns:
            ToolResult with axe-core violations and passes

        """
        try:
            url = self.validate_url(url)
            logger.info(f"Starting axe-core analysis for {url}")

            # config
            timeout = kwargs.get("timeout", self.timeout)
            rules = kwargs.get("rules", self.rules)

            # run axe-core
            axe_results = self._run_async(self._run_axe_with_playwright_async(url, timeout, rules))
            violations = axe_results.get("violations", [])
            incomplete = axe_results.get("incomplete", [])
            inapplicable = axe_results.get("inapplicable", [])

            issue_list = self._map_violations_to_issues(violations)

            logger.info(
                f"Axe-core analysis complete: {len(violations)} violations, "
                f"{len(incomplete)} incomplete, {len(issue_list)} mapped issues"
            )

            return ToolResult(
                tool_name="axe-core",
                status=ToolStatus.SUCCESS,
                data={
                    "violations": violations,
                    "incomplete": incomplete,
                    "inapplicable": inapplicable,
                    "issue_list": issue_list,
                    "url": url,
                    "timestamp": axe_results.get("timestamp"),
                },
            )

        except ToolExecutionError:
            raise

        except Exception as e:
            logger.exception(f"Unexpected error in axe-core execution for {url}")

            return ToolResult(
                tool_name="axe-core", status=ToolStatus.FAILURE, data={}, error=str(e), metadata={"url": url}
            )

    def _run_async(self, coro):
        """Run an async coroutine safely from sync code, even if an event loop exists."""
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

    async def _run_axe_with_playwright_async(
        self, url: str, timeout: int, rules: list[str] | None = None
    ) -> dict[str, Any]:
        """Execute axe-core using Playwright

        Args:
            url: Target URL
            timeout: Page load timeout in seconds
            rules: Specific rules to run (None = all)

        Returns:
            Axe-core results dictionary

        Raises:
            ToolExecutionError: If execution fails

        """
        browser = None

        try:
            async with async_playwright() as playwright:
                # launch browser
                browser = await playwright.chromium.launch(headless=self.headless)
                page = await browser.new_page()

                # navigate to page
                try:
                    await page.goto(url, wait_until=self.wait_for, timeout=timeout * 1000)
                except PlaywrightError as e:
                    if "Timeout" in str(e):
                        raise ToolExecutionError(f"Page load timeout after {timeout}s for {url}") from e
                    else:
                        raise ToolExecutionError(f"Navigation error: {e!s}") from e

                # run axe-core
                await page.add_script_tag(content=self.axe_source)
                axe_options = {"runOnly": {"type": "rule", "values": rules}} if rules else {}
                logger.debug(f"Running axe-core with options: {axe_options}")

                if axe_options:
                    axe_results = await page.evaluate(f"axe.run({json.dumps(axe_options)})")
                else:
                    axe_results = await page.evaluate("axe.run()")

                await browser.close()

                axe_results.pop("passes", None)
                return axe_results

        except ToolExecutionError:
            raise

        except Exception as e:
            logger.exception(f"Playwright execution error for {url}")
            raise ToolExecutionError(f"Playwright error: {e!s}") from e

        finally:  # close browser
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass

    def _map_violations_to_issues(self, violations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        for v in violations:
            wcag = v.get("id") or ""
            description = v.get("description") or v.get("help") or ""
            impact = v.get("impact") or "moderate"
            for idx, node in enumerate(v.get("nodes", [])):
                snippet = node.get("html") or ""
                target = node.get("target") or []
                node_id = "-".join([str(t) for t in target]) if target else str(idx)
                issue = Issue(
                    id=f"axe-{wcag}-{node_id}",
                    wcag_rule=wcag,
                    description=description,
                    severity=self._map_impact(impact),
                    source="axe",
                    confidence="high",
                    html_snippet=snippet.replace("\\n", " "),
                    fix=v.get("help") or v.get("helpUrl") or "",
                ).model_dump()
                issues.append(issue)
        return issues

    def _map_impact(self, impact: str) -> str:
        impact = (impact or "moderate").lower()
        if impact in {"critical", "serious", "moderate", "minor"}:
            return impact
        return "moderate"


# simple test runner
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    test_url = "shop.reply.com" if len(sys.argv) < 2 else sys.argv[1]

    print(f"Testing URL: {test_url}")

    result = AxeCoreTool().execute(test_url).to_dict()
    print(json.dumps(result, indent=2))
