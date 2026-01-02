from __future__ import annotations

import datetime
from collections.abc import Iterable

import polars as pl
from pydantic import BaseModel
from ynab.models import BudgetSummary, CategoryGroupWithCategories, TransactionDetail
from ynab.models.category import Category

from .types import CategoryFrame, TransactionFrame, Uuid


def get_budget_id(data: Iterable[BudgetSummary], budget_name: str) -> Uuid | None:
    for budget_summary in data:
        if budget_summary.name == budget_name:
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
            schema={
                "date": pl.Date,
                "amount": pl.Float64,
                "payee_name": pl.String,
                "category_name": pl.String,
            },
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
    group_watch_list: Iterable[str],
) -> set[Category]:
    groups = set(group_watch_list)
    return {
        freeze_model(category)
        for group in data
        for category in group.categories
        if group.name in groups and not category.hidden
    }


def categories_to_polars(categories: Iterable[Category]) -> CategoryFrame:
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


def build_report_table(
    categories_budgeted: CategoryFrame,
    transactions: TransactionFrame,
    category_names: set[str],
) -> pl.LazyFrame:
    total_spent = (
        transactions.filter(pl.col("category_name").is_in(category_names))
        .group_by("category_name")
        .agg(pl.col("amount").sum().alias("spent"))
    )

    return (
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
