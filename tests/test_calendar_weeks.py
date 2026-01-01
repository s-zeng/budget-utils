import calendar
import datetime as dt

from hypothesis import given, strategies as st

from budget_utils import calendar_weeks


def _year_dates(year: int) -> set[dt.date]:
    start = dt.date(year, 1, 1)
    end = dt.date(year + 1, 1, 1)
    return {start + dt.timedelta(days=offset) for offset in range((end - start).days)}


def _month_dates(year: int, month: int) -> set[dt.date]:
    last_day = calendar.monthrange(year, month)[1]
    return {dt.date(year, month, day) for day in range(1, last_day + 1)}


@given(st.integers(min_value=1900, max_value=2100))
def test_partition_covers_year(year: int) -> None:
    weeks = calendar_weeks.partition_year_into_month_weeks(year)
    days = [day for week in weeks for day in week]
    assert len(days) == len(set(days))
    assert set(days) == _year_dates(year)


@given(st.integers(min_value=1900, max_value=2100), st.integers(min_value=1, max_value=12))
def test_month_partition_covers_month(year: int, month: int) -> None:
    weeks = calendar_weeks.month_weeks(year, month)
    days = [day for week in weeks for day in week]
    assert len(days) == len(set(days))
    assert set(days) == _month_dates(year, month)


@given(st.integers(min_value=1900, max_value=2100), st.integers(min_value=1, max_value=12))
def test_week_invariants(year: int, month: int) -> None:
    weeks = calendar_weeks.month_weeks(year, month)
    month_last = calendar.monthrange(year, month)[1]
    for week in weeks:
        days = tuple(week)
        is_start_sunday = week.week_start.weekday() == 6
        is_end_saturday = week.week_end.weekday() == 5
        assert is_start_sunday or week.week_start.day == 1
        assert is_end_saturday or week.week_end.day == month_last
        assert not ((not is_start_sunday) and (not is_end_saturday))
        assert days
        assert all(day.year == year for day in days)
        assert all(day.month == month for day in days)
        assert days[-1] - days[0] == dt.timedelta(days=len(days) - 1)


@given(st.dates(min_value=dt.date(1900, 1, 1), max_value=dt.date(2100, 12, 31)))
def test_month_week_for_date_contains_date(day: dt.date) -> None:
    week = calendar_weeks.month_week_for_date(day)
    assert week.month == day.month
    assert week.week_start <= day <= week.week_end
    assert week in calendar_weeks.month_weeks(day.year, day.month)
