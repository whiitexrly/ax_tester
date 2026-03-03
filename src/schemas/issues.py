from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SeverityKey = Literal["critical", "serious", "moderate", "minor"]
SourceType = Literal[
    "axe",
    "llm",
    "both",
    "llm/image-analyzer",
    "llm/focus_visible_analyzer",
    "llm/on_focus_analyzer",
]
ConfidenceLevel = Literal["high", "medium", "low"]


class Issue(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"additionalProperties": False})

    id: str = Field(...)
    wcag_rule: str = Field(...)
    description: str = Field(...)
    severity: SeverityKey = Field(...)
    source: SourceType = Field(...)
    confidence: ConfidenceLevel = Field(...)
    html_snippet: str = Field(...)
    fix: str = Field(...)
    image_url_or_path: str | None = Field(...)


class IssueList(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"additionalProperties": False})

    issue_list: list[Issue] = Field(...)


class MetadataItem(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"additionalProperties": False})

    key: str
    value: str | int


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"additionalProperties": False})

    tool_name: str = Field(...)
    total_issues: int = Field(...)
    page: str = Field(...)
    issue_list: list[Issue] = Field(...)
    metadata: list[MetadataItem] = Field(...)
