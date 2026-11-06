"""Human-readable labels and safe HTML for the UI; stored data stays intact."""
from datetime import date, datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo

MONTHS = ("", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
          "Agustus", "September", "Oktober", "November", "Desember")
BUSINESS_ZONE = ZoneInfo("Asia/Makassar")


def human_date(value):
    try:
        if isinstance(value, datetime):
            value = value.date()
        elif not isinstance(value, date):
            text = str(value)
            value = datetime.strptime(text, "%d-%m-%Y" if len(text) == 10 and text[2] == "-" else "%Y-%m-%d").date()
        return f"{value.day} {MONTHS[value.month]} {value.year}"
    except (ValueError, TypeError):
        return "Tanggal tidak tersedia"


def human_time(value):
    try:
        stamp = datetime.fromisoformat(str(value))
        if stamp.tzinfo is not None:
            stamp = stamp.astimezone(BUSINESS_ZONE)
        return f"{human_date(stamp)}, {stamp:%H.%M} WITA"
    except (ValueError, TypeError):
        return "Waktu tidak tersedia"


def preset_dates(preset, today):
    days = {"Hari ini": 1, "7 hari": 7, "30 hari": 30}.get(preset)
    return (today - timedelta(days=days - 1), today) if days else None


def status_label(status):
    return {"success": "Lengkap", "partial": "Sebagian", "failed": "Gagal"}.get(status, "Belum lengkap")


def source_cards(reports):
    cards = []
    for report in reports:
        status = report.get("status")
        status = status if status in {"success", "partial", "failed"} else "partial"
        missing = int(report.get("missing_body", 0))
        note = f"{int(report.get('count', 0))} berita"
        if missing:
            note += f" · {missing} tanpa isi"
        cards.append(
            f'<div class="source-status source-{status}">'
            f'<strong>{escape(str(report.get("source", "Sumber")))}</strong>'
            f'<span class="source-state">{status_label(status)}</span>'
            f'<span class="source-count">{escape(note)}</span></div>'
        )
    return '<div class="source-status-grid" role="group" aria-label="Status sumber">' + "".join(cards) + "</div>"


def article_html(title, body):
    """Escape remote text before allowing HTML; retain only existing line breaks."""
    heading = f'<h2>{escape(str(title or "Tanpa judul"))}</h2>' if title is not None else ""
    return (f'<article class="article-reader">{heading}'
            f'<div class="article-body">{escape(str(body or "Isi belum berhasil diambil."))}</div></article>')
