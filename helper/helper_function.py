import pandas as pd
import re

from helper.http_client import request

BLOCKED_RESPONSE_MARKERS = (
    "<title>tribunnews.com - 403</title>",
    "you don't have permission for this request",
    'var statuscode = "403"',
    '"http_error"',
)

# Data Range
def get_date_range(start_date, end_date):
    """Generate a list fo date strings between start_date and end_date"""
    return pd.date_range(start_date, end_date).strftime('%d-%m-%Y').tolist()

# Fetch Page
def fetch_page(url, retries=2, delay=2, timeout=15, **kwargs):
    """Fetch through the shared safe transport; failures are never empty results."""
    return request("GET", url, retries=retries, timeout=timeout, **kwargs)


def decode_response_text(response):
    """Return response text with a best-effort mojibake repair pass."""
    if response is None:
        return None

    text = response.text
    suspicious_markers = ("â€", "â€™", "â€œ", "â€\x9d", "â€“", "â€”", "Â", "Ã")
    if any(marker in text for marker in suspicious_markers):
        try:
            repaired = text.encode("latin-1").decode("utf-8")
            text = repaired
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

    return text

def is_blocked_response(content):
    """Detect bot-block or deny pages returned as successful HTTP responses."""
    if not content:
        return False

    normalized = str(content).lower()
    return any(marker in normalized for marker in BLOCKED_RESPONSE_MARKERS)

# Mapping Indonesian to English day and month names
def translate_date(raw_date):
    """Translate Indonesian day and month names in a string to English."""
    day_mapping = {
        "Senin": "Monday", "Selasa": "Tuesday", "Rabu": "Wednesday",
        "Kamis": "Thursday", "Jumat": "Friday", "Sabtu": "Saturday",
        "Minggu": "Sunday"
    }
    month_mapping = {
        "Januari": "January", "Februari": "February", "Maret": "March",
        "April": "April", "Mei": "May", "Juni": "June",
        "Juli": "July", "Agustus": "August", "September": "September",
        "Oktober": "October", "November": "November", "Desember": "December"
    }
    
    for indo, eng in {**day_mapping, **month_mapping}.items():
        raw_date = raw_date.replace(indo, eng)
    return raw_date


def normalize_article_text(paragraphs_or_text):
    """Normalize whitespace inside paragraphs without discarding their boundaries."""
    if paragraphs_or_text is None:
        return None

    if isinstance(paragraphs_or_text, (list, tuple)):
        normalized_parts = [
            re.sub(r"\s+", " ", str(part)).strip()
            for part in paragraphs_or_text
            if str(part).strip()
        ]
        text = "\n\n".join(normalized_parts)
    else:
        paragraphs = re.split(r"\n\s*\n", str(paragraphs_or_text))
        text = "\n\n".join(re.sub(r"\s+", " ", paragraph).strip() for paragraph in paragraphs if paragraph.strip())

    return text or None

def build_web_driver():
    """The inactive Tribun browser adapter has not passed network isolation review."""
    raise RuntimeError("Sumber Tribun/browser belum didukung pada runtime aman ini.")


def fetch_with_selenium(url, driver=None, timeout=20, mode="html"):
    raise RuntimeError("Fallback browser dinonaktifkan sampai isolasi jaringannya terverifikasi.")


def fetch_content_with_fallback(url, retries=2, delay=2, timeout=15,
                                driver=None, selenium_timeout=20, mode="html"):
    response = fetch_page(url, retries=retries, timeout=timeout)
    text = decode_response_text(response)
    if is_blocked_response(text):
        raise RuntimeError("Sumber menolak akses; tidak mencoba melewati pembatasan.")
    return text
