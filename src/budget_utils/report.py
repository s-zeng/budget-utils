from __future__ import annotations

import datetime
from collections.abc import Iterable, Mapping

import polars as pl
from pydantic import BaseModel
from ynab.models import BudgetSummary, CategoryGroupWithCategories, TransactionDetail
from ynab.models.category import Category

from .types import CategoryFrame, TransactionFrame, Uuid


def get_budget_id(data: Iterable[BudgetSummary], budget_name: str) -> Uuid | None:
    return next(
        (
            Uuid(budget_summary.id)
            for budget_summary in data
            if budget_summary.name == budget_name
        ),
        None,
    )


def transactions_to_polars(data: Iterable[TransactionDetail]) -> TransactionFrame:
    rows = [row for transaction in data for row in _transaction_rows(transaction)]
    return TransactionFrame(
        pl.LazyFrame(
            rows,
            orient="row",
            schema={
                "date": pl.Date,
                "amount": pl.Float64,
                "payee_name": pl.String,
                "category_name": pl.String,
            },
        )
    )


def _transaction_rows(
    transaction: TransactionDetail,
) -> Iterable[tuple[datetime.date, float, str | None, str]]:
    if transaction.subtransactions:
        return (
            (
                transaction.var_date,
                subtransaction.amount / 1000,
                subtransaction.payee_name or transaction.payee_name,
                subtransaction.category_name,
            )
            for subtransaction in transaction.subtransactions
            if subtransaction.category_name is not None
        )
    if transaction.category_name is None:
        return ()
    return (
        (
            transaction.var_date,
            transaction.amount / 1000,
            transaction.payee_name,
            transaction.category_name,
        ),
    )


def relevant_transactions(
    df: TransactionFrame,
    start_date: datetime.date,
    end_date: datetime.date,
) -> TransactionFrame:
    return TransactionFrame(
        df.filter(pl.col("date") <= end_date).filter(pl.col("date") >= start_date)
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
    group_watch_list: Mapping[str, str],
) -> set[Category]:
    groups = set(group_watch_list)
    return {
        freeze_model(category)
        for group in data
        for category in group.categories
        if group.name in groups and not category.hidden
    }


def get_missing_category_groups(
    data: Iterable[CategoryGroupWithCategories],
    group_watch_list: Mapping[str, str],
) -> set[str]:
    available = {group.name for group in data}
    return set(group_watch_list).difference(available)


def categories_to_polars(categories: Iterable[Category]) -> CategoryFrame:
    return CategoryFrame(
        pl.LazyFrame(
            [
                (
                    category.name,
                    category.category_group_name,
                    category.budgeted / 1000,
                    category.balance / 1000,
                    "monthly"
                    if category.goal_target is not None and category.goal_cadence == 1
                    else "annual",
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


def build_category_group_totals_table(report_table: pl.LazyFrame) -> pl.LazyFrame:
    group_totals = (
        report_table.group_by("category_group_name")
        .agg(
            pl.col("budgeted").sum().alias("budgeted"),
            pl.col("spent").sum().alias("spent"),
            pl.col("balance").sum().alias("balance"),
        )
        .select("category_group_name", "budgeted", "spent", "balance")
        .sort("category_group_name")
    )
    overall_total = report_table.select(
        pl.lit("Total").alias("category_group_name"),
        pl.col("budgeted").sum().alias("budgeted"),
        pl.col("spent").sum().alias("spent"),
        pl.col("balance").sum().alias("balance"),
    )
    return pl.concat([group_totals, overall_total], how="vertical")
