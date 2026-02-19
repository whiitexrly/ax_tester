import urllib.request
from pathlib import Path
from typing import Any

import yaml
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.tool_context import ToolContext

from common import MODEL, ContextKey
from utils.html_sanitizer import sanitize_html_for_llm


def set_wcag_level(tool_context: ToolContext, level: str = "AA") -> dict[str, Any]:
    """Set the active WCAG level set for the loop audit.

    Accepts: A (Level A only), AA (A + AA), AAA (A + AA + AAA).
    """
    normalized = level.strip().upper()
    if normalized not in ["A", "AA", "AAA"]:
        raise ValueError("wcag level must be one of: A, AA, AAA")

    ROOT_DIR = Path(__file__).resolve().parents[2]
    with open(ROOT_DIR / "prompts" / "wcag.yml", encoding="utf-8") as f:
        wcag_data = yaml.safe_load(f)
    levels = wcag_data.get("levels") or {}
    for level in range(len(normalized) + 1, 4):
        levels.pop("A" * level, None)
    wcag_data["levels"] = levels

    tool_context.state[ContextKey.WCAG_PROMPT] = yaml.safe_dump(wcag_data)

    return {"status": "set", "wcag_level": level}


def fetch_dom_html(url: str, tool_context: ToolContext, timeout: int = 30) -> dict[str, Any]:
    """Fetch the HTML DOM for a URL and store it in agent state.

    Returns a small status payload with the number of bytes loaded.
    """
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "adk-accessibility-agent/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    raw_html = raw.decode("utf-8", errors="replace")

    clean_html, _ = sanitize_html_for_llm(raw_html)

    tool_context.state[ContextKey.DOM_HTML] = clean_html
    return {"status": "fetched", "state_name": ContextKey.DOM_HTML, "url": url}


init_agent = LlmAgent(
    name="InitAgent",
    model=MODEL,
    instruction="Call set_wcag_level and fetch_dom_html to prepare data.",
    tools=[set_wcag_level, fetch_dom_html],
)
