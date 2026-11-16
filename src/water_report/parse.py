"""Read Hach CL17sc datalog XML exports.

An export looks like this (whitespace trimmed)::

    <Datalog>
      <DeviceInfo>Device Location: VALLEY SCHOOL</DeviceInfo>
      <Entry>                                  <- header row
        <Time>TIME</Time>
        <CH1><Data>FREE CL2</Data></CH1>
        <CH2><Data>FLOW RATE AVG</Data></CH2>
      </Entry>
      <Entry>                                  <- one reading
        <Time>2023/12/28 10:17:30 AM</Time>
        <CH1><Data>0.130000</Data></CH1>
        <CH2><Data>198</Data></CH2>
      </Entry>
    </Datalog>

Quirks seen in real exports and handled here:

* Timestamps switch between several formats within one file.
* A reading can be missing a channel (often the very first one).
* A reading can repeat its channel blocks; the first value wins.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from xml.etree.ElementTree import Element

from defusedxml import ElementTree

log = logging.getLogger(__name__)

CHLORINE_CHANNEL = "CH1"
FLOW_CHANNEL = "CH2"

# Labels the analyzer writes in the header row. If these ever change, the
# channels may have been reconfigured and the report would mislabel data.
EXPECTED_HEADER_LABELS = {
    CHLORINE_CHANNEL: "FREE CL2",
    FLOW_CHANNEL: "FLOW RATE AVG",
}

HEADER_TIME_LABEL = "TIME"

# Formats the analyzer has written over the years. 12-hour formats use %I so
# that AM/PM is honored (%H silently ignores %p).
TIMESTAMP_FORMATS = (
    "%Y/%m/%d %I:%M:%S %p",
    "%m/%d/%Y %I:%M:%S %p",
    "%Y/%m/%d %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
)


@dataclass(frozen=True)
class Reading:
    """One logged sample. A channel is None when the analyzer didn't record it."""

    timestamp: datetime
    free_chlorine: float | None  # mg/L
    flow: float | None


@dataclass
class Datalog:
    """Everything read from one export file."""

    device_info: dict[str, str] = field(default_factory=dict)
    readings: list[Reading] = field(default_factory=list)
    skipped_entries: int = 0


def parse_timestamp(text: str) -> datetime:
    """Parse a datalog timestamp in any of the known formats."""
    cleaned = text.strip()
    for fmt in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized timestamp format: {cleaned!r}")


def read_datalog(path: Path) -> Datalog:
    """Read a CL17sc XML export into a Datalog."""
    root = ElementTree.parse(path).getroot()
    if root.tag != "Datalog":
        raise ValueError(f"{path} is not a Hach datalog (root element is <{root.tag}>)")

    datalog = Datalog(device_info=_read_device_info(root))

    for entry in root.iterfind("Entry"):
        time_text = _text(entry.find("Time"))
        if time_text == HEADER_TIME_LABEL:
            _check_header(entry)
            continue

        reading = _read_entry(entry, time_text)
        if reading is None:
            datalog.skipped_entries += 1
        else:
            datalog.readings.append(reading)

    if datalog.skipped_entries:
        log.warning("Skipped %d unreadable entries in %s", datalog.skipped_entries, path)
    return datalog


def _read_device_info(root: Element) -> dict[str, str]:
    """Turn '<DeviceInfo>Key: Value</DeviceInfo>' lines into a dict."""
    info = {}
    for element in root.iterfind("DeviceInfo"):
        key, _, value = _text(element).partition(":")
        info[key.strip()] = value.strip()
    return info


def _check_header(entry: Element) -> None:
    """Fail loudly if the analyzer's channels no longer match what we expect."""
    for channel, expected in EXPECTED_HEADER_LABELS.items():
        actual = _channel_text(entry, channel)
        if actual is not None and actual != expected:
            raise ValueError(
                f"Channel {channel} is labeled {actual!r}, expected {expected!r}. "
                "The analyzer may have been reconfigured; update EXPECTED_HEADER_LABELS."
            )


def _read_entry(entry: Element, time_text: str) -> Reading | None:
    """Convert one <Entry> to a Reading, or None if it can't be used."""
    try:
        timestamp = parse_timestamp(time_text)
        free_chlorine = _channel_value(entry, CHLORINE_CHANNEL)
        flow = _channel_value(entry, FLOW_CHANNEL)
    except ValueError as error:
        log.debug("Skipping entry: %s", error)
        return None

    if free_chlorine is None and flow is None:
        return None
    return Reading(timestamp=timestamp, free_chlorine=free_chlorine, flow=flow)


def _channel_value(entry: Element, channel: str) -> float | None:
    text = _channel_text(entry, channel)
    return None if text is None else float(text)


def _channel_text(entry: Element, channel: str) -> str | None:
    """Text of the first <CHn><Data> block, or None if the channel is absent."""
    data = entry.find(f"{channel}/Data")
    return None if data is None else _text(data)


def _text(element: Element | None) -> str:
    return "" if element is None or element.text is None else element.text.strip()
