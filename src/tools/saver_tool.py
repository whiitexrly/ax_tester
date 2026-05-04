"""Persistence tool for saving per-page reports under a run timestamp folder."""

import json
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path

from google.adk.tools.tool_context import ToolContext

from common import FINAL_REPORT_KEYS, ContextKey
from schemas import ScoreInfo
from utils.report_excel import build_excel_report
from utils.report_pptx import build_pptx_report
from utils.wcag_helper import get_wcag_level

logger = logging.getLogger(__name__)

RESULTS_BASE_DIR = Path("ax_tester") / "results"


def generate_run_timestamp() -> str:
    """Generate a timestamp suitable as run/page folder prefix."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _get_run_dir(crawl_folder_name: str) -> Path:
    """Ensure and return the crawl directory."""
    run_dir = RESULTS_BASE_DIR / crawl_folder_name
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_score_info(raw_score: object) -> ScoreInfo:
    if not isinstance(raw_score, dict):
        return ScoreInfo()

    return ScoreInfo(
        level_A=_safe_int(raw_score.get("level_A", 0)),
        level_AA=_safe_int(raw_score.get("level_AA", 0)),
        level_AAA=_safe_int(raw_score.get("level_AAA", 0)),
    )


def _get_unique_page_dir(base_dir: Path) -> Path:
    page_folder_name = generate_run_timestamp()
    candidate = base_dir / page_folder_name
    if not candidate.exists():
        return candidate

    suffix = 2
    while True:
        with_suffix = base_dir / f"{page_folder_name}_{suffix}"
        if not with_suffix.exists():
            return with_suffix
        suffix += 1


def _load_json_dict(file_path: Path) -> dict[str, object] | None:
    try:
        with open(file_path, encoding="utf-8") as file:
            data = json.load(file)
    except Exception:
        return None

    return data if isinstance(data, dict) else None


def _collect_run_ax_reports(run_dir: Path) -> list[dict[str, object]]:
    """Collect all page-level `ax_report.json` files in the crawl folder."""
    if not run_dir.exists():
        return []

    reports: list[dict[str, object]] = []
    for page_dir in sorted(run_dir.iterdir()):
        if not page_dir.is_dir():
            continue
        ax_report = _load_json_dict(page_dir / "ax_report.json")
        if ax_report is not None:
            reports.append(ax_report)
    return reports


def write_run_results_index(crawl_folder_name: str) -> tuple[Path, list[dict[str, object]]]:
    """Write `<run_dir>/results.json` from all discovered page-level ax reports."""
    run_dir = _get_run_dir(crawl_folder_name)
    reports = _collect_run_ax_reports(run_dir)
    results_file = run_dir / "results.json"
    with open(results_file, "w", encoding="utf-8") as file:
        json.dump(reports, file, indent=2, ensure_ascii=False)
    return results_file, reports


def run_save(tool_context: ToolContext) -> dict[str, object]:
    """Save current page reports into `<results>/<crawl_folder_name>/<page_folder>/`."""

    crawl_folder_name = str(tool_context.state.get(ContextKey.CRAWL_FOLDER_NAME, "")).strip()
    if not crawl_folder_name:
        raise ValueError("Missing required state key: ContextKey.CRAWL_FOLDER_NAME")

    run_dir = _get_run_dir(crawl_folder_name)
    page_dir = _get_unique_page_dir(base_dir=run_dir)
    page_dir.mkdir(parents=True, exist_ok=True)

    all_issues: list[dict] = []
    score_passed_agg: ScoreInfo = ScoreInfo()
    score_total_agg: ScoreInfo = ScoreInfo()

    for report_name in FINAL_REPORT_KEYS:
        report_data = tool_context.state.get(report_name, {})
        with open(page_dir / f"{report_name.lower()}.json", "w", encoding="utf-8") as file:
            json.dump(report_data, file, indent=2, ensure_ascii=False)

        issue_list = report_data.get("issue_list", []) if isinstance(report_data, dict) else []
        issue_list = issue_list if isinstance(issue_list, list) else []

        # filter by wcag compliance level
        issue_list = [issue for issue in issue_list if issue.get("severity", "") != "minor"]
        for compliance_level in ["AAA", "AA", "A"]:
            if tool_context.state.get(ContextKey.COMPLIANCE_LEVEL, "AA") == compliance_level:
                break
            issue_list = [issue for issue in issue_list if compliance_level not in issue.get("wcag_rule", "")]

        # compute score info
        if report_name == ContextKey.STATIC_REPORT:
            axe_report = tool_context.state.get(ContextKey.AXE_REPORT, {})
            axe_score_total = _safe_score_info(
                axe_report.get("score_total", {}) if isinstance(axe_report, dict) else {}
            )
            score_total_agg.level_A += axe_score_total.level_A
            score_total_agg.level_AA += axe_score_total.level_AA
            score_total_agg.level_AAA += axe_score_total.level_AAA

            level_counts = Counter(get_wcag_level(item.get("wcag_rule")) for item in issue_list)
            score_passed_agg.level_A += axe_score_total.level_A - level_counts["A"]
            score_passed_agg.level_AA += axe_score_total.level_AA - level_counts["AA"]
            score_passed_agg.level_AAA += axe_score_total.level_AAA - level_counts["AAA"]
        else:
            report_score_total = _safe_score_info(
                report_data.get("score_total", {}) if isinstance(report_data, dict) else {}
            )
            report_score_passed = _safe_score_info(
                report_data.get("score_passed", {}) if isinstance(report_data, dict) else {}
            )

            score_total_agg.level_A += report_score_total.level_A
            score_total_agg.level_AA += report_score_total.level_AA
            score_total_agg.level_AAA += report_score_total.level_AAA

            score_passed_agg.level_A += report_score_passed.level_A
            score_passed_agg.level_AA += report_score_passed.level_AA
            score_passed_agg.level_AAA += report_score_passed.level_AAA

        all_issues.extend(issue_list)

    aggregate_report = {
        "tool_name": "ax_tester",
        "total_issues": len(all_issues),
        "page": tool_context.state.get(ContextKey.STATIC_REPORT, {}).get("page", ""),
        "issue_list": all_issues,
        "score_passed": score_passed_agg.model_dump(),
        "score_total": score_total_agg.model_dump(),
        "metadata": [],
    }
    with open(page_dir / "ax_report.json", "w", encoding="utf-8") as file:
        json.dump(aggregate_report, file, indent=2, ensure_ascii=False)

    build_excel_report(str(page_dir))
    build_pptx_report(str(page_dir))

    return {
        "status": "saved",
        "run_timestamp": crawl_folder_name,
        "run_dir": str(run_dir),
        "page_dir": str(page_dir),
    }
