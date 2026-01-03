from __future__ import annotations

import datetime
from pathlib import Path
from typing import assert_never

import polars as pl
import ynab

from .calendar_weeks import month_week_for_date
from .config import CsvOutput, VisualOutput, load_config
from .report import (
    build_category_group_totals_table,
    build_report_table,
    categories_to_polars,
    freeze_model,
    get_budget_id,
    get_categories_to_watch,
    relevant_transactions,
    transactions_to_polars,
)
from .visual_report import build_visual_report_html


def main() -> None:
    config = load_config(Path("config.json"))

    ynab_config = ynab.Configuration(access_token=config.personal_access_token)

    with ynab.ApiClient(ynab_config) as api_client:
        budgets_api = ynab.BudgetsApi(api_client)
        budget_id = get_budget_id(
            budgets_api.get_budgets().data.budgets, config.budget_name
        )

        if budget_id is None:
            raise ValueError(f"no budget found with name {config.budget_name}")

        categories_api = ynab.CategoriesApi(api_client)
        category_groups = categories_api.get_categories(budget_id).data.category_groups
        categories_to_watch = get_categories_to_watch(
            category_groups,
            config.category_group_watch_list,
        )

        resolution_date = config.resolution_date or datetime.date.today()
        report_week = month_week_for_date(resolution_date)
        report_start = report_week.week_start
        report_end = report_week.week_end
        correct_month_categories = {
            freeze_model(
                categories_api.get_month_category_by_id(
                    budget_id=budget_id,
                    month=report_start,
                    category_id=category.id,
                ).data.category
            )
            for category in categories_to_watch
        }

        categories_budgeted = categories_to_polars(correct_month_categories)

        transactions_api = ynab.TransactionsApi(api_client)
        transactions = transactions_to_polars(
            transactions_api.get_transactions(
                budget_id=budget_id,
                since_date=report_start,
            ).data.transactions
        )
        transactions = relevant_transactions(transactions, report_start, report_end)

        report_table = build_report_table(
            categories_budgeted,
            transactions,
            {category.name for category in correct_month_categories},
        )

        if not config.show_all_rows:
            report_table = report_table.filter(pl.col("spent") != 0)
        category_group_totals = build_category_group_totals_table(report_table)

        week_year = report_week.week_start.year
        week_number = report_week.week_number
        start_label = report_start.strftime("%A %Y-%m-%d")
        end_label = report_end.strftime("%A %Y-%m-%d")
        print(
            f"Week {week_number} of {week_year}, starting on {start_label} and ending on {end_label}"
        )
        week_short_start = report_start.strftime("%b %d").replace(" 0", " ")
        week_short_end = report_end.strftime("%b %d").replace(" 0", " ")
        visual_week_label = (
            f"Week {week_number} ({week_short_start} - {week_short_end})"
        )
        match config.output_format:
            case "polars_print":
                with pl.Config(tbl_rows=-1):
                    print(report_table.collect())
                    print("Category group totals")
                    print(category_group_totals.collect())
            case "csv_print":
                csv_text = report_table.collect().write_csv()
                totals_text = category_group_totals.collect().write_csv()
                print(csv_text, end="")
                print("category_group_totals")
                print(totals_text, end="")
            case CsvOutput():
                csv_text = report_table.collect().write_csv()
                totals_text = category_group_totals.collect().write_csv()
                output_path = config.output_format.csv_output
                totals_path = output_path.with_name(
                    f"{output_path.stem}_category_group_totals{output_path.suffix}"
                )
                output_path.write_text(csv_text)
                totals_path.write_text(totals_text)
            case VisualOutput():
                html_text = build_visual_report_html(
                    report_table,
                    group_colors=config.category_group_watch_list,
                    week_label=visual_week_label,
                    planned_year=week_year,
                )
                output_path = config.output_format.visual_output
                output_path.write_text(html_text)
            case _:
                assert_never(config.output_format)


if __name__ == "__main__":
    main()
