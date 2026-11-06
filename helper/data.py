"""Pure transformations and lossless, text-only spreadsheet export."""
from datetime import datetime
from io import BytesIO
import json
import re

import pandas as pd
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

ORDER = ["Tanggal", "Sumber", "Tagar", "Judul", "Ringkasan", "Isi", "Tautan"]
EXCEL_CHARS = 30000  # Below both the character and UTF-16 cell limits.


def build_summary(text, max_sentences=2, max_chars=320):
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return None
    summary = " ".join(re.split(r"(?<=[.!?])\s+", normalized)[:max_sentences])
    if len(summary) > max_chars:
        summary = summary[:max_chars - 3].rsplit(" ", 1)[0].rstrip(".,;:") + "..."
    return summary


def enrich_scraped_data(rows):
    return [dict(row, Ringkasan=build_summary(row.get("Isi"))) for row in rows]


def format_date_value(value):
    if value is None:
        return value
    text = str(value).strip()
    for pattern in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, pattern).strftime("%d-%m-%Y")
        except ValueError:
            pass
    return text


def format_date_column(df):
    output = df.copy()
    if "Tanggal" in output:
        output["Tanggal"] = output["Tanggal"].map(format_date_value)
    return output


def build_export_dataframe(df):
    columns = [c for c in ORDER if c in df] + [c for c in df if c not in ORDER]
    return format_date_column(df[columns])


def filter_dataframe(df, keyword="", categories=()):
    mask = pd.Series(True, index=df.index)
    if keyword:
        matches = pd.Series(False, index=df.index)
        for column in ("Judul", "Tagar", "Isi"):
            if column in df:
                matches |= df[column].astype("string").str.contains(keyword, case=False, regex=False, na=False)
        mask &= matches
    if categories and "Tagar" in df:
        mask &= df["Tagar"].isin(categories)
    return df.loc[mask].copy()


def _xml_text(value):
    # Encode forbidden XML characters visibly and reversibly; never discard them.
    text = str(value)
    text = text.replace("\\", "\\\\")
    text = ILLEGAL_CHARACTERS_RE.sub(lambda m: f"\\u{ord(m[0]):04x}", text)
    return "".join(f"\\u{ord(c):04x}" if 0xD800 <= ord(c) <= 0xDFFF or ord(c) in (0xFFFE, 0xFFFF)
                   else c for c in text)


def _parts(text):
    # Excel counts supplementary characters as two UTF-16 code units.
    parts, buffer, units = [], [], 0
    for char in text:
        width = 2 if ord(char) > 0xFFFF else 1
        if units + width > EXCEL_CHARS:
            parts.append("".join(buffer))
            buffer, units = [], 0
        buffer.append(char)
        units += width
    parts.append("".join(buffer))
    return parts


def _append_text(sheet, values):
    sheet.append([None] * len(values))
    for index, value in enumerate(values, 1):
        if value is not None:
            cell = sheet.cell(sheet.max_row, index)
            # Assign the final cell type after setting value: openpyxl otherwise
            # infers a leading '=' as formula, or '#N/A' as an error cell.
            cell.value = value
            cell.data_type = "s"


def dataframe_to_excel_bytes(df, metadata=None, reports=None):
    """Preserve all text, splitting long cells into a reconstructable extra sheet.

    Control characters and literal backslashes use a documented reversible
    escape scheme. JSON download preserves the original data directly.
    """
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Berita"
    continuation = workbook.create_sheet("Teks Lanjutan")
    _append_text(sheet, [_xml_text(c) for c in df.columns])
    _append_text(continuation, ["Baris Excel", "Kolom", "Bagian", "Teks"])
    modified = 0
    for number, row in enumerate(df.itertuples(index=False, name=None), 2):
        values = []
        for column, value in zip(df.columns, row):
            if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
                values.append(None)
                continue
            text = _xml_text(value)
            parts = _parts(text)
            modified += int(text != str(value) or len(parts) > 1)
            values.append(parts[0])
            for part_number, part in enumerate(parts[1:], 2):
                _append_text(continuation, [str(number), _xml_text(column), str(part_number), part])
        _append_text(sheet, values)
    if continuation.max_row == 1:
        workbook.remove(continuation)
    info = workbook.create_sheet("Metadata")
    _append_text(info, ["Kunci", "Nilai"])
    details = {**(metadata or {}), "Jumlah baris ekspor": len(df), "Sel dipecah atau di-escape": modified,
               "Aturan teks": "Untuk membaca teks lengkap, sambungkan sel utama dengan Teks Lanjutan "
                              "sesuai nomor baris, kolom, dan bagian. Dua backslash berarti satu backslash. "
                              "Satu backslash diikuti huruf u dan empat digit heksadesimal mewakili karakter "
                              "yang tidak bisa ditulis langsung ke Excel. Teks aslinya ada di file JSON.",
               "Ringkasan": "Diambil dari kalimat awal berita."}
    for key, value in details.items():
        text = _xml_text(json.dumps(value, ensure_ascii=True) if isinstance(value, (dict, list)) else value)
        for part in _parts(text):
            _append_text(info, [_xml_text(key), part])
    errors = workbook.create_sheet("Galat Sumber")
    _append_text(errors, ["Sumber", "Tahap", "Kode", "ID Artikel", "Pesan"])
    for report in reports or []:
        for issue in report.get("issues", []):
            _append_text(errors, [_xml_text(value) for value in [report["source"], issue["stage"],
                         issue["code"], issue.get("article_id", ""), issue["message"]]])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
