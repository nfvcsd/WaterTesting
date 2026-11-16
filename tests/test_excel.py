from datetime import datetime

import pytest
from openpyxl import load_workbook

from tests.conftest import entry
from water_report.excel import ABOUT_SHEET, BELOW_MINIMUM_FILL, SUMMARY_SHEET, build_workbook
from water_report.parse import read_datalog
from water_report.summarize import summarize_by_day


@pytest.fixture
def three_day_datalog(write_datalog):
    return read_datalog(
        write_datalog(
            entry("2024/01/01 10:00:00 AM", "0.50", "190"),
            entry("2024/01/01 10:02:30 AM", "0.70", "210"),
            entry("2024/01/02 10:00:00 AM", "0.10", "200"),
            entry("2024/01/03 10:00:00 AM", "0.40", "205"),
        )
    )


def save_and_reload(tmp_path, datalog, min_chlorine=None):
    summaries = summarize_by_day(datalog.readings, min_chlorine=min_chlorine)
    path = tmp_path / "report.xlsx"
    build_workbook(datalog, summaries, "datalog.xml", min_chlorine).save(path)
    return load_workbook(path)


def test_summary_table_starts_right_under_header(tmp_path, three_day_datalog):
    sheet = save_and_reload(tmp_path, three_day_datalog)[SUMMARY_SHEET]

    assert sheet["A1"].value == "Date"
    assert sheet.max_row == 4  # header + 3 days, no blank row
    assert sheet["A2"].value == datetime(2024, 1, 1)  # a real date, not text
    assert sheet["B2"].value == 2
    assert sheet["C2"].value == pytest.approx(0.60)
    assert sheet["F2"].value == pytest.approx(200)


def test_one_chart_per_measure_covering_every_day(tmp_path, three_day_datalog):
    workbook = build_workbook(
        three_day_datalog, summarize_by_day(three_day_datalog.readings), "datalog.xml"
    )
    chlorine_chart, flow_chart = workbook[SUMMARY_SHEET]._charts

    chlorine_refs = [s.val.numRef.f for s in chlorine_chart.series]
    assert chlorine_refs == ["'Daily Summary'!$C$2:$C$4", "'Daily Summary'!$D$2:$D$4"]
    assert [s.val.numRef.f for s in flow_chart.series] == ["'Daily Summary'!$F$2:$F$4"]
    for chart in (chlorine_chart, flow_chart):
        assert chart.series[0].cat.numRef.f == "'Daily Summary'!$A$2:$A$4"


def test_titles_and_legend_do_not_overlay_the_plot(three_day_datalog):
    """Excel draws these over the plot area unless overlay is explicitly off."""
    workbook = build_workbook(
        three_day_datalog, summarize_by_day(three_day_datalog.readings), "datalog.xml"
    )
    for chart in workbook[SUMMARY_SHEET]._charts:
        assert chart.title.overlay is False
        assert chart.y_axis.title.overlay is False
        assert chart.legend is None or chart.legend.overlay is False


def test_low_chlorine_is_highlighted_and_counted(tmp_path, three_day_datalog):
    sheet = save_and_reload(tmp_path, three_day_datalog, min_chlorine=0.3)[SUMMARY_SHEET]

    assert sheet["I1"].value == "Cl2 Readings Below Minimum"
    assert [sheet[f"I{row}"].value for row in range(2, 5)] == [0, 1, 0]
    assert sheet["D3"].fill.fgColor.rgb.endswith(BELOW_MINIMUM_FILL.fgColor.rgb[-6:])
    assert sheet["D2"].fill.fill_type is None


def test_no_minimum_column_unless_requested(tmp_path, three_day_datalog):
    sheet = save_and_reload(tmp_path, three_day_datalog)[SUMMARY_SHEET]

    assert sheet["I1"].value is None


def test_about_sheet_records_source(tmp_path, three_day_datalog):
    about = save_and_reload(tmp_path, three_day_datalog)[ABOUT_SHEET]
    values = {row[0]: row[1] for row in about.iter_rows(values_only=True)}

    assert values["Source file"] == "datalog.xml"
    assert values["Location"] == "TEST SITE"
    assert values["Readings"] == 4
    assert values["Days"] == 3


def test_refuses_empty_report(three_day_datalog):
    with pytest.raises(ValueError, match="No readings"):
        build_workbook(three_day_datalog, [], "datalog.xml")
