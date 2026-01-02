from __future__ import annotations

import datetime
from pathlib import Path

import ynab

from .calendar_weeks import month_week_for_date
from .config import load_config
from .report import (
    build_report_table,
    categories_to_polars,
    freeze_model,
    get_budget_id,
    get_categories_to_watch,
    transactions_to_polars,
)


def main() -> None:
    config = load_config(Path("config.json"))

    ynab_config = ynab.Configuration(access_token=config.personal_access_token)

    with ynab.ApiClient(ynab_config) as api_client:
        budgets_api = ynab.BudgetsApi(api_client)
        budget_id = get_budget_id(budgets_api.get_budgets().data.budgets, config.budget_name)

        if budget_id is None:
            raise ValueError(f"no budget found with name {config.budget_name}")

        categories_api = ynab.CategoriesApi(api_client)
        category_groups = categories_api.get_categories(budget_id).data.category_groups
        categories_to_watch = get_categories_to_watch(
            category_groups,
            config.category_group_watch_list,
        )

        resolution_date = config.resolution_date or datetime.date.today()
        report_start = month_week_for_date(resolution_date).week_start
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

        report_table = build_report_table(
            categories_budgeted,
            transactions,
            {category.name for category in correct_month_categories},
        )

        print(report_table.collect())


if __name__ == "__main__":
    main()
