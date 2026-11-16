"""Shared fixtures for building small datalog files."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

SAMPLE_DATALOG = Path(__file__).parent / "fixtures" / "cl17sc_sample.xml"

HEADER_ENTRY = """
  <Entry>
    <Time>  TIME  </Time>
    <CH1><Data>  FREE CL2  </Data></CH1>
    <CH2><Data>  FLOW RATE AVG  </Data></CH2>
  </Entry>"""


def entry(time: str, chlorine: str | None = None, flow: str | None = None) -> str:
    """One <Entry> element; pass None to leave a channel out."""
    channels = ""
    if chlorine is not None:
        channels += f"<CH1><Data>  {chlorine}  </Data></CH1>"
    if flow is not None:
        channels += f"<CH2><Data>  {flow}  </Data></CH2>"
    return f"<Entry><Time>  {time}  </Time>{channels}</Entry>"


@pytest.fixture
def sample_datalog() -> Path:
    return SAMPLE_DATALOG


@pytest.fixture
def write_datalog(tmp_path: Path) -> Callable[..., Path]:
    """Write a datalog with the standard header row followed by ``entries``."""

    def _write(*entries: str, header: str = HEADER_ENTRY) -> Path:
        path = tmp_path / "datalog.xml"
        path.write_text(
            '<?xml version="1.0" encoding="ISO-8859-1" ?>\n'
            "<Datalog>\n"
            "  <DeviceInfo>Device Name: CL17sc  </DeviceInfo>\n"
            "  <DeviceInfo>Device Location: TEST SITE  </DeviceInfo>\n"
            f"{header}\n" + "\n".join(entries) + "\n</Datalog>\n",
            encoding="latin-1",
        )
        return path

    return _write
