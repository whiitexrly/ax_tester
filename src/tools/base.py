"""Base interface for all accessibility testing tools"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


@dataclass
class NavigationCommand(StrEnum):
    """Command usable for navigtion"""

    TAB = "Tab"
    SHIFT_TAB = "Shift+Tab"
    SPACE = "Space"
    ENTER = "Enter"
    ESCAPE = "Escape"


@dataclass
class ActiveElementInfo:
    backend_dom_node_id: int | None
    page_screenshot: str | None
    element_screenshot: str | None
    element_ax_info: dict[str, Any] | None
    element_out_html: str | None
    element_html_tag: str | None


@dataclass
class NavigatorState:
    """Navigation state snapshot around the current focus.

    Stores page/element screenshots and AX info for previous/current/next
    focus targets. Screenshots are typically base64-encoded strings.
    """

    path: list[NavigationCommand]

    # element info
    prv_active_element: ActiveElementInfo | None
    cur_active_element: ActiveElementInfo | None


class ToolStatus(StrEnum):
    """Execution status of a tool"""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class ToolResult:
    """Standardized result format for all tools

    Attributes:
        tool_name: Name of the tool that generated this result
        status: Execution status
        data: Tool-specific result data
        error: Error message if status is FAILURE
        metadata: Additional metadata (e.g., URL, timestamp)

    """

    tool_name: str
    status: ToolStatus
    data: dict[str, Any]
    error: str | None = None
    metadata: dict[str, Any] | None = None

    def is_success(self) -> bool:
        """Check if execution was successful"""
        return self.status == ToolStatus.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "tool_name": self.tool_name,
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata or {},
        }


class Tool(ABC):
    """Abstract base class for all accessibility testing tools

    All tools must implement the execute method and follow
    the standardized ToolResult format.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize tool with optional configuration

        Args:
            config: Tool-specific configuration dictionary

        """
        self.config = config or {}
        self.name = self.__class__.__name__

    @abstractmethod
    def execute(self, url: str, **kwargs) -> ToolResult:
        """Execute the accessibility test

        Args:
            url: Target URL to test
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult with standardized format

        Raises:
            ToolExecutionError: If execution fails

        """
        pass

    def validate_url(self, url: str) -> str:
        """Validate and normalize URL

        Args:
            url: URL to validate

        Returns:
            Normalized URL

        Raises:
            ValueError: If URL is invalid

        """
        from urllib.parse import urlparse

        if not url:
            raise ValueError("URL cannot be empty")

        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL format: {url}")

        return url

    def __str__(self) -> str:
        return f"{self.name}(config={self.config})"


class ToolExecutionError(Exception):
    """Base exception for tool execution failures"""

    pass
