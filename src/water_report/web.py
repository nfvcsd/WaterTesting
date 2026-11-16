"""Entry point for the browser converter (runs under Pyodide on GitHub Pages).

The page's web worker writes the chosen XML file into Pyodide's in-memory
filesystem, calls :func:`convert`, then reads the workbook back out and hands
it to the browser as a download. Nothing leaves the user's computer.

Results are returned as JSON so the JavaScript side never has to unpack
Python objects or tracebacks.
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree.ElementTree import ParseError

from water_report.excel import build_workbook, report_filename
from water_report.parse import read_datalog
from water_report.summarize import summarize_by_day

NOT_A_DATALOG = (
    "This doesn't look like a CL17sc datalog. Choose the .xml file exported from the analyzer."
)


def convert(
    xml_path: str,
    source_name: str,
    output_path: str,
    min_chlorine: float | None = None,
) -> str:
    """Build a report from ``xml_path`` and save it to ``output_path``.

    Returns a JSON object: ``{"ok": true, "filename": ..., ...}`` on success,
    or ``{"ok": false, "error": "<message for the user>"}``.
    """
    try:
        datalog = read_datalog(Path(xml_path))
    except (ParseError, ValueError):
        return _failure(NOT_A_DATALOG)
    if not datalog.readings:
        return _failure("This datalog has no readings in it.")

    summaries = summarize_by_day(datalog.readings, min_chlorine=min_chlorine)
    build_workbook(datalog, summaries, source_name, min_chlorine).save(output_path)

    return json.dumps(
        {
            "ok": True,
            "filename": report_filename(datalog),
            "days": len(summaries),
            "readings": len(datalog.readings),
            "skipped": datalog.skipped_entries,
            "low_days": [
                summary.day.strftime("%m/%d/%Y")
                for summary in summaries
                if summary.chlorine_below_minimum
            ],
        }
    )


def _failure(message: str) -> str:
    return json.dumps({"ok": False, "error": message})
