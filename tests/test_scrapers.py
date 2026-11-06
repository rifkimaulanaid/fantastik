from datetime import date, timedelta
from html import escape
import json
import threading
import unittest
from unittest.mock import patch

from helper.http_client import FetchError
from helper.models import Budget, SourceResult
from helper.pipeline import scrape_news
from scrap import benuanta, jawapos
from scrap.tribunkaltara import tribun_scrap

DAY = date(2026, 11, 6)


def item(identity="123", published="2026-11-06 12:00:00"):
    return dict(article_id=identity, title="Berita", date=published,
                category=dict(name="Ekonomi", slug="ekonomi"))


def page(items, more=False):
    return {"data": {"searchArticle": {"data": items, "paginatorInfo": {"hasMorePages": more}}}}


def index(url="https://benuanta.co.id/article", day="06 November 2026", next_page=False):
    return (f'<article><time>{day}</time><h2><a href="{url}">Berita</a></h2>'
            '<span class="gmr-meta-topic">Ekonomi</span></article>'
            + ('<a class="next page-numbers">Next</a>' if next_page else ""))


def run_jawapos(payloads, **kwargs):
    with patch.object(jawapos, "fetch_page", side_effect=payloads), \
            patch.object(jawapos, "extract_content", return_value="Isi"):
        return jawapos.scrape(jawapos.PROKAL, DAY, DAY, **kwargs)


class ScraperTests(unittest.TestCase):
    def test_source_paragraphs_are_preserved_without_inventing_boundaries(self):
        from helper.helper_function import normalize_article_text
        self.assertEqual(normalize_article_text(["Kalimat pertama.\nLanjutan.", "Paragraf kedua."]),
                         "Kalimat pertama. Lanjutan.\n\nParagraf kedua.")
        self.assertEqual(normalize_article_text("Teks lama tanpa batas paragraf."),
                         "Teks lama tanpa batas paragraf.")

    def test_later_page_failure_keeps_prior_data_for_both_publishers(self):
        for publisher in (jawapos.PROKAL, jawapos.RADAR):
            with self.subTest(source=publisher.name), \
                    patch.object(jawapos, "fetch_page", side_effect=[page([item()], True), FetchError("timeout")]), \
                    patch.object(jawapos, "extract_content", return_value="Isi"):
                result = jawapos.scrape(publisher, DAY, DAY)
            self.assertEqual(len(result.rows), 1)
            self.assertEqual(result.status, "partial")
            self.assertFalse(result.coverage_complete)

    def test_bad_article_does_not_drop_next_article(self):
        with patch.object(jawapos, "fetch_page", return_value=page([item(), item("124")])), \
                patch.object(jawapos, "extract_content", side_effect=[ValueError("bad JSON"), "Isi valid"]):
            result = jawapos.scrape(jawapos.PROKAL, DAY, DAY)
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.rows[1]["Isi"], "Isi valid")
        self.assertEqual(result.report()["missing_body"], 1)
        self.assertEqual(result.status, "partial")

    def test_entity_quotes_do_not_corrupt_json(self):
        payload = {"props": {"article": {"content": '<p>Ia berkata &quot;baik&quot; &amp; aman.</p>'}}}
        html = '<div id="app" data-page="' + escape(json.dumps(payload), quote=True) + '"></div>'
        self.assertEqual(jawapos.parse_content(html), 'Ia berkata "baik" & aman.')

    def test_null_and_broken_schema_never_report_success(self):
        for payload in [None, {"data": None}, {"data": {"searchArticle": None}},
                        {"errors": [{"message": "error"}]}, page([], True),
                        {"data": {"searchArticle": {"data": [], "paginatorInfo": {"hasMorePages": "false"}}}}]:
            with self.subTest(payload=payload):
                result = run_jawapos([payload])
                self.assertEqual(result.status, "failed")

    def test_valid_empty_is_success(self):
        result = run_jawapos([page([])])
        self.assertEqual(result.status, "success")
        self.assertTrue(result.coverage_complete)

    def test_out_of_range_does_not_fetch_detail(self):
        with patch.object(jawapos, "fetch_page", return_value=page([item(published="2020-01-01 12:00:00")])), \
                patch.object(jawapos, "extract_content") as fetch:
            result = jawapos.scrape(jawapos.PROKAL, DAY, DAY)
        fetch.assert_not_called()
        self.assertFalse(result.rows)
        self.assertEqual(result.issues[0]["code"], "OUT_OF_RANGE")

    def test_repeated_page_stops_without_repeating_content(self):
        with patch.object(jawapos, "fetch_page", return_value=page([item()], True)) as fetch, \
                patch.object(jawapos, "extract_content", return_value="Isi") as detail:
            result = jawapos.scrape(jawapos.PROKAL, DAY, DAY)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(detail.call_count, 1)
        self.assertEqual(result.stop_reason, "REPEATED_PAGE")

    def test_duplicate_in_overlapping_pages_is_skipped(self):
        result = run_jawapos([page([item()], True), page([item(), item("124")])])
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.duplicates, 1)

    def test_page_article_text_and_time_limits_are_partial(self):
        cases = [Budget(max_pages=1), Budget(max_articles=1), Budget(max_characters=2), Budget(seconds=0)]
        for budget in cases:
            with self.subTest(budget=budget):
                result = run_jawapos([page([item(), item("124")], True)], budget=budget)
                self.assertNotEqual(result.status, "success")
                self.assertIn(result.stop_reason, {"PAGE_LIMIT", "ARTICLE_LIMIT", "TEXT_LIMIT", "TIME_LIMIT"})

    def test_cancellation_preserves_article_metadata(self):
        cancel = threading.Event()

        def stop(*args):
            cancel.set()
            args[-1].check()

        with patch.object(jawapos, "fetch_page", return_value=page([item()])), \
                patch.object(jawapos, "extract_content", side_effect=stop):
            result = jawapos.scrape(jawapos.PROKAL, DAY, DAY, budget=Budget(cancel=cancel))
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.stop_reason, "CANCELLED")

    def test_benuanta_fetch_failure_is_failed(self):
        with patch.object(benuanta, "fetch_page", side_effect=FetchError("offline")):
            result = benuanta.benuanta_scrap(DAY, DAY)
        self.assertEqual(result.status, "failed")

    def test_benuanta_page_cap_and_missing_body_are_visible(self):
        with patch.object(benuanta, "fetch_page"), \
                patch.object(benuanta, "decode_response_text", return_value=index(next_page=True)), \
                patch.object(benuanta, "extract_benuanta_content", side_effect=FetchError("body failed")):
            result = benuanta.benuanta_scrap(DAY, DAY, max_page=1)
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.stop_reason, "PAGE_LIMIT")
        self.assertEqual(result.report()["missing_body"], 1)

    def test_benuanta_unsafe_link_never_reaches_detail(self):
        with patch.object(benuanta, "fetch_page"), \
                patch.object(benuanta, "decode_response_text", return_value=index("http://127.0.0.1/a")), \
                patch.object(benuanta, "extract_benuanta_content") as detail:
            result = benuanta.benuanta_scrap(DAY, DAY)
        detail.assert_not_called()
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.issues[0]["code"], "UNSAFE_URL")

    def test_benuanta_changed_layout_does_not_mean_zero_news(self):
        with patch.object(benuanta, "fetch_page"), patch.object(benuanta, "decode_response_text", return_value="<h1>Denied</h1>"):
            result = benuanta.benuanta_scrap(DAY, DAY)
        self.assertEqual(result.status, "failed")

    def test_benuanta_pinned_old_article_does_not_hide_next_page(self):
        first = index("https://benuanta.co.id/pinned", "01 January 2020") + index(next_page=True)
        second = index("https://benuanta.co.id/next-article")
        with patch.object(benuanta, "fetch_page"), \
                patch.object(benuanta, "decode_response_text", side_effect=[first, second]), \
                patch.object(benuanta, "extract_benuanta_content", return_value="Isi"):
            result = benuanta.benuanta_scrap(DAY, DAY)
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.pages, 2)

    def test_benuanta_valid_empty_marker_is_success(self):
        with patch.object(benuanta, "fetch_page"), \
                patch.object(benuanta, "decode_response_text", return_value='<section class="no-results"></section>'):
            result = benuanta.benuanta_scrap(DAY, DAY)
        self.assertEqual(result.status, "success")

    def test_pipeline_keeps_checkpoints_when_adapter_raises(self):
        def failing(*args, checkpoint, **kwargs):
            result = SourceResult("X", rows=[{"Judul": "Valid", "Isi": "Isi"}])
            checkpoint(result)
            raise RuntimeError("late failure")
        result = scrape_news(DAY, DAY, ["X"], adapters={"X": failing})
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["reports"][0]["status"], "partial")

    def test_invalid_dates_and_source_fail_before_fetch(self):
        with self.assertRaises(ValueError):
            scrape_news(DAY, DAY + timedelta(days=31), ["Prokal"])
        with self.assertRaises(ValueError):
            scrape_news(DAY, DAY, ["Prokal", "Prokal"])
        with self.assertRaises(ValueError):
            scrape_news(DAY, DAY, ["Unknown"])

    def test_inactive_browser_source_fails_closed(self):
        with self.assertRaises(RuntimeError):
            tribun_scrap(["06-11-2026"])

    def test_successful_content_is_cached_but_invalid_content_is_not(self):
        from collections import OrderedDict
        from types import SimpleNamespace
        payload = {"props": {"article": {"content": "<p>Isi valid</p>"}}}
        html = '<div id="app" data-page="' + escape(json.dumps(payload), quote=True) + '"></div>'
        url = "https://www.prokal.co/ekonomi/123/berita"
        with patch("helper.content_cache._entries", OrderedDict()), \
                patch.object(jawapos, "request", return_value=SimpleNamespace(text=html)) as fetch:
            self.assertEqual(jawapos.extract_content(url, jawapos.PROKAL), "Isi valid")
            self.assertEqual(jawapos.extract_content(url, jawapos.PROKAL), "Isi valid")
            self.assertEqual(fetch.call_count, 1)
        with patch("helper.content_cache._entries", OrderedDict()), \
                patch.object(jawapos, "request", return_value=SimpleNamespace(text="invalid")) as fetch:
            for _ in range(2):
                with self.assertRaises(ValueError):
                    jawapos.extract_content(url, jawapos.PROKAL)
            self.assertEqual(fetch.call_count, 2)
