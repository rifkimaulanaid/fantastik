"""Bounded, synthetic audit probes; no requests to production news services.

Run from the repository root: python docs/audit/2026-11-06/reproduce.py
An 'observed' result confirms the audited behavior, not that the app is secure.
Outputs evidence.json beside this script. Requires the app's dependencies.
"""

import argparse
import ast
import contextlib
import hashlib
import importlib
import importlib.metadata
import io
import json
import logging
import platform
import re
import subprocess
import sys
import threading
import time
from datetime import date, datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import requests
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    baseline = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
    changed = [name for name, digest in baseline["source_sha256"].items()
               if not (ROOT / name).exists() or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    if changed:
        print("Probe ini khusus snapshot audit sebelum perbaikan. Untuk kode terbaru: python -m unittest discover -s tests -v")
        sys.exit(2)
from scrap import benuanta, prokal, radartarakan  # noqa: E402

DAY = date(2026, 11, 6)
RESULTS = []
logging.getLogger("streamlit").setLevel(logging.ERROR)


def load_main_functions():
    """Execute original function ASTs without launching the top-level UI."""
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = ast.Module(
        body=[node for node in tree.body if isinstance(node, ast.FunctionDef)],
        type_ignores=[],
    )
    namespace = dict(
        pd=pd, re=re, date=date, datetime=datetime, BytesIO=io.BytesIO,
        SUMMARY_MAX_CHARS=320, SUMMARY_MAX_SENTENCES=2,
        DATE_STORAGE_FORMAT="%Y-%m-%d", DATE_DISPLAY_FORMAT="%d-%m-%Y",
        ACTIVE_SOURCES={
            "Benuanta": benuanta.benuanta_scrap,
            "Prokal": prokal.prokal_scrap,
            "Radar Tarakan": radartarakan.radar_scrap,
        },
    )
    exec(compile(functions, str(ROOT / "main.py"), "exec"), namespace)
    return SimpleNamespace(**namespace)


CORE = load_main_functions()


def probe(name):
    def decorate(function):
        def run():
            started = time.perf_counter()
            captured = io.StringIO()
            try:
                with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                    detail = function()
                result = dict(name=name, outcome="observed", detail=detail)
            except Exception as error:
                result = dict(name=name, outcome="probe_failed", error=repr(error))
            result["seconds"] = round(time.perf_counter() - started, 3)
            RESULTS.append(result)
            print(json.dumps(result, ensure_ascii=True))
        return run
    return decorate


def response(text):
    result = requests.Response()
    result.status_code = 200
    result.encoding = "utf-8"
    result._content = text.encode("utf-8")
    return result


def article(raw_date="2026-11-06 12:00:00"):
    return dict(article_id="123", title="Berita audit", date=raw_date,
                category=dict(name="Ekonomi", slug="ekonomi"))


def page(items, more=False):
    return {"data": {"searchArticle": {
        "data": items, "paginatorInfo": {"hasMorePages": more},
    }}}


def row(**overrides):
    record = dict(Tanggal="2026-11-06", Sumber="Benuanta", Tagar="Ekonomi",
                  Judul="Berita audit", Isi="Teks berita", Ringkasan="Teks berita",
                  Tautan="https://example.invalid/article")
    record.update(overrides)
    return record


def app_with_rows(rows):
    app = AppTest.from_file(str(ROOT / "main.py"), default_timeout=30).run()
    assert not app.exception, [error.message for error in app.exception]
    app.session_state["scraped_df"] = pd.DataFrame(rows)
    app.run()
    assert not app.exception, [error.message for error in app.exception]
    return app


@probe("excel_formula_interpretation")
def formula():
    data = CORE.dataframe_to_excel_bytes(pd.DataFrame({"Judul": ["=1+1"]}))
    cell = load_workbook(io.BytesIO(data), data_only=False).active["A2"]
    assert cell.data_type == "f"
    return dict(input="=1+1", saved_cell_type=cell.data_type, saved_value=cell.value)


@probe("excel_long_text_and_control_character")
def excel_limits():
    data = CORE.dataframe_to_excel_bytes(pd.DataFrame({"Isi": ["x" * 40000]}))
    actual = len(load_workbook(io.BytesIO(data)).active["A2"].value)
    assert actual == 32767
    try:
        CORE.dataframe_to_excel_bytes(pd.DataFrame({"Isi": ["teks\x01berita"]}))
    except Exception as error:
        error_name = type(error).__name__
    else:
        raise AssertionError("Expected rejected XML control character")
    assert error_name == "IllegalCharacterError"
    return dict(input_characters=40000, saved_characters=actual,
                invalid_control_character_error=error_name)


@probe("keyword_regex_crashes_actual_ui")
def regex_crash():
    app = app_with_rows([row()])
    app.text_input[0].set_value("[").run()
    assert app.exception
    return dict(keyword="[", ui_error=app.exception[0].message)


@probe("keyword_dot_matches_all_actual_ui")
def regex_matches():
    app = app_with_rows([row(), row()])
    app.text_input[0].set_value(".").run()
    assert not app.exception
    count = len(app.dataframe[0].value)
    assert count == 2
    return dict(keyword=".", rows_without_literal_dot=2, displayed_rows=count)


@probe("benuanta_fetch_failure_reported_as_success")
def false_success():
    with patch.object(benuanta, "fetch_page", return_value=None):
        result = CORE.scrape_news(DAY, DAY, ["Benuanta"])
    assert result["reports"][0]["status"] == "success"
    return result["reports"][0]


@probe("benuanta_page_cap_reported_as_success")
def page_cap():
    html = '<article><time>07 November 2026</time></article><a class="next page-numbers">Next</a>'
    with patch.object(benuanta, "fetch_page", return_value=response(html)) as fetch:
        data = benuanta.benuanta_scrap(DAY, DAY, max_page=2)
    assert fetch.call_count == 2 and not data
    return dict(pages_requested=fetch.call_count, target_range_not_reached=True,
                result_rows=len(data), terminal_error=False, default_max_page=200)


@probe("missing_article_content_reported_as_success")
def missing_body():
    html = ('<article><time>06 November 2026</time><h2>Berita</h2>'
            '<span class="gmr-meta-topic">Ekonomi</span>'
            '<a href="https://example.invalid/article">Read</a></article>')
    with patch.object(benuanta, "fetch_page", return_value=response(html)), \
            patch.object(benuanta, "extract_benuanta_content", return_value=None):
        result = CORE.scrape_news(DAY, DAY, ["Benuanta"])
    assert result["reports"][0]["status"] == "success"
    assert result["data"][0]["Isi"] is None
    return dict(report=result["reports"][0], rows_without_body=1)


@probe("graphql_later_page_error_discards_prior_rows")
def discarded_rows():
    details = []
    for module, source, fetch_name, content_name in (
        (prokal, "Prokal", "fetch_prokal_page", "extract_prokal_content"),
        (radartarakan, "Radar Tarakan", "fetch_radar_page", "extract_radar_content"),
    ):
        with patch.object(module, fetch_name, side_effect=[page([article()], True), RuntimeError("synthetic page 2 failure")]), \
                patch.object(module, content_name, return_value="Isi tersimpan di memori") as extract:
            result = CORE.scrape_news(DAY, DAY, [source])
        assert extract.call_count == 1 and result["data"] == []
        details.append(dict(source=source, prior_rows_parsed=1,
                            returned_rows=0, status=result["reports"][0]["status"]))
    return details


@probe("graphql_double_unescape_breaks_valid_payload")
def double_unescape():
    payload = {"props": {"article": {"content": '<p>Ia berkata &quot;baik&quot; hari ini.</p>'}}}
    html = '<div id="app" data-page="' + escape(json.dumps(payload), quote=True) + '"></div>'
    errors = {}
    for module, extractor in ((prokal, prokal.extract_prokal_content),
                              (radartarakan, radartarakan.extract_radar_content)):
        with patch.object(module.SESSION, "get", return_value=response(html)):
            try:
                extractor("https://example.invalid/article")
            except json.JSONDecodeError as error:
                errors[module.__name__] = type(error).__name__
    assert len(errors) == 2
    return dict(valid_json_before_html_encoding=True, errors=errors)


@probe("graphql_accepts_out_of_range_article")
def date_range():
    details = []
    for module, scraper, fetch_name, content_name in (
        (prokal, prokal.prokal_scrap, "fetch_prokal_page", "extract_prokal_content"),
        (radartarakan, radartarakan.radar_scrap, "fetch_radar_page", "extract_radar_content"),
    ):
        with patch.object(module, fetch_name, return_value=page([article("2020-01-01 12:00:00")])), \
                patch.object(module, content_name, return_value="Isi"):
            rows = scraper(DAY, DAY)
        assert rows[0]["Tanggal"] == "2020-01-01"
        details.append(dict(source=module.__name__, returned_date=rows[0]["Tanggal"]))
    return dict(requested_date=DAY.isoformat(), results=details)


@probe("graphql_repeated_page_is_not_stopped_or_deduplicated")
def repeated_page():
    details = []
    for module, scraper, fetch_name, content_name in (
        (prokal, prokal.prokal_scrap, "fetch_prokal_page", "extract_prokal_content"),
        (radartarakan, radartarakan.radar_scrap, "fetch_radar_page", "extract_radar_content"),
    ):
        repeated = page([article()], True)
        with patch.object(module, fetch_name, side_effect=[repeated, repeated, repeated, RuntimeError("probe safety stop")]) as fetch, \
                patch.object(module, content_name, return_value="Isi") as extract:
            try:
                scraper(DAY, DAY)
            except RuntimeError as error:
                assert "probe safety stop" in str(error)
        assert fetch.call_count == 4 and extract.call_count == 3
        details.append(dict(source=module.__name__, duplicate_detail_fetches=extract.call_count,
                            stopped_by="synthetic exception on fourth page"))
    return details


@probe("benuanta_external_href_reaches_controlled_loopback")
def loopback_fetch():
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            body = b'<div class="entry-content"><p>AUDIT_LOOPBACK_ONLY</p></div>'
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    target = f"http://127.0.0.1:{server.server_port}/audit"
    index = ('<article><time>06 November 2026</time><h2>Berita</h2>'
             '<span class="gmr-meta-topic">Ekonomi</span>'
             f'<a href="{target}">Read</a></article>')
    original_fetch = benuanta.fetch_page

    def fake_index(url, *args, **kwargs):
        if url.startswith("https://benuanta.co.id/index.php/page/"):
            return response(index)
        assert url == target, "Probe must never contact any other destination"
        return original_fetch(url, *args, **kwargs)

    try:
        with patch.object(benuanta, "fetch_page", side_effect=fake_index), \
                patch.object(benuanta.SESSION, "trust_env", False):
            rows = benuanta.benuanta_scrap(DAY, DAY)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert hits == ["/audit"] and rows[0]["Isi"] == "AUDIT_LOOPBACK_ONLY"
    return dict(controlled_loopback_requests=len(hits), body_in_scraped_result=True,
                prerequisite="control of remote index href or redirect destination")


@probe("remote_category_reaches_html_enabled_markdown")
def raw_html():
    record = row()
    record["Tagar"] = "<b>AUDIT_HTML</b>"
    app = app_with_rows([record])
    rendered = [element.value for element in app.markdown]
    sink = [value for value in rendered if "detail-meta-card" in value]
    assert any("<b>AUDIT_HTML</b>" in value for value in sink)
    return dict(raw_markup_in_detail_sink=True, javascript_execution_tested=False)


@probe("inactive_tabs_render_all_details_and_rebuild_excel")
def eager_render():
    app = AppTest.from_file(str(ROOT / "main.py"), default_timeout=30).run()
    app.session_state["scraped_df"] = pd.DataFrame([row() for _ in range(250)])
    original_to_excel = pd.DataFrame.to_excel
    calls = []

    def counted_export(frame, *args, **kwargs):
        calls.append(len(frame))
        return original_to_excel(frame, *args, **kwargs)

    with patch.object(pd.DataFrame, "to_excel", counted_export):
        app.run()
        assert not app.exception
        details = len(app.expander)
        app.text_input[0].set_value("berita").run()
        assert not app.exception
    assert details == 250 and calls == [250, 250]
    return dict(rows=250, rendered_detail_expanders_with_table_selected=details,
                excel_builds_over_two_runs=len(calls), excel_download_clicks=0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("evidence.json"))
    args = parser.parse_args()
    for check in (formula, excel_limits, regex_crash, regex_matches, false_success,
                  page_cap, missing_body, discarded_rows, double_unescape,
                  date_range, repeated_page, loopback_fetch, raw_html, eager_render):
        check()
    tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    evidence = {
        "audit_date": "2026-11-06",
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "python": platform.python_version(),
        "versions": {name: importlib.metadata.version(name) for name in
                     ("pandas", "streamlit", "openpyxl", "requests", "beautifulsoup4", "Pillow")},
        "method": "Synthetic fixtures and Streamlit AppTest; only HTTP is a controlled loopback server",
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                          for name in tracked if (ROOT / name).is_file()},
        "checks": RESULTS,
    }
    output = args.output
    output.write_text(json.dumps(evidence, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Evidence: {output}")
    sys.exit(1 if any(result["outcome"] == "probe_failed" for result in RESULTS) else 0)
