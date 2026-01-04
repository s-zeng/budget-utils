from __future__ import annotations

import calendar
import datetime as dt
from collections.abc import Iterable, Iterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class _MonthWeek:
    month: int
    week_start: dt.date
    week_end: dt.date
    week_number: int

    def __iter__(self) -> Iterator[dt.date]:
        days = (self.week_end - self.week_start).days
        return iter(
            tuple(
                self.week_start + dt.timedelta(days=offset)
                for offset in range(days + 1)
            )
        )


def _previous_sunday(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=(day.weekday() + 1) % 7)


def _week_days(week_start: dt.date) -> tuple[dt.date, ...]:
    return tuple(week_start + dt.timedelta(days=offset) for offset in range(7))


def _split_by_month(days: Iterable[dt.date]) -> list[int]:
    return sorted({day.month for day in days})


def _month_week(
    *,
    year: int,
    month: int,
    week_start: dt.date,
    week_end: dt.date,
    week_number: int,
) -> _MonthWeek:
    month_first = dt.date(year, month, 1)
    month_last = dt.date(year, month, calendar.monthrange(year, month)[1])
    return _MonthWeek(
        month=month,
        week_start=max(week_start, month_first),
        week_end=min(week_end, month_last),
        week_number=week_number,
    )


def partition_year_into_month_weeks(year: int) -> Iterator[_MonthWeek]:
    """Partition a calendar year into Sunday-Saturday weeks split at month edges.

    Weeks are anchored to Sunday-Saturday ranges, but any week that spans a month
    boundary is split into two MonthWeek entries. Each MonthWeek has a start and
    end clipped to its month.

    >>> import datetime as dt
    >>> from budget_utils.calendar_weeks import partition_year_into_month_weeks
    >>> weeks = list(partition_year_into_month_weeks(2024))
    >>> weeks[0].week_start
    datetime.date(2024, 1, 1)
    >>> weeks[0].week_end
    datetime.date(2024, 1, 6)
    >>> any(w.week_end == dt.date(2024, 1, 31) for w in weeks)
    True
    >>> any(w.week_start == dt.date(2024, 2, 1) for w in weeks)
    True
    """
    first_day = dt.date(year, 1, 1)
    last_day = dt.date(year, 12, 31)
    anchor_week_start = _previous_sunday(first_day)
    last_week_end = _previous_sunday(last_day) + dt.timedelta(days=6)

    weeks = (
        anchor_week_start + dt.timedelta(days=7 * offset)
        for offset in range(((last_week_end - anchor_week_start).days // 7) + 1)
    )
    for week_number, week_start in enumerate(weeks, start=1):
        week_end = week_start + dt.timedelta(days=6)
        in_year_days = [day for day in _week_days(week_start) if day.year == year]
        for month in _split_by_month(in_year_days):
            yield _month_week(
                year=year,
                month=month,
                week_start=week_start,
                week_end=week_end,
                week_number=week_number,
            )


def month_weeks(year: int, month: int) -> list[_MonthWeek]:
    """Filter a year's partition down to weeks for a specific month."""
    return [
        week for week in partition_year_into_month_weeks(year) if week.month == month
    ]


def month_week_for_date(day: dt.date) -> _MonthWeek:
    """Return the MonthWeek segment that contains the provided date."""
    week = next(
        (
            week
            for week in month_weeks(day.year, day.month)
            if week.week_start <= day <= week.week_end
        ),
        None,
    )
    if week is not None:
        return week
    msg = f"Date {day.isoformat()} not found in month weeks for {day.year}-{day.month:02d}"
    raise ValueError(msg)
