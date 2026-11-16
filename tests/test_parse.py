from datetime import datetime

import pytest
from defusedxml import EntitiesForbidden

from tests.conftest import entry
from water_report.parse import parse_timestamp, read_datalog


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2023/12/28 10:15:00 AM", datetime(2023, 12, 28, 10, 15)),
        ("2024/01/17 12:10:00 PM", datetime(2024, 1, 17, 12, 10)),
        ("2024/01/17 12:05:00 AM", datetime(2024, 1, 17, 0, 5)),
        # The old script read this as 01:00 because %H ignores AM/PM.
        ("2024/01/17 01:00:00 PM", datetime(2024, 1, 17, 13, 0)),
        ("01/04/2024 23:27:30", datetime(2024, 1, 4, 23, 27, 30)),
        ("01/04/2024 11:27:30 PM", datetime(2024, 1, 4, 23, 27, 30)),
        ("2024/01/04 23:27:30", datetime(2024, 1, 4, 23, 27, 30)),
        ("  2024/01/04 23:27:30  ", datetime(2024, 1, 4, 23, 27, 30)),
    ],
)
def test_parse_timestamp_formats(text, expected):
    assert parse_timestamp(text) == expected


def test_parse_timestamp_rejects_unknown_format():
    with pytest.raises(ValueError, match="Unrecognized timestamp"):
        parse_timestamp("28 Dec 2023 10:15")


def test_reads_device_info_and_readings(write_datalog):
    path = write_datalog(entry("2023/12/28 10:17:30 AM", "0.130000", "198"))

    datalog = read_datalog(path)

    assert datalog.device_info["Device Location"] == "TEST SITE"
    assert len(datalog.readings) == 1
    reading = datalog.readings[0]
    assert reading.timestamp == datetime(2023, 12, 28, 10, 17, 30)
    assert reading.free_chlorine == pytest.approx(0.13)
    assert reading.flow == pytest.approx(198)


def test_keeps_reading_with_one_missing_channel(write_datalog):
    path = write_datalog(entry("2023/12/28 10:15:00 AM", chlorine=None, flow="198"))

    reading = read_datalog(path).readings[0]

    assert reading.free_chlorine is None
    assert reading.flow == pytest.approx(198)


def test_duplicate_channel_blocks_use_first_value(write_datalog):
    duplicated = (
        "<Entry><Time>2024/01/03 06:50:00 AM</Time>"
        "<CH1><Data>0.30</Data></CH1><CH2><Data>199</Data></CH2>"
        "<CH1><Data>9.99</Data></CH1><CH2><Data>999</Data></CH2></Entry>"
    )
    reading = read_datalog(write_datalog(duplicated)).readings[0]

    assert reading.free_chlorine == pytest.approx(0.30)
    assert reading.flow == pytest.approx(199)


def test_skips_and_counts_unreadable_entries(write_datalog):
    path = write_datalog(
        entry("2023/12/28 10:15:00 AM", "0.12", "198"),
        entry("not a time", "0.12", "198"),
        entry("2023/12/28 10:20:00 AM", "----", "198"),
        entry("2023/12/28 10:22:30 AM"),
    )

    datalog = read_datalog(path)

    assert len(datalog.readings) == 1
    assert datalog.skipped_entries == 3


def test_rejects_reconfigured_channels(write_datalog):
    header = (
        "<Entry><Time>TIME</Time><CH1><Data>TOTAL CL2</Data></CH1>"
        "<CH2><Data>FLOW RATE AVG</Data></CH2></Entry>"
    )
    with pytest.raises(ValueError, match="reconfigured"):
        read_datalog(write_datalog(header=header))


def test_rejects_non_datalog_xml(tmp_path):
    path = tmp_path / "other.xml"
    path.write_text("<Something/>")

    with pytest.raises(ValueError, match="not a Hach datalog"):
        read_datalog(path)


def test_refuses_xml_entities(tmp_path):
    """defusedxml blocks entity tricks (billion laughs, external entities)."""
    path = tmp_path / "evil.xml"
    path.write_text('<!DOCTYPE d [<!ENTITY x "boom">]><Datalog>&x;</Datalog>')

    with pytest.raises(EntitiesForbidden):
        read_datalog(path)


def test_sample_export(sample_datalog):
    datalog = read_datalog(sample_datalog)

    assert datalog.device_info["Device Name"] == "CL17sc"
    assert len(datalog.readings) == 11567
    assert datalog.skipped_entries == 0
    assert datalog.readings[0].timestamp == datetime(2023, 12, 28, 10, 15)
    assert datalog.readings[0].free_chlorine is None
    assert datalog.readings[-1].timestamp == datetime(2024, 1, 17, 12, 10)
