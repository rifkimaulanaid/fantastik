"""Synthetic news only; browser checks must never trigger production scraping."""
from helper.data import enrich_scraped_data


def preview_result():
    rows = []
    for index in range(40):
        rows.append({"Judul": f"Berita contoh {index + 1}: Kegiatan ekonomi dan usaha masyarakat",
                     "Tagar": ("Ekonomi", "Pendidikan", "Pertanian")[index % 3],
                     "Sumber": "Prokal", "Tanggal": "2026-11-06", "Status Isi": "lengkap",
                     "Tautan": "https://www.prokal.co/ekonomi/123/berita-contoh",
                     "Isi": "Paragraf pertama dari data contoh untuk menguji tampilan berita. " * 5
                            + "\n\n" + "Paragraf kedua tetap mempertahankan pemisah yang tersedia pada data asli. " * 5})
    return {"data": enrich_scraped_data(rows), "reports": [
        {"source": "Prokal", "count": 40, "missing_body": 0, "pages": 2, "status": "success", "issues": []},
        {"source": "Benuanta", "count": 0, "missing_body": 0, "pages": 0, "status": "failed",
         "message": "Pengambilan sumber gagal (HTTP 503).", "issues": [
             {"code": "FETCH_FAILED", "stage": "pagination", "message": "Pengambilan sumber gagal (HTTP 503).", "article_id": ""}]},
        {"source": "Radar Tarakan", "count": 0, "missing_body": 0, "pages": 0, "status": "success", "issues": []},
    ], "metadata": {"run_id": "contoh-ui", "state": "incomplete", "started_at": "2026-11-06T10:00:00+08:00",
                    "requested_start": "2026-11-01", "requested_end": "2026-11-06",
                    "requested_sources": ["Prokal", "Benuanta", "Radar Tarakan"]}}
