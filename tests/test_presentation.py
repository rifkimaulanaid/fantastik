from datetime import date
import unittest

from helper.presentation import article_html, human_date, human_time, preset_dates, source_cards


class PresentationTests(unittest.TestCase):
    def test_human_dates_use_business_timezone(self):
        self.assertEqual(human_date("2026-11-06"), "6 November 2026")
        self.assertEqual(human_date("06-11-2026"), "6 November 2026")
        self.assertEqual(human_time("2026-11-05T20:15:00Z"), "6 November 2026, 04.15 WITA")
        self.assertEqual(human_date(None), "Tanggal tidak tersedia")

    def test_presets_are_inclusive_and_bounded(self):
        today = date(2026, 11, 6)
        for label, days in [("Hari ini", 1), ("7 hari", 7), ("30 hari", 30)]:
            start, end = preset_dates(label, today)
            self.assertEqual((end - start).days + 1, days)
            self.assertEqual(end, today)
        self.assertIsNone(preset_dates("Atur tanggal", today))

    def test_remote_text_never_becomes_article_markup(self):
        title = '<img src=x onerror="alert(1)">'
        text = '<script>alert(1)</script>\n\nParagraf asli & lengkap.'
        html = article_html(title, text)
        self.assertNotIn("<img", html)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("\n\nParagraf asli &amp; lengkap.", html)

    def test_remote_source_is_escaped_and_status_has_a_label(self):
        html = source_cards([dict(source="<b>Uji</b>", status="failed", count=0)])
        self.assertNotIn("<b>Uji</b>", html)
        self.assertIn("&lt;b&gt;Uji&lt;/b&gt;", html)
        self.assertIn("Gagal", html)
