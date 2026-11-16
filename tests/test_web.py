import json

from openpyxl import load_workbook

from tests.conftest import entry
from water_report.web import NOT_A_DATALOG, convert


def test_converts_sample_export(tmp_path, sample_datalog):
    output = tmp_path / "report.xlsx"

    result = json.loads(convert(str(sample_datalog), "sample.xml", str(output), 0.2))

    assert result["ok"] is True
    assert result["filename"] == "2023-12-28_to_2024-01-17.xlsx"
    assert result["days"] == 21
    assert result["readings"] == 11567
    assert "12/30/2023" in result["low_days"]
    assert load_workbook(output)["Daily Summary"].max_row == 22


def test_no_low_days_without_minimum(tmp_path, sample_datalog):
    result = json.loads(convert(str(sample_datalog), "s.xml", str(tmp_path / "r.xlsx")))

    assert result["low_days"] == []


def test_explains_wrong_file(tmp_path):
    not_xml = tmp_path / "photo.xml"
    not_xml.write_bytes(b"\x89PNG not xml")

    result = json.loads(convert(str(not_xml), "photo.xml", str(tmp_path / "r.xlsx")))

    assert result == {"ok": False, "error": NOT_A_DATALOG}


def test_explains_empty_datalog(tmp_path, write_datalog):
    path = write_datalog(entry("2023/12/28 10:15:00 AM"))  # no channel data

    result = json.loads(convert(str(path), "empty.xml", str(tmp_path / "r.xlsx")))

    assert result["ok"] is False
    assert "no readings" in result["error"]
