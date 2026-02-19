from pydantic import BaseModel, Field, ConfigDict
from typing import Literal

SeverityKey = Literal["critical", "serious", "moderate", "minor"]
SourceType = Literal["axe", "llm", "both"]
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


class IssueList(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"additionalProperties": False})

    issue_list: list[Issue] = Field(...)


class SeverityCount(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "additionalProperties": False,
            "required": ["critical", "serious", "moderate", "minor"]
        }
    )

    critical: int = Field(0)
    serious: int = Field(0)
    moderate: int = Field(0)
    minor: int = Field(0)

class SourceCount(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "additionalProperties": False,
            "required": ["axe", "llm", "both"]
        }
    )

    axe: int = Field(0)
    llm: int = Field(0)
    both: int = Field(0)

class WcagLevelCount(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "additionalProperties": False,
            "required": ["A", "AA", "AAA"]
        }
    )

    A: int = Field(0)
    AA: int = Field(0)
    AAA: int = Field(0)


class StaticReport(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"additionalProperties": False})

    issue_list: list[Issue] = Field(...)
    total_issues: int = Field(...)
    by_severity: SeverityCount = Field(...)
    by_source: SourceCount = Field(...)
    by_wcag_level: WcagLevelCount = Field(...)
    coverage_score: float = Field(...)
    top_priorities: list[str] = Field(...)

class ImageAnalyzerReport(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"additionalProperties": False})

    page: str = Field(...)
    issue_list: list[Issue] = Field(default_factory=list)
    skipped: int = Field(0)
    extracted: int = Field(...)