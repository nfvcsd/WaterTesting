"""Roll individual readings up into one summary per day."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from statistics import fmean

from water_report.parse import Reading


@dataclass(frozen=True)
class Stats:
    mean: float
    minimum: float
    maximum: float

    @classmethod
    def of(cls, values: list[float]) -> Stats | None:
        """Stats for the values, or None when there are none."""
        if not values:
            return None
        return cls(mean=fmean(values), minimum=min(values), maximum=max(values))


@dataclass(frozen=True)
class DailySummary:
    day: date
    samples: int
    free_chlorine: Stats | None
    flow: Stats | None
    chlorine_below_minimum: int | None  # None when no minimum was given


def summarize_by_day(
    readings: Iterable[Reading],
    min_chlorine: float | None = None,
) -> list[DailySummary]:
    """Group readings by calendar day, oldest first.

    If ``min_chlorine`` is given, also count readings below it each day.
    """
    by_day: dict[date, list[Reading]] = defaultdict(list)
    for reading in readings:
        by_day[reading.timestamp.date()].append(reading)

    return [_summarize_day(day, by_day[day], min_chlorine) for day in sorted(by_day)]


def _summarize_day(
    day: date,
    readings: list[Reading],
    min_chlorine: float | None,
) -> DailySummary:
    chlorine = [r.free_chlorine for r in readings if r.free_chlorine is not None]
    flow = [r.flow for r in readings if r.flow is not None]

    below_minimum = None
    if min_chlorine is not None:
        below_minimum = sum(value < min_chlorine for value in chlorine)

    return DailySummary(
        day=day,
        samples=len(readings),
        free_chlorine=Stats.of(chlorine),
        flow=Stats.of(flow),
        chlorine_below_minimum=below_minimum,
    )
