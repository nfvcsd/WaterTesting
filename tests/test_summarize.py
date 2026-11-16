from datetime import date, datetime

import pytest

from water_report.parse import Reading
from water_report.summarize import summarize_by_day


def reading(timestamp: str, chlorine: float | None, flow: float | None) -> Reading:
    return Reading(datetime.fromisoformat(timestamp), chlorine, flow)


READINGS = [
    reading("2024-01-02 08:00", 0.40, 180),
    reading("2024-01-01 23:59", 0.20, 200),
    reading("2024-01-01 00:00", 0.60, 190),
    reading("2024-01-01 12:00", None, 210),
]


def test_groups_by_calendar_day_oldest_first():
    summaries = summarize_by_day(READINGS)

    assert [s.day for s in summaries] == [date(2024, 1, 1), date(2024, 1, 2)]
    assert [s.samples for s in summaries] == [3, 1]


def test_daily_stats_ignore_missing_values():
    first_day = summarize_by_day(READINGS)[0]

    assert first_day.free_chlorine.mean == pytest.approx(0.40)
    assert first_day.free_chlorine.minimum == pytest.approx(0.20)
    assert first_day.free_chlorine.maximum == pytest.approx(0.60)
    assert first_day.flow.mean == pytest.approx(200)


def test_day_without_chlorine_has_no_chlorine_stats():
    summaries = summarize_by_day([reading("2024-01-01 00:00", None, 190)])

    assert summaries[0].free_chlorine is None
    assert summaries[0].flow.mean == pytest.approx(190)


def test_counts_readings_below_minimum_only_when_requested():
    without_minimum = summarize_by_day(READINGS)
    with_minimum = summarize_by_day(READINGS, min_chlorine=0.3)

    assert without_minimum[0].chlorine_below_minimum is None
    assert [s.chlorine_below_minimum for s in with_minimum] == [1, 0]
