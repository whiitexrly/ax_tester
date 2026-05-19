import asyncio
import json
import logging
import os
from contextlib import AsyncExitStack
from typing import Any

import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

logger = logging.getLogger(__name__)

BROWSER_EXECUTOR_URL_ENV = "BROWSER_EXECUTOR_URL"


class BrowserExecutorError(RuntimeError):
    """Raised when the browser executor MCP call fails."""


def get_browser_executor_url() -> str:
    """Read the browser executor MCP URL from env or the repo .env file."""
    value = os.getenv(BROWSER_EXECUTOR_URL_ENV)
    if value:
        return value.strip()

    raise BrowserExecutorError(f"Missing {BROWSER_EXECUTOR_URL_ENV}. Set it in the .env file.")


class BrowserExecutorClient:
    """Persistent MCP client for the external browser executor server."""

    def __init__(
        self,
        timeout_seconds: float = 30.0,
        sse_read_timeout_seconds: float = 300.0,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._sse_read_timeout_seconds = sse_read_timeout_seconds
        self._lock = asyncio.Lock()
        self._exit_stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self.session_id: str | None = None
        self.transport_session_id: str | None = None

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        include_session_id: bool = True,
    ) -> Any:
        """Call an executor MCP tool and return its serializable payload."""
        async with self._lock:
            await self._ensure_connected()
            assert self._session is not None

            tool_args = dict(arguments or {})
            if include_session_id and self.session_id and "session_id" not in tool_args:
                tool_args["session_id"] = self.session_id

            if name == "create_session_web":
                capability_result = await self._session.call_tool("executor.get_capabilities")
                if capability_result.isError:
                    raise BrowserExecutorError(
                        f"Executor tool {name!r} failed: {self._result_to_text(capability_result)}"
                    )

                capability_payload = self._parse_result(capability_result)
                tool_args["capability_id"] = capability_payload["capabilities"][-1]["id"]
                tool_args["capability_name"] = capability_payload["capabilities"][-1]["name"]
                # tool_args["capability_id"] = "browser-chrome"
                # tool_args["capability_name"] = "chrome di Pasquale"

            result = await self._session.call_tool(f"executor.{name}", tool_args)
            if result.isError:
                raise BrowserExecutorError(f"Executor tool {name!r} failed: {self._result_to_text(result)}")

            payload = self._parse_result(result)
            if name == "create_session_web":
                self.session_id = payload.get("id")
            elif name == "close_session":
                self.session_id = None
            return payload

    async def close(self) -> None:
        """Close the MCP transport."""
        async with self._lock:
            await self._close_unlocked()
            self.session_id = None

    async def _ensure_connected(self) -> None:
        if self._session is not None:
            return

        url = get_browser_executor_url()
        self._exit_stack = AsyncExitStack()
        try:
            http_client = create_mcp_http_client(
                timeout=httpx.Timeout(self._timeout_seconds, read=self._sse_read_timeout_seconds)
            )
            await self._exit_stack.enter_async_context(http_client)
            read_stream, write_stream, get_session_id = await self._exit_stack.enter_async_context(
                streamable_http_client(url, http_client=http_client)
            )
            session = ClientSession(read_stream, write_stream)
            self._session = await self._exit_stack.enter_async_context(session)
            await self._session.initialize()
            try:
                self.transport_session_id = get_session_id()
            except Exception:
                self.transport_session_id = None
        except Exception:
            await self._close_unlocked()
            raise

    async def _close_unlocked(self) -> None:
        if self._exit_stack is not None:
            try:
                await self._exit_stack.aclose()
            except Exception:
                logger.debug("Error while closing browser executor MCP client", exc_info=True)
        self._exit_stack = None
        self._session = None
        self.transport_session_id = None

    def _parse_result(self, result: Any) -> Any:
        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            return self._unwrap_payload(structured)

        text = self._result_to_text(result).strip()
        if not text:
            return {}
        try:
            return self._unwrap_payload(json.loads(text))
        except json.JSONDecodeError:
            return text

    def _unwrap_payload(self, payload: Any) -> Any:
        if isinstance(payload, dict) and set(payload) == {"result"}:
            return payload["result"]
        return payload

    def _result_to_text(self, result: Any) -> str:
        chunks: list[str] = []
        for item in getattr(result, "content", []) or []:
            text = getattr(item, "text", None)
            if text is not None:
                chunks.append(text)
            elif isinstance(item, dict) and item.get("text") is not None:
                chunks.append(str(item["text"]))
        return "\n".join(chunks)
