"""Command-line entry point: ``water-report LOG.xml``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from xml.etree.ElementTree import ParseError

from water_report.excel import build_workbook, report_filename
from water_report.parse import read_datalog
from water_report.summarize import summarize_by_day

log = logging.getLogger("water_report")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    try:
        datalog = read_datalog(args.datalog)
    except (OSError, ParseError, ValueError) as error:
        log.error("Could not read %s: %s", args.datalog, error)
        return 1
    if not datalog.readings:
        log.error("No readings found in %s", args.datalog)
        return 1

    output = args.output or args.output_dir / report_filename(datalog)
    if output.exists() and not args.force:
        log.error("%s already exists; use --force to overwrite it", output)
        return 1

    summaries = summarize_by_day(datalog.readings, min_chlorine=args.min_chlorine)
    workbook = build_workbook(datalog, summaries, args.datalog.name, args.min_chlorine)
    output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output)

    log.info("Wrote %s (%d days, %d readings)", output, len(summaries), len(datalog.readings))
    if args.min_chlorine is not None:
        low_days = [s.day for s in summaries if s.chlorine_below_minimum]
        if low_days:
            log.warning(
                "Free chlorine fell below %.2f mg/L on %d day(s): %s",
                args.min_chlorine,
                len(low_days),
                ", ".join(day.strftime("%m/%d/%Y") for day in low_days),
            )
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="water-report",
        description="Summarize a Hach CL17sc datalog export into a daily Excel report.",
    )
    parser.add_argument(
        "datalog", type=_existing_file, help="datalog .xml exported from the CL17sc"
    )
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument(
        "-o", "--output", type=Path, help="report path (default: named by date range)"
    )
    destination.add_argument(
        "-d",
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="folder for the auto-named report (default: current folder)",
    )
    parser.add_argument(
        "--min-chlorine",
        type=float,
        metavar="MG_L",
        help="highlight and count free chlorine readings below this value (mg/L)",
    )
    parser.add_argument("-f", "--force", action="store_true", help="overwrite an existing report")
    parser.add_argument("-v", "--verbose", action="store_true", help="show skipped entries")
    return parser.parse_args(argv)


def _existing_file(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"file not found: {path}")
    return path


if __name__ == "__main__":
    sys.exit(main())
