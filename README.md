# WaterTesting

Turns a Hach CL17sc chlorine analyzer datalog export (`.xml`) into an Excel
report with one row per day and charts for free chlorine and flow rate.

## Install

Requires [uv](https://docs.astral.sh/uv/). uv provides its own Python, so the
system Python version doesn't matter.

```sh
uv tool install .            # from a clone of this repo
uv tool upgrade water-report # after pulling changes
```

## Run

```sh
water-report ~/Downloads/CL17sc_..._DL_....xml --min-chlorine 0.3 -d ~/Reports
```

That writes `~/Reports/2023-12-28_to_2024-01-17.xlsx`, named by the first and
last day in the export. You can drag the `.xml` file into the terminal instead
of typing its path.

| Option | Meaning |
| --- | --- |
| `-d, --output-dir DIR` | Folder for the auto-named report (default: current folder) |
| `-o, --output FILE` | Exact report path instead of the auto name |
| `--min-chlorine MG_L` | Shade days whose free chlorine mean or minimum is below this, count low readings per day, and print a warning. **Use the minimum residual from the system's permit;** `0.3` above is only an example. |
| `-f, --force` | Overwrite an existing report |
| `-v, --verbose` | Show entries that were skipped |

## The report

**Daily Summary** sheet: date, sample count, free chlorine mean/min/max
(mg/L), flow mean/min/max, and (with `--min-chlorine`) the number of readings
below the minimum. Two line charts sit beside the table: free chlorine (daily
mean and minimum) and flow rate (daily mean). Each chart has its own y-axis
because the two measures are on very different scales.

**About** sheet: source file, analyzer name/location/serial, date range,
reading counts, the minimum used, and when the report was generated.

The first and last days of an export are usually partial; check the Samples
column.

## Development

```sh
uv sync                  # create .venv with dev tools
uv run pytest            # tests, including a real export in tests/fixtures/
uv run ruff check .      # lint
uv run ruff format .     # format
```

Code layout:

| Module | Job |
| --- | --- |
| `parse.py` | Read the XML (via `defusedxml`) into `Reading`s; handles the analyzer's mixed timestamp formats, missing channels and duplicated blocks |
| `summarize.py` | Group readings by day into mean/min/max |
| `excel.py` | Build the workbook and charts |
| `cli.py` | Command-line arguments and file handling |

CI runs lint and tests on every pull request. Dependabot opens monthly PRs for
dependency and GitHub Actions updates.
