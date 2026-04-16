"""MCP server exposing the ADK root agent for accessibility testing.

Tools exposed:
- open_page(url): initialize browser (if needed) and navigate using root agent.
- run_full_test(url): run full root flow and force immediate delegation to tester agent.
- reset_session(): create a brand new ADK session and close browser session.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.utils.context_utils import Aclosing
from google.genai import types
from mcp.server.fastmcp import FastMCP

from agent import root_agent
from utils.browser_session import BROWSER_SESSION

APP_NAME = "ax_tester_mcp"
USER_ID = "mcp_user"

mcp = FastMCP("ax-tester-root-agent")


@dataclass
class RootAgentBridge:
    """Keeps ADK runner/session alive across MCP tool calls."""

    session_service: InMemorySessionService = field(default_factory=InMemorySessionService)
    runner: Runner | None = None
    session_id: str | None = None

    async def reset(self) -> dict[str, Any]:
        if BROWSER_SESSION.is_initialized():
            await BROWSER_SESSION.close_session()
        await self._open_session()
        return {"status": "reset", "session_id": self.session_id}

    async def run_turn(self, user_message: str) -> dict[str, Any]:
        await self._ensure_session()

        content = types.Content(role="user", parts=[types.Part(text=user_message)])
        events: list[Any] = []

        async with Aclosing(
            self.runner.run_async(
                user_id=USER_ID,
                session_id=self.session_id,
                new_message=content,
            )
        ) as event_stream:
            async for event in event_stream:
                events.append(event)

        messages: list[dict[str, str]] = []
        function_calls: list[dict[str, Any]] = []
        final_response: str = ""

        for event in events:
            if event.content and event.content.parts:
                text = "".join(part.text or "" for part in event.content.parts)
                if text.strip():
                    messages.append({"author": event.author or "unknown", "text": text})
                    if (event.author or "").lower() != "user":
                        final_response = text

            for fc in event.get_function_calls() or []:
                function_calls.append({"name": fc.name, "args": fc.args})

        return {
            "status": "ok",
            "session_id": self.session_id,
            "current_url": BROWSER_SESSION.page.url if BROWSER_SESSION.is_initialized() else "",
            "final_response": final_response,
            "messages": messages,
            "function_calls": function_calls,
        }

    async def _ensure_session(self) -> None:
        if self.runner is None:
            self.runner = Runner(
                app_name=APP_NAME,
                agent=root_agent,
                session_service=self.session_service,
            )

        if self.session_id is None:
            await self._open_session()

    async def _open_session(self) -> None:
        self.session_id = str(uuid.uuid4())
        await self.session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=self.session_id,
            state={},
        )


bridge = RootAgentBridge()


@mcp.tool()
async def open_page(url: str) -> dict[str, Any]:
    """Open a page through root_agent without triggering full analysis."""
    prompt = f"Open page {url}. Initialize the session if needed, then stop without running the analysis."
    return await bridge.run_turn(prompt)


@mcp.tool()
async def run_full_test(url: str) -> dict[str, Any]:
    """Run the full root flow on a given URL and force delegation to tester_agent."""
    prompt = (
        f"Run the full accessibility test on {url} and start immediately without additional confirmations. "
        "Follow your standard workflow and delegate to AccessibilityTesterAgent."
    )
    return await bridge.run_turn(prompt)


# @mcp.tool()
# async def run_test_on_current_page() -> dict[str, Any]:
#     """Run full test on the page currently loaded in shared browser session."""
#     if not BROWSER_SESSION.is_initialized():
#         return {
#             "status": "error",
#             "message": "No page is currently open: run open_page(url) or run_full_test(url) first.",
#         }

#     current_url = BROWSER_SESSION.page.url
#     prompt = (
#         f"Run the full accessibility test on {current_url} and start immediately without additional confirmations. "
#         "Follow your standard workflow and delegate to AccessibilityTesterAgent."
#     )
#     return await bridge.run_turn(prompt)


@mcp.tool()
async def reset_session() -> dict[str, Any]:
    """Reset ADK session and close browser if open."""
    return await bridge.reset()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
