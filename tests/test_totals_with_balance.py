from __future__ import annotations

import datetime as dt
import io

import polars as pl
import pytest
import ynab
from ynab import models
from ynab.models.transaction_cleared_status import TransactionClearedStatus

from budget_utils import cli
from budget_utils.config import Config
from budget_utils.visual_report import Currency, build_visual_report_html


def _make_config(*, output_format: object, show_all_rows: bool) -> Config:
    payload: dict[str, object] = {
        "budgetName": "Test Budget",
        "personalAccessToken": "token",
        "categoryGroupWatchList": {
            "Essentials": "#dfe7f5",
        },
        "resolution_date": dt.date(2024, 3, 13),
        "showAllRows": show_all_rows,
        "outputFormat": output_format,
    }
    return Config.model_validate(payload)


def _make_categories() -> dict[str, models.Category]:
    groceries = models.Category(
        id="cat-groceries",
        category_group_id="group-essentials",
        category_group_name="Essentials",
        name="Groceries",
        hidden=False,
        original_category_group_id=None,
        note=None,
        budgeted=50000,
        activity=0,
        balance=30000,
        goal_type=None,
        goal_needs_whole_amount=None,
        goal_day=None,
        goal_cadence=1,
        goal_cadence_frequency=None,
        goal_creation_month=None,
        goal_target=60000,
        goal_target_month=None,
        goal_percentage_complete=None,
        goal_months_to_budget=None,
        goal_under_funded=None,
        goal_overall_funded=None,
        goal_overall_left=None,
        goal_snoozed_at=None,
        deleted=False,
    )
    savings = models.Category(
        id="cat-savings",
        category_group_id="group-essentials",
        category_group_name="Essentials",
        name="Savings",
        hidden=False,
        original_category_group_id=None,
        note=None,
        budgeted=20000,
        activity=0,
        balance=90000,
        goal_type=None,
        goal_needs_whole_amount=None,
        goal_day=None,
        goal_cadence=1,
        goal_cadence_frequency=None,
        goal_creation_month=None,
        goal_target=60000,
        goal_target_month=None,
        goal_percentage_complete=None,
        goal_months_to_budget=None,
        goal_under_funded=None,
        goal_overall_funded=None,
        goal_overall_left=None,
        goal_snoozed_at=None,
        deleted=False,
    )
    return {category.id: category for category in (groceries, savings)}


def _make_transactions() -> list[models.TransactionDetail]:
    return [
        models.TransactionDetail(
            id="txn-1",
            date=dt.date(2024, 3, 12),
            amount=-12500,
            memo=None,
            cleared=TransactionClearedStatus.CLEARED,
            approved=True,
            flag_color=None,
            flag_name=None,
            account_id="acc-1",
            payee_id=None,
            category_id="cat-groceries",
            transfer_account_id=None,
            transfer_transaction_id=None,
            matched_transaction_id=None,
            import_id=None,
            import_payee_name=None,
            import_payee_name_original=None,
            debt_transaction_type=None,
            deleted=False,
            account_name="Checking",
            payee_name="Market",
            category_name="Groceries",
            subtransactions=[],
        ),
    ]


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
    categories: dict[str, models.Category],
    transactions: list[models.TransactionDetail],
) -> str:
    class FakeApiClient:
        def __init__(self, configuration: ynab.Configuration) -> None:
            self.configuration = configuration

        def __enter__(self) -> "FakeApiClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class FakeBudgetsApi:
        def __init__(self, api_client: FakeApiClient) -> None:
            self.api_client = api_client

        def get_budgets(self) -> models.BudgetSummaryResponse:
            budget = models.BudgetSummary(id="budget-123", name="Test Budget")
            data = models.BudgetSummaryResponseData(
                budgets=[budget], default_budget=None
            )
            return models.BudgetSummaryResponse(data=data)

    class FakeCategoriesApi:
        def __init__(self, api_client: FakeApiClient) -> None:
            self.api_client = api_client

        def get_categories(self, budget_id: str) -> models.CategoriesResponse:
            assert budget_id == "budget-123"
            group_essentials = models.CategoryGroupWithCategories(
                id="group-essentials",
                name="Essentials",
                hidden=False,
                deleted=False,
                categories=list(categories.values()),
            )
            data = models.CategoriesResponseData(
                category_groups=[group_essentials],
                server_knowledge=1,
            )
            return models.CategoriesResponse(data=data)

        def get_month_category_by_id(
            self,
            *,
            budget_id: str,
            month: dt.date,
            category_id: str,
        ) -> models.CategoryResponse:
            assert budget_id == "budget-123"
            assert month == dt.date(2024, 3, 10)
            data = models.CategoryResponseData(category=categories[category_id])
            return models.CategoryResponse(data=data)

    class FakeTransactionsApi:
        def __init__(self, api_client: FakeApiClient) -> None:
            self.api_client = api_client

        def get_transactions(
            self,
            *,
            budget_id: str,
            since_date: dt.date,
        ) -> models.TransactionsResponse:
            assert budget_id == "budget-123"
            assert since_date == dt.date(2024, 3, 10)
            data = models.TransactionsResponseData(
                transactions=transactions, server_knowledge=1
            )
            return models.TransactionsResponse(data=data)

    monkeypatch.setattr(cli, "load_config", lambda _: config)
    monkeypatch.setattr(ynab, "ApiClient", FakeApiClient)
    monkeypatch.setattr(ynab, "BudgetsApi", FakeBudgetsApi)
    monkeypatch.setattr(ynab, "CategoriesApi", FakeCategoriesApi)
    monkeypatch.setattr(ynab, "TransactionsApi", FakeTransactionsApi)

    cli.main()
    return capsys.readouterr().out


def test_category_group_totals_include_balance_without_spending(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    categories = _make_categories()
    transactions = _make_transactions()
    config = _make_config(output_format="csv_print", show_all_rows=False)

    captured = _run_main(monkeypatch, capsys, config, categories, transactions)
    report_text, totals_text = captured.split("category_group_totals\n", 1)
    report_text = report_text.split("\n", 1)[1]
    report_df = pl.read_csv(io.StringIO(report_text))
    totals_df = pl.read_csv(io.StringIO(totals_text))

    assert report_df.shape[0] == 1
    essentials = totals_df.filter(pl.col("category_group_name") == "Essentials")
    row = essentials.to_dicts()[0]
    assert row["budgeted"] == pytest.approx(70.0)
    assert row["spent"] == pytest.approx(-12.5)
    assert row["balance"] == pytest.approx(120.0)


def test_visual_report_totals_include_hidden_balance() -> None:
    report_table = pl.LazyFrame(
        [
            ("Groceries", "Essentials", 50.0, -10.0, 30.0, "monthly"),
            ("Savings", "Essentials", 20.0, 0.0, 90.0, "monthly"),
        ],
        orient="row",
        schema=(
            "category_name",
            "category_group_name",
            "budgeted",
            "spent",
            "balance",
            "goal_cadence",
        ),
    )
    html = build_visual_report_html(
        report_table,
        group_colors={"Essentials": "#dfe7f5"},
        week_label="Week 1",
        planned_year=2024,
        show_all_rows=False,
    )

    assert "Savings" not in html
    assert "Total Essentials" in html
    assert f"{Currency}840.00" in html
    assert f"{Currency}70.00" in html
    assert f"{Currency}10.00" in html
    assert f"{Currency}60.00" in html


def test_visual_report_hides_remaining_when_spent_blank() -> None:
    report_table = pl.LazyFrame(
        [
            ("Zero Spend", "Essentials", 50.0, 0.0, 50.0, "monthly"),
        ],
        orient="row",
        schema=(
            "category_name",
            "category_group_name",
            "budgeted",
            "spent",
            "balance",
            "goal_cadence",
        ),
    )
    html = build_visual_report_html(
        report_table,
        group_colors={"Essentials": "#dfe7f5"},
        week_label="Week 1",
        planned_year=2024,
        show_all_rows=True,
    )

    expected_row = "\n".join(
        [
            '      <tr class="group" style="background-color: #dfe7f5;">',
            "        <td>Zero Spend</td>",
            f'        <td class="number">{Currency}600.00</td>',
            f'        <td class="number">{Currency}50.00</td>',
            '        <td class="number"></td>',
            '        <td class="number"></td>',
            "      </tr>",
        ]
    )
    assert expected_row in html
