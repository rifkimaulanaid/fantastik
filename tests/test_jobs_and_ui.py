from copy import deepcopy
from datetime import date
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from helper.jobs import ScrapeJob, load_checkpoint, save_checkpoint

ROOT = Path(__file__).resolve().parents[1]


def result(rows=2, state="complete"):
    return {"data": [{"Judul": "Berita [uji]", "Tagar": "<b>Ekonomi</b>", "Isi": "Teks biasa",
                       "Tanggal": "2026-11-06", "Sumber": "Prokal", "Ringkasan": "Teks biasa",
                       "Tautan": "https://www.prokal.co/ekonomi/123/berita"} for _ in range(rows)],
            "reports": [{"source": "Prokal", "count": rows, "status": "success", "issues": [],
                         "coverage_complete": True, "pages": 1, "missing_body": 0}],
            "metadata": {"run_id": "a" * 32, "state": state, "started_at": "2026-11-06T10:00:00+08:00",
                         "requested_start": "2026-11-06", "requested_end": "2026-11-06"}}


def app_with_result(rows=2):
    with patch("helper.jobs.DEFAULT_STORE", Path(tempfile.gettempdir()) / "fantastik-test-missing"):
        app = AppTest.from_file(str(ROOT / "main.py"), default_timeout=30).run()
    app.session_state["active_result"] = result(rows)
    app.run()
    if app.exception:
        raise AssertionError([e.message for e in app.exception])
    return app


class JobTests(unittest.TestCase):
    def test_atomic_checkpoint_and_interrupted_status(self):
        payload = result(state="running")
        payload["reports"][0].update(coverage_complete=False, status="partial")
        with tempfile.TemporaryDirectory() as directory:
            save_checkpoint(payload, directory)
            path = Path(directory) / ("a" * 32 + ".json")
            recovered = load_checkpoint(path)
            self.assertEqual(recovered["metadata"]["state"], "interrupted")
            self.assertEqual(recovered["reports"][0]["stop_reason"], "INTERRUPTED")
            self.assertEqual(len(recovered["data"]), 2)
            self.assertFalse(list(Path(directory).glob("*.tmp")))

    def test_checkpoint_path_traversal_rejected(self):
        payload = result()
        payload["metadata"]["run_id"] = "../outside"
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            save_checkpoint(payload, directory)

    def test_checkpoint_retention_keeps_unrelated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            unrelated = Path(directory) / "notes.json"
            unrelated.write_text("{}")
            for i in range(23):
                payload = result()
                payload["metadata"]["run_id"] = f"{i:032x}"
                save_checkpoint(payload, directory)
            self.assertTrue(unrelated.exists())
            self.assertEqual(len(list(Path(directory).glob("*.json"))), 21)

    def test_background_job_completes_and_persists_without_streamlit(self):
        with tempfile.TemporaryDirectory() as directory, patch("helper.jobs.scrape_news", return_value=result()):
            job = ScrapeJob(date(2026, 11, 6), date(2026, 11, 6), ["Prokal"], store=directory)
            job.start()
            self.assertTrue(job.done.wait(5))
            self.assertIsNone(job.error)
            self.assertEqual(len(job.snapshot()[2]["data"]), 2)

    def test_global_concurrency_rejects_third_job(self):
        gate = threading.BoundedSemaphore(2)
        gate.acquire()
        gate.acquire()
        with patch("helper.jobs._slots", gate), self.assertRaises(RuntimeError):
            ScrapeJob(date(2026, 11, 6), date(2026, 11, 6), ["Prokal"]).start()

    def test_storage_error_does_not_discard_in_memory_result(self):
        job = ScrapeJob(date(2026, 11, 6), date(2026, 11, 6), ["Prokal"])
        with patch("helper.jobs.save_checkpoint", side_effect=PermissionError("denied")):
            job._checkpoint(result())
        self.assertIsNotNone(job.storage_error)
        self.assertEqual(len(job.snapshot()[2]["data"]), 2)


class UITests(unittest.TestCase):
    def test_search_bracket_and_no_eager_details_or_export(self):
        with patch("helper.data.dataframe_to_excel_bytes") as export:
            app = app_with_result(250)
            app.text_input[0].set_value("[").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe[0].value), 250)
        self.assertFalse(any(box.key == "article_position" for box in app.selectbox))
        self.assertFalse(any('class="article-reader"' in block.value for block in app.markdown))
        export.assert_not_called()

    def test_html_category_uses_text_and_one_detail(self):
        app = app_with_result(250)
        app.radio[0].set_value("Detail").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("<b>Ekonomi</b>" in element.value for element in app.text))
        self.assertFalse(any("<b>Ekonomi</b>" in element.value for element in app.markdown))
        self.assertEqual(len(app.get("link_button")), 1)

    def test_export_only_runs_on_prepare_and_invalidates_after_filter(self):
        from helper.data import dataframe_to_excel_bytes
        with patch("helper.data.dataframe_to_excel_bytes", wraps=dataframe_to_excel_bytes) as export:
            app = app_with_result()
            app.radio[0].set_value("Unduh").run()
            export.assert_not_called()
            next(button for button in app.button if button.label == "Siapkan unduhan").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(export.call_count, 1)
            self.assertEqual(len(app.get("download_button")), 2)
            app.text_input[0].set_value("Tidak ditemukan").run()
            self.assertEqual(export.call_count, 1)
            self.assertEqual(len(app.get("download_button")), 0)

    def test_failed_attempt_preserves_previous_good_result(self):
        app = app_with_result()
        failed = result(0, "incomplete")
        failed["reports"][0].update(status="failed", message="timeout", coverage_complete=False)
        app.session_state["last_attempt"] = failed
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe[0].value), 2)
        self.assertTrue(any("sebelumnya" in notice.value for notice in app.warning))

    def test_completed_background_job_adopts_result_and_archives_previous(self):
        app = app_with_result()
        incoming = result(3)
        incoming["metadata"]["run_id"] = "b" * 32
        done = threading.Event()
        done.set()
        app.session_state["job"] = SimpleNamespace(snapshot=lambda: (1.0, "Selesai", incoming),
                                                   done=done, error=None, storage_error=None)
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe[0].value), 3)
        self.assertEqual(len(app.session_state["run_history"]), 1)

    def test_cancel_button_signals_worker(self):
        app = app_with_result()
        cancel = threading.Event()
        app.session_state["job"] = SimpleNamespace(snapshot=lambda: (0.1, "Memproses", None),
                                                   done=threading.Event(), cancel=cancel, storage_error=None)
        app.run()
        next(button for button in app.button if button.label == "Batalkan proses").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(cancel.is_set())

    def test_date_presets_and_invalid_range(self):
        from datetime import timedelta
        app = app_with_result()
        next(box for box in app.selectbox if box.key == "date_preset").set_value("7 hari").run()
        self.assertEqual((app.session_state["collect_end"] - app.session_state["collect_start"]).days, 6)
        next(box for box in app.selectbox if box.key == "date_preset").set_value("30 hari").run()
        self.assertEqual((app.session_state["collect_end"] - app.session_state["collect_start"]).days, 29)
        next(widget for widget in app.date_input if widget.key == "collect_start").set_value(
            app.session_state["collect_end"] - timedelta(days=40)).run()
        self.assertFalse(app.exception)
        self.assertTrue(next(button for button in app.button if button.key == "collect_news").disabled)
        self.assertEqual(app.session_state["date_preset"], "Atur tanggal")

    def test_clear_filters_recovers_empty_results(self):
        app = app_with_result()
        app.text_input[0].set_value("Tidak ditemukan").run()
        self.assertEqual(len(app.dataframe), 0)
        self.assertTrue(any("Tidak ada berita yang cocok" in item.value for item in app.info))
        next(button for button in app.button if button.key == "clear_filters").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe[0].value), 2)
        self.assertEqual(app.session_state["result_keyword"], "")

    def test_article_navigation_and_filter_change(self):
        app = app_with_result(3)
        app.radio[0].set_value("Detail").run()
        self.assertTrue(next(button for button in app.button if button.key == "previous_article").disabled)
        next(button for button in app.button if button.key == "next_article").click().run()
        self.assertEqual(app.session_state["article_position"], 1)
        next(button for button in app.button if button.key == "next_article").click().run()
        self.assertTrue(next(button for button in app.button if button.key == "next_article").disabled)
        app.text_input[0].set_value("[").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["article_position"], 0)

    def test_export_filter_change_explains_regeneration(self):
        app = app_with_result()
        app.radio[0].set_value("Unduh").run()
        next(button for button in app.button if button.key == "prepare_download").click().run()
        app.text_input[0].set_value("berita").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Siapkan ulang unduhan" in item.value for item in app.info))
        self.assertEqual(len(app.get("download_button")), 0)
