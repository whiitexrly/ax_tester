"""
Base interface for all accessibility testing tools
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional
from enum import StrEnum


class ToolStatus(StrEnum):
    """Execution status of a tool"""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class ToolResult:
    """
    Standardized result format for all tools
    
    Attributes:
        tool_name: Name of the tool that generated this result
        status: Execution status
        data: Tool-specific result data
        error: Error message if status is FAILURE
        metadata: Additional metadata (e.g., URL, timestamp)
    """
    tool_name: str
    status: ToolStatus
    data: Dict[str, Any]
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def is_success(self) -> bool:
        """Check if execution was successful"""
        return self.status == ToolStatus.SUCCESS
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "tool_name": self.tool_name,
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata or {}
        }


class Tool(ABC):
    """
    Abstract base class for all accessibility testing tools
    
    All tools must implement the execute method and follow
    the standardized ToolResult format.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize tool with optional configuration
        
        Args:
            config: Tool-specific configuration dictionary
        """
        self.config = config or {}
        self.name = self.__class__.__name__
    
    @abstractmethod
    def execute(self, url: str, **kwargs) -> ToolResult:
        """
        Execute the accessibility test
        
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
        """
        Validate and normalize URL
        
        Args:
            url: URL to validate
        
        Returns:
            Normalized URL
        
        Raises:
            ValueError: If URL is invalid
        """
        from urllib.parse import urlparse
        
        if not url: raise ValueError("URL cannot be empty")
        
        if not url.startswith(('http://', 'https://')): url = f'https://{url}'
        
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL format: {url}")
        
        return url
    
    def __str__(self) -> str:
        return f"{self.name}(config={self.config})"


class ToolExecutionError(Exception):
    """Base exception for tool execution failures"""
    pass