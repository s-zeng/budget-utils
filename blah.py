from ynab.models.category import Category
import ynab
import datetime
import polars as pl
from ynab.models import BudgetSummary, TransactionDetail, CategoryGroupWithCategories
from collections.abc import Iterable
from pydantic import BaseModel
from pathlib import Path
from typing import NewType


class Config(BaseModel):
    budgetName: str
    personalAccessToken: str
    categoryGroupWatchList: list[str]


Uuid = NewType("Uuid", str)
TransactionFrame = NewType("TransactionFrame", pl.LazyFrame)
CategoryFrame = NewType("CategoryFrame", pl.LazyFrame)


def get_id(data: Iterable[BudgetSummary], budgetName: str) -> Uuid | None:
    for budget_summary in data:
        if budget_summary.name == budgetName:
            return Uuid(budget_summary.id)
    return None


def transactions_to_polars(data: Iterable[TransactionDetail]) -> TransactionFrame:
    return TransactionFrame(
        pl.LazyFrame(
            [
                (
                    transaction.var_date,
                    transaction.amount / 1000,
                    transaction.payee_name,
                    transaction.category_name,
                )
                for transaction in data
            ],
            orient="row",
            schema=("date", "amount", "payee_name", "category_name"),
        )
    )


def relevant_transactions(
    df: TransactionFrame,
    start_date: datetime.date,
    end_date: datetime.date,
) -> TransactionFrame:
    return TransactionFrame(
        df.filter(pl.col("date") < end_date).filter(pl.col("date") > start_date)
    )


def freeze_model[T: BaseModel](model: T) -> T:
    new_model = model.model_copy()
    new_model.model_config["frozen"] = True

    HashableSubclass = type(
        f"_{type(model).__name__}Hashable",
        (type(model),),
        {"__hash__": lambda m: hash(tuple(m.to_dict().items()))},
    )

    new_model.__class__ = HashableSubclass
    return new_model


def get_categories_to_watch(
    data: Iterable[CategoryGroupWithCategories],
) -> set[Category]:
    return {
        freeze_model(category)
        for group in data
        for category in group.categories
        if group.name in set(config.categoryGroupWatchList) and not category.hidden
    }


def categories_to_polars(categories: Iterable[Category]) -> pl.LazyFrame:
    return CategoryFrame(
        pl.LazyFrame(
            [
                (
                    category.name,
                    category.category_group_name,
                    category.budgeted / 1000,
                    category.balance / 1000,
                    "monthly" if category.goal_cadence == 1 else "annual",
                )
                for category in categories
            ],
            orient="row",
            schema=(
                "category_name",
                "category_group_name",
                "budgeted",
                "balance",
                "goal_cadence",
            ),
        )
    )


config = Config.model_validate_json(Path("config.json").read_text())

ynab_config = ynab.Configuration(access_token=config.personalAccessToken)

with ynab.ApiClient(ynab_config) as api_client:
    budgets_api = ynab.BudgetsApi(api_client)
    budget_id = get_id(budgets_api.get_budgets().data.budgets, config.budgetName)

    if budget_id is None:
        raise ValueError(f"no budget found with name {config.budgetName}")

    categories_api = ynab.CategoriesApi(api_client)
    category_groups = categories_api.get_categories(budget_id).data.category_groups
    categories_to_watch = get_categories_to_watch(category_groups)

    correct_month_categories = {
        freeze_model(
            categories_api.get_month_category_by_id(
                budget_id=budget_id,
                month=datetime.date(2025, 12, 25).replace(day=1),
                category_id=category.id,
            ).data.category
        )
        for category in categories_to_watch
    }

    categories_budgeted = categories_to_polars(correct_month_categories)

    transactions_api = ynab.TransactionsApi(api_client)
    transactions = transactions_to_polars(
        transactions_api.get_transactions(
            budget_id=budget_id, since_date=datetime.date(2025, 12, 25)
        ).data.transactions
    )
    total_spent = (
        transactions.filter(
            pl.col("category_name").is_in(
                {category.name for category in correct_month_categories}
            )
        )
        .group_by("category_name")
        .agg(pl.col("amount").sum().alias("spent"))
    )

    report_table = (
        categories_budgeted.join(total_spent, on="category_name", how="left")
        .with_columns(pl.col("spent").fill_null(0))
        .select(
            "category_group_name",
            "category_name",
            "budgeted",
            "spent",
            "balance",
            "goal_cadence",
        )
        .sort("category_group_name", "category_name")
    )

    print(report_table.collect())
