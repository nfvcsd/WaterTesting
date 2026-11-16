import logging

from openpyxl import load_workbook

from water_report.cli import main

EXPECTED_NAME = "2023-12-28_to_2024-01-17.xlsx"


def test_writes_report_named_by_date_range(tmp_path, sample_datalog):
    assert main([str(sample_datalog), "--output-dir", str(tmp_path)]) == 0

    report = load_workbook(tmp_path / EXPECTED_NAME)
    assert report["Daily Summary"].max_row == 22  # header + 21 days


def test_will_not_overwrite_without_force(tmp_path, sample_datalog):
    output = tmp_path / "report.xlsx"
    output.write_text("keep me")

    assert main([str(sample_datalog), "-o", str(output)]) == 1
    assert output.read_text() == "keep me"

    assert main([str(sample_datalog), "-o", str(output), "--force"]) == 0
    assert load_workbook(output)["Daily Summary"]["A1"].value == "Date"


def test_warns_about_low_chlorine_days(tmp_path, sample_datalog, caplog):
    with caplog.at_level(logging.WARNING):
        main([str(sample_datalog), "-d", str(tmp_path), "--min-chlorine", "0.2"])

    assert "fell below 0.20 mg/L" in caplog.text


def test_reports_unreadable_file(tmp_path, caplog):
    bad = tmp_path / "bad.xml"
    bad.write_text("not xml")

    assert main([str(bad), "-d", str(tmp_path)]) == 1
    assert "Could not read" in caplog.text
