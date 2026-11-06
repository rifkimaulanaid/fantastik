import io
import json
import socket
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
import requests
from openpyxl import load_workbook

from helper.data import dataframe_to_excel_bytes, filter_dataframe
from helper.http_client import FetchError, PublicHTTPSAdapter, UnsafeURL, public_address, request, validate_url


def response(body=b"ok", status=200, headers=None):
    result = requests.Response()
    result.status_code = status
    result.headers.update(headers or {})
    result.raw = MagicMock()
    result.raw.read1.side_effect = [body, b""]
    result.url = "https://benuanta.co.id/"
    return result


class URLSecurityTests(unittest.TestCase):
    def test_bad_urls_fail_before_network(self):
        values = ["http://benuanta.co.id/a", "https://localhost/a", "http://127.0.0.1/",
                  "https://169.254.169.254/", "https://[::1]/", "https://benuanta.co.id.evil.test/",
                  "https://benuanta.co.id@evil.test/", "https://evil.test@benuanta.co.id/",
                  "https://benuanta.co.id:444/", "https://benuanta.co.id\\@evil.test/",
                  "https://benuanta.co.id/\nheader", "file:///etc/passwd"]
        with patch("helper.http_client.session") as network:
            for value in values:
                with self.subTest(value=value), self.assertRaises(UnsafeURL):
                    request("GET", value)
            network.assert_not_called()

    def test_dns_private_mixed_and_multicast_are_rejected(self):
        for ip in ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fc00::1",
                   "fe80::1", "224.0.0.1", "fec0::1", "::ffff:127.0.0.1"]:
            records = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
                       (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]
            with self.subTest(ip=ip), patch("socket.getaddrinfo", return_value=records), self.assertRaises(UnsafeURL):
                public_address("benuanta.co.id")

    def test_connection_pins_ip_but_keeps_tls_hostname(self):
        adapter = PublicHTTPSAdapter()
        prepared = requests.Request("GET", "https://benuanta.co.id/article").prepare()
        with patch("helper.http_client.public_address", return_value="8.8.8.8") as resolve, \
                patch.object(adapter.poolmanager, "connection_from_host") as pool:
            adapter.get_connection_with_tls_context(prepared, True)
        resolve.assert_called_once_with("benuanta.co.id")
        self.assertEqual(pool.call_args.args, ("8.8.8.8",))
        self.assertEqual(pool.call_args.kwargs["pool_kwargs"]["assert_hostname"], "benuanta.co.id")
        self.assertEqual(pool.call_args.kwargs["pool_kwargs"]["server_hostname"], "benuanta.co.id")
        self.assertEqual(prepared.headers["Host"], "benuanta.co.id")
        with self.assertRaises(UnsafeURL):
            adapter.get_connection_with_tls_context(prepared, False)

    def test_redirect_is_checked_before_second_request(self):
        client = MagicMock()
        client.request.return_value = response(status=302, headers={"Location": "http://127.0.0.1/a"})
        with patch("helper.http_client.session", return_value=client), self.assertRaises(UnsafeURL):
            request("GET", "https://benuanta.co.id/")
        self.assertEqual(client.request.call_count, 1)

    def test_redirect_cannot_leave_publisher(self):
        client = MagicMock()
        client.request.return_value = response(status=302, headers={"Location": "https://www.prokal.co/a"})
        with patch("helper.http_client.session", return_value=client), self.assertRaises(UnsafeURL):
            request("GET", "https://benuanta.co.id/", allowed_hosts={"benuanta.co.id"})
        self.assertEqual(client.request.call_count, 1)

    def test_bounded_response_and_closed_stream(self):
        client = MagicMock()
        received = response(b"x" * 20)
        client.request.return_value = received
        with patch("helper.http_client.session", return_value=client), self.assertRaises(FetchError):
            request("GET", "https://benuanta.co.id/", max_bytes=10)
        received.raw.close.assert_called()

    def test_small_response_still_decodes_after_close(self):
        received = response(b'{"ok": true}')
        received.encoding = "utf-8"
        with patch("helper.http_client.session") as client:
            client.return_value.request.return_value = received
            result = request("GET", "https://benuanta.co.id/")
        self.assertEqual(result.json(), {"ok": True})

    def test_no_retry_for_403(self):
        client = MagicMock()
        client.request.return_value = response(status=403)
        with patch("helper.http_client.session", return_value=client), self.assertRaises(FetchError):
            request("GET", "https://benuanta.co.id/")
        self.assertEqual(client.request.call_count, 1)

    def test_trickling_response_stops_at_deadline(self):
        clock = [0.0]
        received = response()

        def drip(*args, **kwargs):
            clock[0] = 46.0
            return b"x"

        received.raw.read1.side_effect = drip
        with patch("helper.http_client.time.monotonic", side_effect=lambda: clock[0]), \
                patch("helper.http_client.session") as client:
            client.return_value.request.return_value = received
            with self.assertRaises(FetchError):
                request("GET", "https://benuanta.co.id/")
        self.assertEqual(received.raw.read1.call_count, 1)


class ExportTests(unittest.TestCase):
    def test_all_sheets_write_external_values_as_text(self):
        frame = pd.DataFrame({"Judul": ["=1+1", "#N/A", "+1", "@test"]})
        reports = [{"source": "=1+1", "issues": [{"code": "=1+1", "stage": "content", "message": "=1+1"}]}]
        book = load_workbook(io.BytesIO(dataframe_to_excel_bytes(frame, {"x": "=1+1"}, reports)))
        self.assertEqual(book["Berita"]["A2"].value, "=1+1")
        self.assertEqual(book["Berita"]["A3"].value, "#N/A")
        for sheet in book:
            for row in sheet:
                for cell in row:
                    self.assertNotEqual(cell.data_type, "f")
                    self.assertNotEqual(cell.data_type, "e")

    def test_long_unicode_text_is_reconstructable(self):
        text = "a" * 40000 + "\U0001f600" * 20000
        book = load_workbook(io.BytesIO(dataframe_to_excel_bytes(pd.DataFrame({"Isi": [text]}))))
        rebuilt = book["Berita"]["A2"].value
        for _, _, _, extra in list(book["Teks Lanjutan"].values)[1:]:
            rebuilt += extra
        self.assertEqual(rebuilt, text)
        for sheet in book:
            for row in sheet:
                for cell in row:
                    if isinstance(cell.value, str):
                        self.assertLessEqual(len(cell.value.encode("utf-16-le")) // 2, 32767)

    def test_control_characters_preserved_as_documented_escapes(self):
        original = "abc\x01def\\u0001\ufffe"
        book = load_workbook(io.BytesIO(dataframe_to_excel_bytes(pd.DataFrame({"Isi": [original]}))))
        self.assertEqual(book["Berita"]["A2"].value, r"abc\u0001def\\u0001\ufffe")
        self.assertIn("Metadata", book.sheetnames)

    def test_literal_search_and_optional_columns(self):
        frame = pd.DataFrame({"Judul": ["A+B", "[uji]", "Titik.", None]})
        self.assertEqual(filter_dataframe(frame, "[")["Judul"].tolist(), ["[uji]"])
        self.assertEqual(filter_dataframe(frame, ".")["Judul"].tolist(), ["Titik."])
        self.assertEqual(filter_dataframe(frame, "a+b")["Judul"].tolist(), ["A+B"])
        self.assertTrue(filter_dataframe(frame, "tidak ada").empty)
