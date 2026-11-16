"""Write daily summaries to an Excel workbook with charts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.chart.text import RichText
from openpyxl.drawing.text import (
    CharacterProperties,
    Paragraph,
    ParagraphProperties,
    RichTextProperties,
)
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from water_report import __version__
from water_report.parse import Datalog
from water_report.summarize import DailySummary, Stats

SUMMARY_SHEET = "Daily Summary"
ABOUT_SHEET = "About"

DATE_FORMAT = "mm/dd/yyyy"
CHLORINE_FORMAT = "0.00"
FLOW_FORMAT = "0"

# Series colors: a validated, colorblind-safe pair. The second series is also
# dashed so the lines never depend on color alone.
SERIES_COLORS = ("2A78D6", "EB6834")
LINE_WIDTH_EMU = 22225  # 1.75 pt
DATE_LABEL_ROTATION = -2_700_000  # -45 degrees, in 60,000ths of a degree
BELOW_MINIMUM_FILL = PatternFill("solid", fgColor="F8D7DA")
HEADER_FONT = Font(bold=True)


@dataclass(frozen=True)
class Column:
    header: str
    number_format: str
    width: int


COLUMNS = (
    Column("Date", DATE_FORMAT, 12),
    Column("Samples", "0", 9),
    Column("Free Cl2 Mean (mg/L)", CHLORINE_FORMAT, 12),
    Column("Free Cl2 Min (mg/L)", CHLORINE_FORMAT, 12),
    Column("Free Cl2 Max (mg/L)", CHLORINE_FORMAT, 12),
    Column("Flow Mean", FLOW_FORMAT, 10),
    Column("Flow Min", FLOW_FORMAT, 10),
    Column("Flow Max", FLOW_FORMAT, 10),
)
BELOW_MINIMUM_COLUMN = Column("Cl2 Readings Below Minimum", "0", 14)

# 1-based column positions used by the charts and highlighting.
DATE_COL = 1
CHLORINE_MEAN_COL = 3
CHLORINE_MIN_COL = 4
FLOW_MEAN_COL = 6


def build_workbook(
    datalog: Datalog,
    summaries: list[DailySummary],
    source_name: str,
    min_chlorine: float | None = None,
) -> Workbook:
    """Create the report workbook: a daily summary sheet with charts, plus an About sheet."""
    if not summaries:
        raise ValueError("No readings to report")

    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = SUMMARY_SHEET

    _write_summary_table(summary_sheet, summaries, min_chlorine)
    _add_charts(summary_sheet, last_row=len(summaries) + 1)
    _write_about_sheet(
        workbook.create_sheet(ABOUT_SHEET), datalog, summaries, source_name, min_chlorine
    )
    return workbook


def _write_summary_table(
    sheet: Worksheet,
    summaries: list[DailySummary],
    min_chlorine: float | None,
) -> None:
    columns = COLUMNS + ((BELOW_MINIMUM_COLUMN,) if min_chlorine is not None else ())

    sheet.append([column.header for column in columns])
    for summary in summaries:
        row = [
            summary.day,
            summary.samples,
            *_stats_cells(summary.free_chlorine),
            *_stats_cells(summary.flow),
        ]
        if min_chlorine is not None:
            row.append(summary.chlorine_below_minimum)
        sheet.append(row)

    for index, column in enumerate(columns, start=1):
        letter = get_column_letter(index)
        sheet.column_dimensions[letter].width = column.width
        header = sheet.cell(row=1, column=index)
        header.font = HEADER_FONT
        header.alignment = Alignment(wrap_text=True, vertical="top")
        for (cell,) in sheet.iter_rows(min_row=2, min_col=index, max_col=index):
            cell.number_format = column.number_format

    sheet.freeze_panes = "B2"

    if min_chlorine is not None:
        _highlight_low_chlorine(sheet, min_chlorine)


def _stats_cells(stats: Stats | None) -> tuple[float | None, float | None, float | None]:
    if stats is None:
        return (None, None, None)
    return (stats.mean, stats.minimum, stats.maximum)


def _highlight_low_chlorine(sheet: Worksheet, min_chlorine: float) -> None:
    """Shade chlorine mean/min cells under the minimum (also counted in its own column)."""
    for row in sheet.iter_rows(min_row=2, min_col=CHLORINE_MEAN_COL, max_col=CHLORINE_MIN_COL):
        for cell in row:
            if cell.value is not None and cell.value < min_chlorine:
                cell.fill = BELOW_MINIMUM_FILL


@dataclass(frozen=True)
class ChartSpec:
    title: str
    y_title: str
    first_col: int
    last_col: int
    number_format: str
    anchor_row: int


# One chart per measure, so each keeps its own honest y-axis.
CHARTS = (
    ChartSpec(
        title="Free Chlorine (daily mean and minimum)",
        y_title="mg/L",
        first_col=CHLORINE_MEAN_COL,
        last_col=CHLORINE_MIN_COL,
        number_format=CHLORINE_FORMAT,
        anchor_row=2,
    ),
    ChartSpec(
        title="Flow Rate (daily mean)",
        y_title="Flow",
        first_col=FLOW_MEAN_COL,
        last_col=FLOW_MEAN_COL,
        number_format=FLOW_FORMAT,
        anchor_row=20,
    ),
)


def _add_charts(sheet: Worksheet, last_row: int) -> None:
    anchor_col = get_column_letter(len(COLUMNS) + 3)
    for spec in CHARTS:
        sheet.add_chart(_line_chart(sheet, spec, last_row), f"{anchor_col}{spec.anchor_row}")


def _line_chart(sheet: Worksheet, spec: ChartSpec, last_row: int) -> LineChart:
    chart = LineChart()
    chart.title = spec.title
    chart.width = 20
    chart.height = 8.5
    chart.y_axis.title = spec.y_title
    chart.y_axis.number_format = spec.number_format
    chart.x_axis.number_format = "mm/dd"
    chart.x_axis.txPr = _rotated_text(DATE_LABEL_ROTATION)
    # openpyxl 3.1 hides axes unless told otherwise.
    chart.x_axis.delete = False
    chart.y_axis.delete = False

    data = Reference(
        sheet, min_col=spec.first_col, max_col=spec.last_col, min_row=1, max_row=last_row
    )
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(Reference(sheet, min_col=DATE_COL, min_row=2, max_row=last_row))

    if len(chart.series) == 1:
        chart.legend = None  # the title already names the single series
    else:
        chart.legend.position = "b"

    for index, series in enumerate(chart.series):
        line = series.graphicalProperties.line
        line.solidFill = SERIES_COLORS[index]
        line.width = LINE_WIDTH_EMU
        if index > 0:
            line.dashStyle = "dash"
        series.marker.symbol = "circle"
        series.marker.size = 5
        series.marker.graphicalProperties.solidFill = SERIES_COLORS[index]
        series.marker.graphicalProperties.line.solidFill = SERIES_COLORS[index]
        series.smooth = False
    return chart


def _rotated_text(rotation: int) -> RichText:
    """Axis label text turned by ``rotation`` so dates don't overlap."""
    return RichText(
        bodyPr=RichTextProperties(rot=rotation, vert="horz"),
        p=[
            Paragraph(
                pPr=ParagraphProperties(defRPr=CharacterProperties()),
                endParaRPr=CharacterProperties(),
            )
        ],
    )


def _write_about_sheet(
    sheet: Worksheet,
    datalog: Datalog,
    summaries: list[DailySummary],
    source_name: str,
    min_chlorine: float | None,
) -> None:
    info = datalog.device_info
    first, last = datalog.readings[0].timestamp, datalog.readings[-1].timestamp
    rows = [
        ("Source file", source_name),
        ("Device", info.get("Device Name", "")),
        ("Location", info.get("Device Location", "")),
        ("Serial number", info.get("Serial Number", "")),
        ("First reading", first),
        ("Last reading", last),
        ("Days", len(summaries)),
        ("Readings", len(datalog.readings)),
        ("Skipped entries", datalog.skipped_entries),
        ("Minimum free Cl2 (mg/L)", "not set" if min_chlorine is None else min_chlorine),
        ("Generated", datetime.now().replace(microsecond=0)),
        ("Generator", f"water-report {__version__}"),
        (
            "Note",
            "The first and last days are usually partial; compare their Samples "
            "count with the other days.",
        ),
    ]
    for row in rows:
        sheet.append(row)
    for (label,) in sheet.iter_rows(min_col=1, max_col=1):
        label.font = HEADER_FONT
        label.alignment = Alignment(vertical="top")
    for (value,) in sheet.iter_rows(min_col=2, max_col=2):
        value.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        if isinstance(value.value, datetime):
            value.number_format = "mm/dd/yyyy h:mm AM/PM"
    sheet.column_dimensions["A"].width = 24
    sheet.column_dimensions["B"].width = 60
