"""Browser tests for the GitHub Pages converter.

They need a built site and Playwright's Chromium:

    uv run scripts/build_site.py
    uv run --group e2e playwright install chromium
    SITE_DIR=_site uv run --group e2e pytest tests/e2e

Without SITE_DIR (or Playwright) they are skipped, so plain ``pytest`` stays fast.
"""

from __future__ import annotations

import functools
import os
import threading
from collections.abc import Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from openpyxl import load_workbook

from tests.conftest import SAMPLE_DATALOG

playwright_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = os.environ.get("SITE_DIR")
pytestmark = pytest.mark.skipif(not SITE_DIR, reason="set SITE_DIR to a built site to run")

READY_TIMEOUT_MS = 60_000


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture(scope="module")
def site_url() -> Iterator[str]:
    handler = functools.partial(QuietHandler, directory=str(Path(SITE_DIR).resolve()))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()


@pytest.fixture(scope="module")
def browser() -> Iterator[object]:
    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser, site_url):
    """A loaded page with the converter ready, recording any off-site requests."""
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()
    page.off_site_requests = []
    page.console_errors = []
    page.on(
        "request",
        lambda request: (
            None
            if request.url.startswith((site_url, "blob:", "data:"))
            else page.off_site_requests.append(request.url)
        ),
    )
    page.on(
        "console",
        lambda message: (
            page.console_errors.append(message.text) if message.type == "error" else None
        ),
    )
    page.goto(site_url)
    playwright_api.expect(page.locator("#status")).to_have_text(
        "Ready. Choose a datalog to begin.", timeout=READY_TIMEOUT_MS
    )
    yield page
    context.close()


def test_converts_sample_datalog(page, tmp_path):
    page.set_input_files("#datalog", SAMPLE_DATALOG)
    page.fill("#min-chlorine", "0.2")

    with page.expect_download() as download_info:
        page.click("#convert")
    download = download_info.value
    assert download.suggested_filename == "2023-12-28_to_2024-01-17.xlsx"

    report = tmp_path / download.suggested_filename
    download.save_as(report)
    workbook = load_workbook(report)
    assert workbook.sheetnames == ["Daily Summary", "About"]
    assert workbook["Daily Summary"].max_row == 22  # header + 21 days

    playwright_api.expect(page.locator("#result-summary")).to_contain_text("21 days")
    playwright_api.expect(page.locator("#result-warning")).to_contain_text("12/30/2023")


def test_explains_a_file_that_is_not_a_datalog(page, tmp_path):
    wrong = tmp_path / "notes.xml"
    wrong.write_text("<Notes>hello</Notes>")

    page.set_input_files("#datalog", wrong)
    page.click("#convert")

    playwright_api.expect(page.locator("#status")).to_contain_text("doesn't look like a CL17sc")
    assert page.locator("#result").is_hidden()


def test_rejects_non_xml_files(page, tmp_path):
    spreadsheet = tmp_path / "report.xlsx"
    spreadsheet.write_bytes(b"PK")

    page.set_input_files("#datalog", spreadsheet)

    playwright_api.expect(page.locator("#status")).to_contain_text("isn't an .xml file")
    assert page.locator("#convert").is_disabled()


def test_nothing_is_fetched_from_other_sites(page):
    page.set_input_files("#datalog", SAMPLE_DATALOG)
    with page.expect_download():
        page.click("#convert")

    assert page.off_site_requests == []
    assert page.console_errors == []
