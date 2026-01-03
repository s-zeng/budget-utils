from __future__ import annotations

import html
from collections.abc import Mapping

import polars as pl

Currency = "£"


def _format_currency(value: float, *, show_zero: bool) -> str:
    rounded = round(value, 2)
    if rounded == 0 and not show_zero:
        return ""
    sign = "-" if rounded < 0 else ""
    return f"{sign}{Currency}{abs(rounded):,.2f}"


def _darken_hex(color: str, *, factor: float = 0.85) -> str:
    if not color.startswith("#") or len(color) != 7:
        return color
    try:
        red = int(color[1:3], 16)
        green = int(color[3:5], 16)
        blue = int(color[5:7], 16)
    except ValueError:
        return color
    red = max(0, min(255, int(red * factor)))
    green = max(0, min(255, int(green * factor)))
    blue = max(0, min(255, int(blue * factor)))
    return f"#{red:02x}{green:02x}{blue:02x}"


def build_visual_report_html(
    report_table: pl.LazyFrame,
    *,
    group_colors: Mapping[str, str],
    week_label: str,
    planned_year: int,
) -> str:
    report_df = report_table.collect()

    rows: list[str] = []
    for group_name, color in group_colors.items():
        group_df = report_df.filter(pl.col("category_group_name") == group_name).sort(
            "category_name"
        )
        if group_df.is_empty():
            continue

        planned_values: list[float] = []
        per_month_values: list[float] = []
        spent_values: list[float] = []
        remaining_values: list[float] = []

        for row in group_df.iter_rows(named=True):
            cadence = row["goal_cadence"]
            budgeted = float(row["budgeted"])
            planned = budgeted if cadence == "annual" else budgeted * 12
            per_month = planned / 12
            spent = float(row["spent"])
            remaining = per_month + spent

            planned_values.append(planned)
            per_month_values.append(per_month)
            spent_values.append(spent)
            remaining_values.append(remaining)

            rows.append(
                _row_html(
                    category=row["category_name"],
                    planned=planned,
                    per_month=per_month,
                    spent=spent,
                    remaining=remaining,
                    color=color,
                    is_total=False,
                    show_period_values=spent != 0,
                    is_annual=cadence == "annual",
                )
            )

        rows.append(
            _row_html(
                category=f"Total {group_name}",
                planned=sum(planned_values),
                per_month=sum(per_month_values),
                spent=sum(spent_values),
                remaining=sum(remaining_values),
                color=_darken_hex(color),
                is_total=True,
                show_period_values=True,
                is_annual=False,
            )
        )
    body_rows = "\n".join(rows)

    return "\n".join(
        [
            "<!DOCTYPE html>",
            "<html lang=\"en\">",
            "<head>",
            "  <meta charset=\"utf-8\">",
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
            "  <title>Budget Visual Report</title>",
            "  <style>",
            "    :root {",
            "      --grid: #d9d9d9;",
            "      --header-bg: #f7f3e9;",
            "      --text: #1f1f1f;",
            "    }",
            "    body {",
            "      margin: 24px;",
            "      font-family: \"Alegreya Sans\", \"Trebuchet MS\", sans-serif;",
            "      color: var(--text);",
            "      background: linear-gradient(180deg, #fbf9f4 0%, #f3efe7 100%);",
            "      -webkit-user-select: text;",
            "      user-select: text;",
            "    }",
            "    h1 {",
            "      font-size: 20px;",
            "      margin: 0 0 16px 0;",
            "      letter-spacing: 0.02em;",
            "      text-transform: uppercase;",
            "    }",
            "    table {",
            "      width: 100%;",
            "      border-collapse: collapse;",
            "      background: #fffefc;",
            "      box-shadow: 0 6px 24px rgba(0, 0, 0, 0.08);",
            "      user-select: none;",
            "    }",
            "    th, td {",
            "      border: 1px solid var(--grid);",
            "      padding: 6px 8px;",
            "      font-size: 13px;",
            "      vertical-align: middle;",
            "      -webkit-user-select: text;",
            "      user-select: text;",
            "    }",
            "    th {",
            "      background: var(--header-bg);",
            "      text-align: left;",
            "      font-weight: 700;",
            "    }",
            "    td.number {",
            "      text-align: right;",
            "      white-space: nowrap;",
            "    }",
            "    tr.total td {",
            "      font-weight: 700;",
            "      border-top: 2px solid #9a9a9a;",
            "    }",
            "    td.selected {",
            "      outline: 2px solid #2a5d86;",
            "      outline-offset: -2px;",
            "      position: relative;",
            "    }",
            "    @media (max-width: 760px) {",
            "      body { margin: 12px; }",
            "      th, td { font-size: 12px; }",
            "    }",
            "  </style>",
            "</head>",
            "<body>",
            f"  <h1>{html.escape(week_label)}</h1>",
            "  <table class=\"selectable\">",
            "    <thead>",
            "      <tr>",
            "        <th rowspan=\"2\">Category</th>",
            f"        <th rowspan=\"2\">{planned_year} (planned)</th>",
            f"        <th rowspan=\"2\">{planned_year} per month</th>",
            f"        <th colspan=\"2\">{html.escape(week_label)}</th>",
            "      </tr>",
            "      <tr>",
            "        <th>Spent</th>",
            "        <th>Remaining in period</th>",
            "      </tr>",
            "    </thead>",
            "    <tbody>",
            f"{body_rows}",
            "    </tbody>",
            "  </table>",
            "  <script>",
            "    const table = document.querySelector(\"table.selectable\");",
            "    if (table) {",
            "      const rows = Array.from(table.querySelectorAll(\"tbody tr\"));",
            "      const cellGrid = rows.map((row, rowIndex) => {",
            "        return Array.from(row.querySelectorAll(\"td\")).map((cell, colIndex) => {",
            "          cell.dataset.row = String(rowIndex);",
            "          cell.dataset.col = String(colIndex);",
            "          return cell;",
            "        });",
            "      });",
            "      let selecting = false;",
            "      let startCell = null;",
            "      let selection = null;",
            "      const clearSelection = () => {",
            "        table.querySelectorAll(\"td.selected\").forEach((cell) => {",
            "          cell.classList.remove(\"selected\");",
            "        });",
            "      };",
            "      const applySelection = (endCell) => {",
            "        if (!startCell || !endCell) {",
            "          return;",
            "        }",
            "        const startRow = Number(startCell.dataset.row);",
            "        const startCol = Number(startCell.dataset.col);",
            "        const endRow = Number(endCell.dataset.row);",
            "        const endCol = Number(endCell.dataset.col);",
            "        const minRow = Math.min(startRow, endRow);",
            "        const maxRow = Math.max(startRow, endRow);",
            "        const minCol = Math.min(startCol, endCol);",
            "        const maxCol = Math.max(startCol, endCol);",
            "        selection = { minRow, maxRow, minCol, maxCol };",
            "        clearSelection();",
            "        for (let row = minRow; row <= maxRow; row += 1) {",
            "          const cells = cellGrid[row] || [];",
            "          for (let col = minCol; col <= maxCol; col += 1) {",
            "            const cell = cells[col];",
            "            if (cell) {",
            "              cell.classList.add(\"selected\");",
            "            }",
            "          }",
            "        }",
            "      };",
            "      table.addEventListener(\"mousedown\", (event) => {",
            "        const cell = event.target.closest(\"td\");",
            "        if (!cell) {",
            "          return;",
            "        }",
            "        selecting = true;",
            "        startCell = cell;",
            "        applySelection(cell);",
            "        event.preventDefault();",
            "      });",
            "      table.addEventListener(\"mouseover\", (event) => {",
            "        if (!selecting) {",
            "          return;",
            "        }",
            "        const cell = event.target.closest(\"td\");",
            "        if (cell) {",
            "          applySelection(cell);",
            "        }",
            "      });",
            "      document.addEventListener(\"mouseup\", () => {",
            "        selecting = false;",
            "      });",
            "      document.addEventListener(\"copy\", (event) => {",
            "        if (!selection) {",
            "          return;",
            "        }",
            "        const { minRow, maxRow, minCol, maxCol } = selection;",
            "        const lines = [];",
            "        for (let row = minRow; row <= maxRow; row += 1) {",
            "          const cells = cellGrid[row] || [];",
            "          const values = [];",
            "          for (let col = minCol; col <= maxCol; col += 1) {",
            "            const cell = cells[col];",
            "            values.push(cell ? cell.innerText.trim() : \"\");",
            "          }",
            "          lines.push(values.join(\"\\t\"));",
            "        }",
            "        event.clipboardData.setData(\"text/plain\", lines.join(\"\\n\"));",
            "        event.preventDefault();",
            "      });",
            "    }",
            "  </script>",
            "</body>",
            "</html>",
        ]
    )


def _row_html(
    *,
    category: str,
    planned: float,
    per_month: float,
    spent: float,
    remaining: float,
    color: str,
    is_total: bool,
    show_period_values: bool,
    is_annual: bool,
) -> str:
    class_name = "total" if is_total else "group"
    row_style = f" style=\"background-color: {color};\""
    show_values = show_period_values or is_total
    annual_style = ""
    if is_annual:
        annual_style = f" style=\"background-color: {_darken_hex(color, factor=0.7)};\""

    return "\n".join(
        [
            f"      <tr class=\"{class_name}\"{row_style}>",
            f"        <td>{html.escape(category)}</td>",
            (
                "        <td class=\"number\""
                f"{annual_style}>{_format_currency(planned, show_zero=is_total)}</td>"
            ),
            (
                "        <td class=\"number\""
                f"{annual_style}>{_format_currency(per_month, show_zero=is_total)}</td>"
            ),
            f"        <td class=\"number\">{_format_currency(-spent, show_zero=show_values)}</td>",
            f"        <td class=\"number\">{_format_currency(remaining, show_zero=show_values)}</td>",
            "      </tr>",
        ]
    )
