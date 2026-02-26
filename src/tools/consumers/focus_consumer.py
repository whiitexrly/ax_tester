import json
import logging
import re
from typing import Any

from common import MODEL_NAME, ContextKey
from schemas import Issue
from tools.base import NavigatorState
from tools.consumers.base import BaseConsumer
from utils.llm_helper import call_llm

logger = logging.getLogger(__name__)

FOCUS_VISIBILITY_PROMPT = """
    You check keyboard focus visibility for images.
    Each screenshot is centered on the focused element or may be not, if the element is on the border of the web page.
    Decide for each item:
    - is_image: true if the focused element is an image or graphic content (photo, illustration, icon).
    - has_focus_indicator: true if a clear focus outline/border/box/glow surrounds the focused element.
    Return JSON ONLY as an array of objects with keys: index, is_image, has_focus_indicator.
    If not an image, set is_image false and has_focus_indicator false.
    If unsure, set has_focus_indicator false.
    The index must match the number shown in the input label "Item {index}".
    Do not add extra keys or commentary. Use valid JSON with double quotes.

    Example output:
    [
        {"index": 0, "is_image": true, "has_focus_indicator": true},
        {"index": 1, "is_image": false, "has_focus_indicator": false}
    ]
"""


class FocusConsumer(BaseConsumer):
    """Analyze focus visibility using navigator states."""

    name = "focus-consumer"
    report_key = ContextKey.FOCUS_NAVIGATION_REPORT

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.0,
        max_items_per_batch: int = 10,
        max_prompt_chars: int = 100_000,
    ):
        self.model = model or MODEL_NAME
        self.temperature = temperature
        self.max_items_per_batch = max_items_per_batch
        self.max_prompt_chars = max_prompt_chars
        self._items: list[dict[str, Any]] = []
        self._steps = 0
        self._seen_ids: set[int] = set()

    def consume(self, state: NavigatorState) -> None:
        """Collect screenshot data from the current state."""
        self._steps += 1
        current = state.cur_active_element
        if not current:
            return

        backend_id = current.backend_dom_node_id
        if backend_id is not None:
            if backend_id in self._seen_ids:
                return
            self._seen_ids.add(backend_id)

        self._items.append(
            {
                "index": self._steps - 1,
                "backend_dom_node_id": backend_id,
                "mime": "image/png",
                "b64": current.element_screenshot,
                "html_snippet": current.element_out_html or "",
            }
        )

    def finalize(self) -> dict[str, Any]:
        """Run LLM analysis and build issues."""
        if not self._items:
            return {
                "name": self.name,
                "issue_list": [],
                "steps": self._steps,
                "checked": 0,
            }

        batches = self._batch_items(self._items, self.max_items_per_batch, self.max_prompt_chars)
        results: list[dict[str, Any]] = []
        for batch in batches:
            results.extend(self._analyze_batch(batch))

        issues = self._build_issues(self._items, results)
        return {
            "name": self.name,
            "issue_list": issues,
            "steps": self._steps,
            "checked": len(self._items),
        }

    def _batch_items(
        self, items: list[dict[str, Any]], max_items_per_batch: int, max_prompt_chars: int
    ) -> list[list[dict[str, Any]]]:
        if max_items_per_batch <= 0:
            max_items_per_batch = len(items) or 1

        batches: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        base_prompt_len = len(FOCUS_VISIBILITY_PROMPT)
        current_len = base_prompt_len

        for item in items:
            item_len = self._estimate_item_prompt_len(item)
            if current and (len(current) == max_items_per_batch or current_len + item_len > max_prompt_chars):
                batches.append(current)
                current = []
                current_len = base_prompt_len

            current.append(item)
            current_len += item_len

        if current:
            batches.append(current)

        return batches

    def _estimate_item_prompt_len(self, item: dict[str, Any]) -> int:
        return len(item.get("b64", "")) + 200

    def _analyze_batch(self, batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
        messages = self._build_messages(batch)
        response_text = call_llm(self.model, self.temperature, messages)
        return self._parse_response(response_text)

    def _build_messages(self, batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [{"type": "text", "text": FOCUS_VISIBILITY_PROMPT.strip()}]
        for item in batch:
            label = f"Item {item['index']}"
            content.append({"type": "text", "text": label})
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{item['mime']};base64,{item['b64']}"},
                }
            )
        return [{"role": "user", "content": content}]

    def _parse_response(self, text: str) -> list[dict[str, Any]]:
        try:
            parsed = json.loads(text)
        except Exception:
            match = re.search(r"(\[.*\])", text, re.DOTALL)
            if not match:
                return []
            try:
                parsed = json.loads(match.group(1))
            except Exception:
                return []

        if isinstance(parsed, list):
            normalized: list[dict[str, Any]] = []
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                if "index" not in item or "is_image" not in item or "has_focus_indicator" not in item:
                    continue
                normalized.append(
                    {
                        "index": item.get("index"),
                        "is_image": bool(item.get("is_image")),
                        "has_focus_indicator": bool(item.get("has_focus_indicator")),
                    }
                )
            if normalized:
                return normalized
        return []

    def _build_issues(self, items: list[dict[str, Any]], results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_index = {r.get("index"): r for r in results if isinstance(r, dict)}
        issues: list[dict[str, Any]] = []
        for item in items:
            res = by_index.get(item.get("index"))
            if not res:
                continue
            if res.get("is_image") and not res.get("has_focus_indicator"):
                index = item.get("index")
                issue = Issue(
                    id=f"focus-visible-image-{index}",
                    wcag_rule="2.4.7 - Focus Visible (Level AA)",
                    description="Focused image lacks a visible focus indicator",
                    html_snippet=item.get("html_snippet", ""),
                    severity="serious",
                    confidence="high",
                    source="llm/focus_analyzer",
                    fix="Ensure focused images display a clear focus outline or border.",
                ).model_dump()
                issues.append(issue)
        return issues
