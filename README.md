# WaterTesting

Turns a Hach CL17sc chlorine analyzer datalog export (`.xml`) into an Excel
report with one row per day and charts for free chlorine and flow rate.

## Use it in a web browser

**https://nfvcsd.github.io/WaterTesting/**

Choose the datalog, optionally enter the minimum free chlorine, and click
**Create report**. The spreadsheet downloads. It works in current Chrome, Edge,
Safari and Firefox, including on Chromebooks, with nothing to install.

The report is made inside the browser by the same Python code as the
command-line tool (run with [Pyodide](https://pyodide.org/)). The datalog is
never uploaded, and the page loads nothing from outside this site.

To pre-fill the minimum for everyone, set `default_min_chlorine` in
[`web/config.json`](web/config.json) (for example `0.3`) in a pull request.

## Command-line install

Requires [uv](https://docs.astral.sh/uv/). uv provides its own Python, so the
system Python version doesn't matter.

```sh
uv tool install .            # from a clone of this repo
uv tool upgrade water-report # after pulling changes
```

## Command-line use

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
| `web.py` | Entry point the browser converter calls |

### Browser converter

| Path | Job |
| --- | --- |
| `web/` | The page: `index.html`, `app.js` (form and download), `worker.js` (runs Python via Pyodide off the main thread), `config.json`, NFV logo and self-hosted Open Sans |
| `scripts/build_site.py` | Assembles `_site/`: copies `web/`, adds the Pyodide runtime (pinned by version and SHA-256) and the wheels from `uv.lock` (hash-checked) |
| `tests/e2e/` | Playwright tests that convert the sample file in Chromium and check nothing is fetched from other sites |

Try it locally:

```sh
uv run scripts/build_site.py
python -m http.server -d _site 8000          # open http://localhost:8000
uv sync --group e2e && uv run playwright install chromium
SITE_DIR=_site uv run pytest tests/e2e
```

To upgrade Pyodide, change `PYODIDE_VERSION` in `scripts/build_site.py`, run it,
and copy the new hash from the error after checking it against the
[release page](https://github.com/pyodide/pyodide/releases).

### CI and deployment

- **CI** (`ci.yml`): lint and unit tests on every pull request.
- **Pages** (`pages.yml`): builds the site and runs the browser tests on every
  pull request; on `main`, also deploys to GitHub Pages. Repository setting
  required once: *Settings → Pages → Source: GitHub Actions*.
- **Dependabot**: monthly PRs for Python dependencies and GitHub Actions.
