from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import pytest
import ynab
from ynab import models
from ynab.models.transaction_cleared_status import TransactionClearedStatus

from budget_utils import cli
from budget_utils.config import Config


def _read_golden(name: str) -> str:
    return (Path(__file__).with_name("golden") / name).read_text()


def _write_golden(name: str, content: str) -> None:
    (Path(__file__).with_name("golden") / name).write_text(content)


def _assert_golden(name: str, content: str) -> None:
    if os.getenv("UPDATE_GOLDENS") == "1":
        _write_golden(name, content)
        return
    assert content == _read_golden(name)


def _make_config(*, output_format: object | None = None) -> Config:
    payload: dict[str, object] = {
        "budgetName": "Test Budget",
        "personalAccessToken": "token",
        "categoryGroupWatchList": ["Essentials", "Fun"],
        "resolution_date": dt.date(2024, 3, 13),
        "showAllRows": False,
    }
    if output_format is not None:
        payload["outputFormat"] = output_format
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
        goal_target=None,
        goal_target_month=None,
        goal_percentage_complete=None,
        goal_months_to_budget=None,
        goal_under_funded=None,
        goal_overall_funded=None,
        goal_overall_left=None,
        goal_snoozed_at=None,
        deleted=False,
    )
    rent = models.Category(
        id="cat-rent",
        category_group_id="group-essentials",
        category_group_name="Essentials",
        name="Rent",
        hidden=False,
        original_category_group_id=None,
        note=None,
        budgeted=100000,
        activity=0,
        balance=100000,
        goal_type=None,
        goal_needs_whole_amount=None,
        goal_day=None,
        goal_cadence=12,
        goal_cadence_frequency=None,
        goal_creation_month=None,
        goal_target=None,
        goal_target_month=None,
        goal_percentage_complete=None,
        goal_months_to_budget=None,
        goal_under_funded=None,
        goal_overall_funded=None,
        goal_overall_left=None,
        goal_snoozed_at=None,
        deleted=False,
    )
    games = models.Category(
        id="cat-games",
        category_group_id="group-fun",
        category_group_name="Fun",
        name="Games",
        hidden=False,
        original_category_group_id=None,
        note=None,
        budgeted=20000,
        activity=0,
        balance=15000,
        goal_type=None,
        goal_needs_whole_amount=None,
        goal_day=None,
        goal_cadence=1,
        goal_cadence_frequency=None,
        goal_creation_month=None,
        goal_target=None,
        goal_target_month=None,
        goal_percentage_complete=None,
        goal_months_to_budget=None,
        goal_under_funded=None,
        goal_overall_funded=None,
        goal_overall_left=None,
        goal_snoozed_at=None,
        deleted=False,
    )
    return {category.id: category for category in (groceries, rent, games)}


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
        models.TransactionDetail(
            id="txn-2",
            date=dt.date(2024, 3, 15),
            amount=-3000,
            memo=None,
            cleared=TransactionClearedStatus.CLEARED,
            approved=True,
            flag_color=None,
            flag_name=None,
            account_id="acc-1",
            payee_id=None,
            category_id="cat-games",
            transfer_account_id=None,
            transfer_transaction_id=None,
            matched_transaction_id=None,
            import_id=None,
            import_payee_name=None,
            import_payee_name_original=None,
            debt_transaction_type=None,
            deleted=False,
            account_name="Checking",
            payee_name="Arcade",
            category_name="Games",
            subtransactions=[],
        ),
    ]


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
) -> str:
    categories = _make_categories()
    transactions = _make_transactions()

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
            data = models.BudgetSummaryResponseData(budgets=[budget], default_budget=None)
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
                categories=[categories["cat-groceries"], categories["cat-rent"]],
            )
            group_fun = models.CategoryGroupWithCategories(
                id="group-fun",
                name="Fun",
                hidden=False,
                deleted=False,
                categories=[categories["cat-games"]],
            )
            data = models.CategoriesResponseData(
                category_groups=[group_essentials, group_fun],
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
            data = models.TransactionsResponseData(transactions=transactions, server_knowledge=1)
            return models.TransactionsResponse(data=data)

    monkeypatch.setattr(cli, "load_config", lambda _: config)
    monkeypatch.setattr(ynab, "ApiClient", FakeApiClient)
    monkeypatch.setattr(ynab, "BudgetsApi", FakeBudgetsApi)
    monkeypatch.setattr(ynab, "CategoriesApi", FakeCategoriesApi)
    monkeypatch.setattr(ynab, "TransactionsApi", FakeTransactionsApi)

    cli.main()
    return capsys.readouterr().out


def test_main_golden_output(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    config = _make_config(output_format="polars_print")
    captured = _run_main(monkeypatch, capsys, config)
    _assert_golden("main_output.txt", captured)


def test_main_golden_output_csv_print(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _make_config(output_format="csv_print")
    captured = _run_main(monkeypatch, capsys, config)
    _assert_golden("main_output_csv_print.txt", captured)


def test_main_golden_output_csv_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "report.csv"
    totals_path = tmp_path / "report_category_group_totals.csv"
    config = _make_config(output_format={"csv_output": str(output_path)})
    captured = _run_main(monkeypatch, capsys, config)
    _assert_golden("main_output_csv_output.txt", captured)
    _assert_golden("main_output_csv.txt", output_path.read_text())
    _assert_golden("main_output_csv_totals.txt", totals_path.read_text())
