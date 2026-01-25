from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict

import polars as pl
import pytest
from hypothesis import assume, given, strategies as st
from hypothesis.strategies import SearchStrategy
from ynab import models
from ynab.models.transaction_cleared_status import TransactionClearedStatus

from budget_utils import report
from budget_utils.types import CategoryFrame, TransactionFrame

LETTERS: SearchStrategy[str] = st.characters(min_codepoint=97, max_codepoint=122)
SHORT_TEXT: SearchStrategy[str] = st.text(alphabet=LETTERS, min_size=1, max_size=10)
SHORT_ID: SearchStrategy[str] = st.text(alphabet=LETTERS, min_size=1, max_size=12)
AMOUNTS: SearchStrategy[float] = st.floats(
    min_value=-1_000_000,
    max_value=1_000_000,
    allow_nan=False,
    allow_infinity=False,
)
DATES: SearchStrategy[dt.date] = st.dates(
    min_value=dt.date(2000, 1, 1), max_value=dt.date(2030, 12, 31)
)


def _category_group(name: str) -> models.CategoryGroupWithCategories:
    return models.CategoryGroupWithCategories(
        id=f"group-{name}",
        name=name,
        hidden=False,
        deleted=False,
        categories=[],
    )


def _category_frame(
    rows: list[tuple[str, str, float, float, str]],
) -> CategoryFrame:
    return CategoryFrame(
        pl.LazyFrame(
            rows,
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


def _transaction_frame(
    rows: list[tuple[dt.date, float, str | None, str]],
) -> TransactionFrame:
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


@given(
    st.sets(SHORT_TEXT, min_size=0, max_size=8),
    st.sets(SHORT_TEXT, min_size=0, max_size=8),
)
def test_get_missing_category_groups(
    group_names: set[str],
    watch_names: set[str],
) -> None:
    groups = [_category_group(name) for name in group_names]
    watch_list = {name: "#ffffff" for name in watch_names}
    missing = report.get_missing_category_groups(groups, watch_list)
    assert missing == watch_names.difference(group_names)


@st.composite
def category_rows(draw: st.DrawFn) -> list[tuple[str, str, float, float, str]]:
    names: list[str] = draw(st.lists(SHORT_TEXT, min_size=1, max_size=8, unique=True))
    groups: list[str] = draw(st.lists(SHORT_TEXT, min_size=1, max_size=4, unique=True))
    rows: list[tuple[str, str, float, float, str]] = []
    for name in names:
        group: str = draw(st.sampled_from(groups))
        budgeted: float = draw(AMOUNTS)
        balance: float = draw(AMOUNTS)
        goal_cadence: str = draw(st.sampled_from(["monthly", "annual"]))
        rows.append(
            (
                name,
                group,
                budgeted,
                balance,
                goal_cadence,
            )
        )
    return rows


@st.composite
def transaction_rows(
    draw: st.DrawFn, category_names: list[str]
) -> list[tuple[dt.date, float, str | None, str]]:
    count: int = draw(st.integers(min_value=0, max_value=25))
    other_names: list[str] = draw(
        st.lists(SHORT_TEXT, min_size=1, max_size=5, unique=True)
    )
    other_names = [
        f"other_{name}"
        for name in other_names
        if f"other_{name}" not in set(category_names)
    ]
    if not other_names:
        other_names = ["other"]
    rows: list[tuple[dt.date, float, str | None, str]] = []
    for _ in range(count):
        choose_known: bool = draw(st.booleans())
        date_value: dt.date = draw(DATES)
        amount: float = draw(AMOUNTS)
        payee_name: str | None = draw(st.one_of(st.none(), SHORT_TEXT))
        category_name: str = draw(
            st.sampled_from(category_names if choose_known else other_names)
        )
        rows.append(
            (
                date_value,
                amount,
                payee_name,
                category_name,
            )
        )
    return rows


@st.composite
def categories_and_transactions(
    draw: st.DrawFn,
) -> tuple[
    list[tuple[str, str, float, float, str]],
    list[tuple[dt.date, float, str | None, str]],
]:
    categories: list[tuple[str, str, float, float, str]] = draw(category_rows())
    transactions: list[tuple[dt.date, float, str | None, str]] = draw(
        transaction_rows([row[0] for row in categories])
    )
    return categories, transactions


@st.composite
def transaction_rows_any(
    draw: st.DrawFn,
) -> list[tuple[dt.date, float, str | None, str]]:
    count: int = draw(st.integers(min_value=0, max_value=25))
    rows: list[tuple[dt.date, float, str | None, str]] = []
    for _ in range(count):
        date_value: dt.date = draw(DATES)
        amount: float = draw(AMOUNTS)
        payee_name: str | None = draw(st.one_of(st.none(), SHORT_TEXT))
        category_name: str = draw(SHORT_TEXT)
        rows.append((date_value, amount, payee_name, category_name))
    return rows


@st.composite
def budget_summaries(
    draw: st.DrawFn,
) -> list[models.BudgetSummary]:
    pairs: list[tuple[str, str]] = draw(
        st.lists(
            st.tuples(SHORT_ID, SHORT_TEXT),
            min_size=1,
            max_size=8,
            unique_by=lambda pair: pair[1],
        )
    )
    return [models.BudgetSummary(id=budget_id, name=name) for budget_id, name in pairs]


@st.composite
def budget_summaries_and_target(
    draw: st.DrawFn,
) -> tuple[list[models.BudgetSummary], str]:
    summaries: list[models.BudgetSummary] = draw(budget_summaries())
    target: str = draw(st.sampled_from([summary.name for summary in summaries]))
    return summaries, target


@st.composite
def transaction_details(
    draw: st.DrawFn,
) -> list[models.TransactionDetail]:
    amount_strategy: SearchStrategy[int] = st.integers(
        min_value=-1_000_000, max_value=1_000_000
    )

    @st.composite
    def subtransaction_strategy(
        draw: st.DrawFn, transaction_id: str
    ) -> models.SubTransaction:
        category_name: str | None = draw(st.one_of(st.none(), SHORT_TEXT))
        category_id: str | None = (
            draw(st.one_of(st.none(), SHORT_ID)) if category_name else None
        )
        sub_id: str = draw(SHORT_ID)
        amount: int = draw(amount_strategy)
        payee_name: str | None = draw(st.one_of(st.none(), SHORT_TEXT))
        return models.SubTransaction(
            id=sub_id,
            transaction_id=transaction_id,
            amount=amount,
            memo=None,
            payee_id=None,
            payee_name=payee_name,
            category_id=category_id,
            category_name=category_name,
            transfer_account_id=None,
            transfer_transaction_id=None,
            deleted=False,
        )

    count: int = draw(st.integers(min_value=0, max_value=15))
    transactions: list[models.TransactionDetail] = []
    for _ in range(count):
        transaction_id: str = draw(SHORT_ID)
        subtransactions: list[models.SubTransaction] = draw(
            st.lists(subtransaction_strategy(transaction_id), min_size=0, max_size=3)
        )
        is_split: bool = bool(subtransactions)
        category_name: str | None = (
            "Split" if is_split else draw(st.one_of(st.none(), SHORT_TEXT))
        )
        category_id: str | None = (
            None if category_name is None else draw(st.one_of(st.none(), SHORT_ID))
        )
        date_value: dt.date = draw(DATES)
        amount: int = draw(amount_strategy)
        payee_name: str | None = draw(st.one_of(st.none(), SHORT_TEXT))
        transactions.append(
            models.TransactionDetail(
                id=transaction_id,
                date=date_value,
                amount=amount,
                memo=None,
                cleared=TransactionClearedStatus.CLEARED,
                approved=True,
                flag_color=None,
                flag_name=None,
                account_id="acc-1",
                payee_id=None,
                category_id=category_id,
                transfer_account_id=None,
                transfer_transaction_id=None,
                matched_transaction_id=None,
                import_id=None,
                import_payee_name=None,
                import_payee_name_original=None,
                debt_transaction_type=None,
                deleted=False,
                account_name="Checking",
                payee_name=payee_name,
                category_name=category_name,
                subtransactions=subtransactions,
            )
        )
    return transactions


@given(budget_summaries_and_target())
def test_get_budget_id_finds_match(
    payload: tuple[list[models.BudgetSummary], str],
) -> None:
    summaries, target = payload
    expected_id = next(summary.id for summary in summaries if summary.name == target)
    assert report.get_budget_id(summaries, target) == expected_id


@given(budget_summaries(), SHORT_TEXT)
def test_get_budget_id_missing_returns_none(
    summaries: list[models.BudgetSummary],
    missing_name: str,
) -> None:
    assume(missing_name not in {summary.name for summary in summaries})
    assert report.get_budget_id(summaries, missing_name) is None


@given(categories_and_transactions())
def test_build_report_table_sums_spent(
    payload: tuple[
        list[tuple[str, str, float, float, str]],
        list[tuple[dt.date, float, str | None, str]],
    ],
) -> None:
    categories, transactions = payload
    category_names = [row[0] for row in categories]
    categories_frame = _category_frame(categories)
    transactions_frame = _transaction_frame(transactions)

    report_table = report.build_report_table(
        categories_frame, transactions_frame, set(category_names)
    ).collect()
    spent_expected: dict[str, float] = defaultdict(float)
    for _, amount, _, category_name in transactions:
        if category_name in category_names:
            spent_expected[category_name] += amount

    assert report_table.shape[0] == len(category_names)
    for row in report_table.to_dicts():
        assert row["spent"] == pytest.approx(spent_expected[row["category_name"]])


@given(transaction_rows_any(), DATES, DATES)
def test_relevant_transactions_filters_range(
    rows: list[tuple[dt.date, float, str | None, str]],
    start: dt.date,
    end: dt.date,
) -> None:
    if start > end:
        start, end = end, start
    transactions_frame = _transaction_frame(rows)
    filtered = report.relevant_transactions(transactions_frame, start, end).collect()

    filtered_rows = [
        (
            item["date"],
            item["amount"],
            item["payee_name"],
            item["category_name"],
        )
        for item in filtered.to_dicts()
    ]
    expected_rows = [
        (date, amount, payee, category)
        for date, amount, payee, category in rows
        if start <= date <= end
    ]
    assert Counter(filtered_rows) == Counter(expected_rows)
    assert all(start <= date <= end for date, _, _, _ in filtered_rows)


@given(categories_and_transactions())
def test_category_group_totals_match_rows(
    payload: tuple[
        list[tuple[str, str, float, float, str]],
        list[tuple[dt.date, float, str | None, str]],
    ],
) -> None:
    categories, transactions = payload
    category_names = [row[0] for row in categories]
    report_table = report.build_report_table(
        _category_frame(categories),
        _transaction_frame(transactions),
        set(category_names),
    )
    report_df = report_table.collect()
    totals_df = report.build_category_group_totals_table(report_table).collect()

    group_sums: dict[str, dict[str, float]] = defaultdict(
        lambda: {"budgeted": 0.0, "spent": 0.0, "balance": 0.0}
    )
    for row in report_df.to_dicts():
        group = row["category_group_name"]
        group_sums[group]["budgeted"] += float(row["budgeted"])
        group_sums[group]["spent"] += float(row["spent"])
        group_sums[group]["balance"] += float(row["balance"])

    totals_by_group = {row["category_group_name"]: row for row in totals_df.to_dicts()}
    for group_name, sums in group_sums.items():
        totals_row = totals_by_group[group_name]
        assert totals_row["budgeted"] == pytest.approx(sums["budgeted"])
        assert totals_row["spent"] == pytest.approx(sums["spent"])
        assert totals_row["balance"] == pytest.approx(sums["balance"])

    overall = totals_by_group["Total"]
    overall_expected = {
        "budgeted": sum(sums["budgeted"] for sums in group_sums.values()),
        "spent": sum(sums["spent"] for sums in group_sums.values()),
        "balance": sum(sums["balance"] for sums in group_sums.values()),
    }
    assert overall["budgeted"] == pytest.approx(overall_expected["budgeted"])
    assert overall["spent"] == pytest.approx(overall_expected["spent"])
    assert overall["balance"] == pytest.approx(overall_expected["balance"])


@given(transaction_details())
def test_transactions_to_polars_matches_manual_rows(
    transactions: list[models.TransactionDetail],
) -> None:
    expected_rows = []
    for transaction in transactions:
        if transaction.subtransactions:
            for subtransaction in transaction.subtransactions:
                if subtransaction.category_name is None:
                    continue
                expected_rows.append(
                    (
                        transaction.var_date,
                        subtransaction.amount / 1000,
                        subtransaction.payee_name or transaction.payee_name,
                        subtransaction.category_name,
                    )
                )
        elif transaction.category_name is not None:
            expected_rows.append(
                (
                    transaction.var_date,
                    transaction.amount / 1000,
                    transaction.payee_name,
                    transaction.category_name,
                )
            )

    result = report.transactions_to_polars(transactions).collect()
    result_rows = [
        (row["date"], row["amount"], row["payee_name"], row["category_name"])
        for row in result.to_dicts()
    ]
    assert result_rows == expected_rows
