import json
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill

from utils.wcag_helper import WCAG_RULE_MAPPER, get_wcag_level

ISSUE_COLUMNS = [
    "id",
    "wcag_rule",
    "level",
    "description",
    "why it matters",
    "source",
    "html_snippet",
    "fix",
    "image_url_or_path",
]
LEVEL_ORDER = {"A": 0, "AA": 1, "AAA": 2}
REPORT_FILENAME = "ax_report.json"


def build_excel_report(results_dir: str) -> str:
    if not results_dir:
        raise ValueError("results_dir not found in tool_context.state. Run save first.")

    report = _load_report(results_dir)
    all_issues = _extract_issue_list(report)
    all_issues_df = _build_all_issues_df(all_issues)
    wcag_summary_df = _build_wcag_summary(all_issues_df)
    level_summary_df = _build_level_summary(all_issues)

    out_xlsx = str(Path(results_dir) / "ax_report.xlsx")
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
        level_summary_df.to_excel(writer, sheet_name="Level Summary", index=False, header=False)
        wcag_summary_df.to_excel(writer, sheet_name="WCAG Summary", index=False)
        all_issues_df.to_excel(writer, sheet_name="All Issues", index=False)
        _format_workbook(writer)

    return out_xlsx


def _build_all_issues_df(all_issues: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(all_issues)
    if df.empty:
        return pd.DataFrame(columns=ISSUE_COLUMNS)

    df["level"] = df.get("wcag_rule").apply(get_wcag_level)
    df["why it matters"] = df.get("why_this_matters")
    for column in ISSUE_COLUMNS:
        if column not in df.columns:
            df[column] = None
    df = df[ISSUE_COLUMNS]
    return _sort_with_level(df, by=["wcag_rule", "source", "id"], ascending=[True, True, True])


def _build_level_summary(all_issues: list[dict[str, Any]]) -> pd.DataFrame:
    level_counts = {"A": 0, "AA": 0, "AAA": 0}
    for issue in all_issues:
        level_counts[get_wcag_level(issue.get("wcag_rule"))] += 1

    return pd.DataFrame(
        {
            "summary": [
                f"Level A issues: {level_counts['A']}",
                f"Level AA issues: {level_counts['AA']}",
                f"Level AAA issues: {level_counts['AAA']}",
            ]
        }
    )


def _build_wcag_summary(all_issues_df: pd.DataFrame) -> pd.DataFrame:
    baseline_df = pd.DataFrame({"wcag_rule": _get_a_aa_wcag_rules()})
    if baseline_df.empty:
        return pd.DataFrame(columns=["wcag_rule", "level", "total_issues"])

    if all_issues_df.empty:
        summary_df = baseline_df.assign(total_issues=0)
    else:
        observed_counts_df = (
            all_issues_df.groupby("wcag_rule", dropna=False)["id"].count().reset_index(name="total_issues")
        )
        summary_df = baseline_df.merge(observed_counts_df, on="wcag_rule", how="left")
        summary_df["total_issues"] = summary_df["total_issues"].fillna(0).astype(int)

        extra_rules_df = observed_counts_df[~observed_counts_df["wcag_rule"].isin(summary_df["wcag_rule"])]
        if not extra_rules_df.empty:
            summary_df = pd.concat([summary_df, extra_rules_df], ignore_index=True)

    summary_df["level"] = summary_df["wcag_rule"].apply(get_wcag_level)
    summary_df = _sort_with_level(summary_df, by=["total_issues", "wcag_rule"], ascending=[False, True])
    return summary_df[["wcag_rule", "level", "total_issues"]]


def _sort_with_level(df: pd.DataFrame, by: list[str], ascending: list[bool]) -> pd.DataFrame:
    if df.empty:
        return df

    sorted_df = df.assign(level_order=df["level"].map(_level_order))
    sorted_df = sorted_df.sort_values(
        by=["level_order", *by],
        ascending=[True, *ascending],
        kind="stable",
    )
    return sorted_df.drop(columns=["level_order"])


def _get_a_aa_wcag_rules() -> list[str]:
    return list(dict.fromkeys(rule for rule in WCAG_RULE_MAPPER.values() if get_wcag_level(rule) in {"A", "AA"}))


def _level_order(level: object) -> int:
    if isinstance(level, str):
        return LEVEL_ORDER.get(level.upper(), 3)
    return 3


def _format_workbook(writer: pd.ExcelWriter) -> None:
    workbook = writer.book
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    workbook["Level Summary"].column_dimensions["A"].width = 40

    for sheet_name in ["WCAG Summary", "All Issues"]:
        ws = workbook[sheet_name]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(vertical="center", horizontal="center")

        for col_cells in ws.columns:
            col_letter = col_cells[0].column_letter
            max_len = max(len("" if cell.value is None else str(cell.value)) for cell in col_cells)
            ws.column_dimensions[col_letter].width = min(max(max_len + 2, 12), 70)


def _load_report(results_dir: str) -> dict[str, Any]:
    report_path = Path(results_dir) / REPORT_FILENAME
    if not report_path.exists():
        raise FileNotFoundError(f"Missing report file: {report_path}")

    with open(report_path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid report format in {report_path}: expected JSON object")
    return data


def _extract_issue_list(report: dict[str, Any]) -> list[dict[str, Any]]:
    issue_list = report.get("issue_list", [])
    all_issues: list[dict[str, Any]] = []
    if not isinstance(issue_list, list):
        return all_issues

    for issue in issue_list:
        if isinstance(issue, dict):
            all_issues.append(issue)
    return all_issues


if __name__ == "__main__":
    results_dir = "/home/pbianco/ax_tester/results/2026-05-18_15-54-29_shop.reply.com/2026-05-18_15-58-56"
    build_excel_report(results_dir)
