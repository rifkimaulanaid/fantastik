"""Streamlit UI; scraping, validation and export live in importable modules."""
from copy import deepcopy
from datetime import datetime
import hashlib
from html import escape
import json
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

from helper.data import build_export_dataframe, dataframe_to_excel_bytes, filter_dataframe, format_date_column
from helper.http_client import UnsafeURL, validate_url
from helper.jobs import DEFAULT_STORE, ScrapeJob, list_checkpoints, load_checkpoint
from helper.models import validate_dates
from helper.pipeline import ACTIVE_SOURCES
from helper.presentation import BUSINESS_ZONE, article_html, human_date, human_time, preset_dates, source_cards, status_label

ROOT = Path(__file__).resolve().parent


def render_app_header():
    st.markdown(
        '<header class="app-header"><div><span class="eyebrow">Fenomena Statistik Kabupaten Bulungan</span>'
        '<h1>Fantastik Bulungan</h1><p>Berita lokal untuk membaca fenomena daerah.</p></div>'
        '<span class="brand-mark" aria-hidden="true">F.</span></header>',
        unsafe_allow_html=True,
    )


def reset_result_filters():
    st.session_state.result_keyword = ""
    st.session_state.result_categories = []
    st.session_state.article_position = 0


def reset_article():
    st.session_state.article_position = 0


def change_preset():
    dates = preset_dates(st.session_state.date_preset, datetime.now(BUSINESS_ZONE).date())
    if dates:
        st.session_state.collect_start, st.session_state.collect_end = dates


def custom_dates():
    st.session_state.date_preset = "Atur tanggal"


def adopt_result(result):
    old = st.session_state.get("active_result")
    if old and old.get("data") and old != result:
        history = st.session_state.get("run_history", [])
        st.session_state.run_history = ([deepcopy(old)] + history)[:3]
    st.session_state.active_result = deepcopy(result)
    st.session_state.export_cache = None
    # Apply widget resets on the next full run, including completion from a fragment.
    st.session_state.reset_results_pending = True


@st.fragment(run_every="1s")
def monitor_job():
    job = st.session_state.get("job")
    if job is None:
        return
    fraction, note, result = job.snapshot()
    st.progress(fraction, text=note)
    if result:
        st.caption(f"{len(result['data'])} berita diperoleh. Hasil disimpan bertahap.")
    if job.storage_error:
        st.warning("Hasil belum dapat disimpan pada perangkat. Data tetap tersedia dalam sesi ini.")
        st.text(job.storage_error)
    if not job.done.is_set():
        if st.button("Batalkan proses", disabled=job.cancel.is_set(), key="cancel_job"):
            job.cancel.set()
            st.rerun()
        if job.cancel.is_set():
            st.caption("Pembatalan diminta. Menunggu pengambilan halaman yang sedang berlangsung selesai.")
        return
    st.session_state.last_attempt = result
    st.session_state.last_job_error = job.error or job.storage_error
    if result and (result["data"] or all(r["status"] == "success" for r in result["reports"])):
        adopt_result(result)
    st.session_state.job = None
    st.rerun()


def render_sidebar():
    with st.sidebar:
        st.image(str(ROOT / "asset/Fantastik_Logo_Teks.png"), width=132)
        st.caption("Pantau berita lokal, telaah fenomena, dan simpan hasilnya.")
        with st.expander("Panduan singkat"):
            st.write("1. Buka **Kumpulkan berita** dan pilih tanggal serta sumber.")
            st.write("2. Cari berita melalui tabel atau baca pada tampilan Detail.")
            st.write("3. Pilih Unduh dan siapkan berkas sesuai filter hasil.")
            st.caption("Hasil parsial berarti sebagian berita atau sumber belum berhasil dikumpulkan.")
        history = st.session_state.get("run_history", [])
        if history:
            with st.expander("Hasil sebelumnya"):
                selected = st.selectbox(
                    "Pilih hasil sebelumnya", range(len(history)), key="history_selection",
                    format_func=lambda i: f"{human_time(history[i]['metadata'].get('started_at'))} ({len(history[i]['data'])} berita)",
                )
                if st.button("Tampilkan hasil sebelumnya"):
                    adopt_result(history[selected])
        files = list_checkpoints(DEFAULT_STORE)[:20]
        if files:
            with st.expander("Hasil tersimpan di perangkat"):
                def file_label(path):
                    try:
                        stamp = datetime.fromtimestamp(path.stat().st_mtime, BUSINESS_ZONE)
                        return f"{human_time(stamp)} ({stamp:%S} detik)"
                    except OSError:
                        return "Berkas tidak tersedia"

                path = st.selectbox("Pilih hasil tersimpan", files, format_func=file_label, key="saved_selection")
                if st.button("Pulihkan hasil tersimpan"):
                    try:
                        adopt_result(load_checkpoint(path))
                    except (OSError, ValueError, KeyError) as error:
                        st.error("Hasil tersimpan belum dapat dibuka.")
                        st.text(str(error))
                st.caption("Pemulihan membuka data yang sudah tersimpan dan tidak mengulang pengumpulan berita.")


def render_collection_filters():
    today = datetime.now(BUSINESS_ZONE).date()
    defaults = dict(collect_start=today, collect_end=today, date_preset="Hari ini",
                    collect_sources=list(ACTIVE_SOURCES))
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    busy = st.session_state.get("job") is not None
    expanded = st.session_state.get("active_result") is None and not busy
    with st.expander("Kumpulkan berita", expanded=expanded, key="collection_panel"):
        st.caption("Filter pengambilan: menentukan berita baru yang akan dikumpulkan.")
        with st.container(horizontal=True, vertical_alignment="bottom", key="collection_dates"):
            st.selectbox("Rentang tanggal", ["Hari ini", "7 hari", "30 hari", "Atur tanggal"],
                         key="date_preset", on_change=change_preset, disabled=busy, width="stretch")
            start = st.date_input("Tanggal awal", key="collect_start", format="DD-MM-YYYY",
                                  on_change=custom_dates, disabled=busy, width="stretch")
            end = st.date_input("Tanggal akhir", key="collect_end", format="DD-MM-YYYY",
                                on_change=custom_dates, disabled=busy, width="stretch")
        sources = st.multiselect("Sumber media", list(ACTIVE_SOURCES), key="collect_sources",
                                 placeholder="Pilih sumber media", disabled=busy)
        validation = None
        try:
            validate_dates(start, end)
        except ValueError as error:
            validation = str(error)
            st.error(validation)
        if not sources:
            st.info("Pilih setidaknya satu sumber media untuk mulai mengumpulkan berita.")
        clicked = st.button("Kumpulkan berita", key="collect_news", type="primary", width="stretch",
                            disabled=busy or bool(validation) or not sources)
        st.caption("Maksimal 31 hari setiap pengambilan. Proses dapat dibatalkan dan hasil yang sudah diperoleh tetap disimpan.")
        if clicked:
            try:
                job = ScrapeJob(start, end, sources)
                job.start()
                st.session_state.job = job
                st.session_state.last_attempt = None
                st.session_state.last_job_error = None
                st.rerun()
            except (ValueError, RuntimeError) as error:
                st.error(str(error))


def render_status_reports(reports):
    st.markdown(source_cards(reports), unsafe_allow_html=True)


def render_diagnostics(result):
    details = st.expander("Rincian pengambilan dan kendala", on_change="rerun", key="source_details")
    if not details.open:
        return
    with details:
        for report in result["reports"]:
            st.text(f"{report['source']} - {status_label(report['status'])}: {report['count']} berita; "
                    f"{report.get('missing_body', 0)} tanpa isi; {report.get('pages', 0)} halaman.")
            if report.get("message"):
                st.text(report["message"])
            if report.get("issues"):
                st.dataframe(pd.DataFrame(report["issues"]), hide_index=True, width="stretch")
        st.caption("Batas per sumber: 200 halaman, 1.000 entri, 8 juta karakter isi, dan target durasi 3 menit. "
                   "Pembatalan diperiksa di antara operasi pengambilan halaman.")
        st.json(result["metadata"], expanded=False)


def move_article(offset):
    st.session_state.article_position += offset


def render_article(shown):
    position = st.session_state.get("article_position", 0)
    if position not in range(len(shown)):
        st.session_state.article_position = 0
    with st.container(horizontal=True, vertical_alignment="bottom", key="article_navigation"):
        st.button("Sebelumnya", key="previous_article", on_click=move_article, args=(-1,),
                  disabled=st.session_state.get("article_position", 0) == 0)
        st.selectbox("Pilih berita", range(len(shown)), key="article_position", width="stretch",
                     format_func=lambda i: f"{i + 1}. {shown.iloc[i].get('Judul', 'Tanpa judul')}")
        st.button("Berikutnya", key="next_article", on_click=move_article, args=(1,),
                  disabled=st.session_state.get("article_position", 0) == len(shown) - 1)
    record = shown.iloc[st.session_state.article_position]
    st.caption(f"Berita {st.session_state.article_position + 1} dari {len(shown)}")
    # Values from news sources are escaped individually before enabling HTML.
    st.markdown(f'<h2 class="article-title">{escape(str(record.get("Judul", "Tanpa judul")))}</h2>', unsafe_allow_html=True)
    st.text(f"{record.get('Sumber', '-')} | Kategori: {record.get('Tagar', '-')} | {human_date(record.get('Tanggal'))}")
    if record.get("Ringkasan"):
        with st.container(key="article_summary"):
            st.caption("Sekilas berita - kalimat awal artikel")
            st.text(record["Ringkasan"])
    if record.get("Isi"):
        st.markdown(article_html(None, record["Isi"]), unsafe_allow_html=True)
    else:
        st.warning("Isi berita belum berhasil diambil. Periksa rincian kendala atau buka artikel sumber.")
    try:
        st.link_button("Buka artikel sumber", validate_url(record.get("Tautan")))
    except UnsafeURL:
        st.caption("Tautan artikel tidak tersedia.")


def render_downloads(filtered, result, keyword, categories):
    st.write(f"Unduh **{len(filtered)} berita** sesuai filter hasil saat ini.")
    st.caption("Excel menyertakan keterangan pengambilan dan kendala sumber. JSON menyimpan data lengkap untuk diolah kembali.")
    export_meta = dict(result["metadata"], filter_keyword=keyword, filter_categories=categories,
                       exported_rows=len(filtered))
    payload = json.dumps(dict(data=filtered.to_dict("records"), metadata=export_meta,
                              reports=result["reports"]), ensure_ascii=True)
    signature = hashlib.sha256(payload.encode()).hexdigest()
    cache = st.session_state.get("export_cache")
    if cache and cache["signature"] != signature:
        st.info("Filter hasil berubah. Siapkan ulang unduhan agar berkas mengikuti hasil yang sedang ditampilkan.")
    if st.button("Siapkan unduhan", key="prepare_download", type="primary", disabled=filtered.empty):
        try:
            with st.spinner("Menyiapkan berkas unduhan..."):
                excel = dataframe_to_excel_bytes(build_export_dataframe(filtered), export_meta, result["reports"])
            cache = dict(signature=signature, excel=excel, json=payload.encode())
            st.session_state.export_cache = cache
        except Exception as error:
            st.error("Berkas belum dapat disiapkan. Hasil berita tetap tersedia.")
            st.caption(f"Kode kendala: {type(error).__name__}")
    if cache and cache["signature"] == signature:
        with st.container(horizontal=True):
            st.download_button("Unduh Excel", cache["excel"], "fantastik.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", on_click="ignore")
            st.download_button("Unduh JSON lengkap", cache["json"], "fantastik.json", "application/json", on_click="ignore")
    with st.expander("Tentang format unduhan"):
        st.write("Teks panjang dalam Excel dilanjutkan pada sheet Teks Lanjutan. Cara membacanya dan "
                 "penulisan karakter khusus dijelaskan pada sheet Metadata. JSON mempertahankan teks asli.")


def render_results(result):
    if st.session_state.pop("reset_results_pending", False):
        reset_result_filters()
    metadata = result["metadata"]
    complete = metadata.get("state") == "complete"
    label = "Lengkap" if complete else "Belum lengkap"
    state_class = "complete" if complete else "incomplete"
    date_range = f"{human_date(metadata.get('requested_start'))} - {human_date(metadata.get('requested_end'))}"
    st.markdown(
        f'<section class="results-heading"><h2>Hasil berita</h2><span class="result-badge {state_class}">{label}</span>'
        f'<p>{escape(date_range)} · Diambil {escape(human_time(metadata.get("started_at")))}</p></section>',
        unsafe_allow_html=True,
    )
    render_status_reports(result["reports"])
    if not result["data"]:
        st.info("Tidak ada berita pada rentang yang berhasil diperiksa. Coba tanggal atau sumber lain melalui Kumpulkan berita.")
        render_diagnostics(result)
        return
    df = pd.DataFrame(result["data"])
    available = sorted(df["Tagar"].dropna().astype(str).unique()) if "Tagar" in df else []
    if "result_categories" in st.session_state:
        st.session_state.result_categories = [c for c in st.session_state.result_categories if c in available]
    with st.container(horizontal=True, vertical_alignment="bottom", key="result_filters"):
        keyword = st.text_input("Cari dalam hasil", key="result_keyword", on_change=reset_article,
                                placeholder="Judul, kategori, atau isi berita", width="stretch")
        categories = st.multiselect("Kategori", available, key="result_categories", on_change=reset_article,
                                     placeholder="Semua kategori", width="stretch")
        if keyword or categories:
            st.button("Hapus filter", key="clear_filters", on_click=reset_result_filters)
    filtered = filter_dataframe(df, keyword, categories)
    shown = format_date_column(filtered)
    sources = filtered["Sumber"].nunique() if "Sumber" in filtered else 0
    category_count = filtered["Tagar"].nunique() if "Tagar" in filtered else 0
    st.markdown(
        f'<dl class="result-metrics"><div><dt>Berita sesuai filter</dt><dd>{len(filtered)}</dd></div>'
        f'<div><dt>Sumber dengan hasil</dt><dd>{sources}</dd></div><div><dt>Kategori</dt><dd>{category_count}</dd></div></dl>',
        unsafe_allow_html=True,
    )
    view = st.radio("Tampilan hasil", ["Tabel", "Detail", "Unduh"], horizontal=True, key="result_view", label_visibility="collapsed")
    if shown.empty:
        st.info("Tidak ada berita yang cocok. Ubah kata kunci/kategori atau pilih Hapus filter.")
    if view == "Tabel" and not shown.empty:
        display_columns = [c for c in ["Judul", "Tanggal", "Sumber", "Tagar", "Ringkasan", "Status Isi", "Tautan"] if c in shown]
        safe = shown[display_columns].copy()
        if "Tautan" in safe:
            def safe_link(value):
                try:
                    return validate_url(value)
                except UnsafeURL:
                    return None
            safe["Tautan"] = safe["Tautan"].map(safe_link)
        st.dataframe(safe, hide_index=True, width="stretch", key="news_table",
                     column_config={"Tagar": st.column_config.TextColumn("Kategori"),
                                    "Tautan": st.column_config.LinkColumn("Sumber asli", display_text="Buka artikel"),
                                    "Judul": st.column_config.TextColumn("Judul", width="large"),
                                    "Ringkasan": st.column_config.TextColumn("Sekilas berita", width="large")})
    elif view == "Detail" and not shown.empty:
        render_article(shown)
    elif view == "Unduh":
        render_downloads(filtered, result, keyword, categories)
    render_diagnostics(result)


def main():
    with Image.open(ROOT / "asset/LOGO-BPS.png") as icon:
        st.set_page_config(page_title="Fantastik Bulungan", page_icon=icon.copy(), layout="wide")
    st.markdown("<style>" + (ROOT / "styles/style.css").read_text(encoding="utf-8") + "</style>", unsafe_allow_html=True)
    render_sidebar()
    render_app_header()
    render_collection_filters()
    monitor_job()
    if st.session_state.get("last_job_error"):
        st.error("Pengambilan terbaru mengalami kendala. Data yang sudah tersedia tetap dipertahankan.")
        with st.expander("Rincian kendala proses"):
            st.text(st.session_state.last_job_error)
    active = st.session_state.get("active_result")
    attempt = st.session_state.get("last_attempt")
    if attempt and active != attempt and not attempt.get("data"):
        st.warning("Pengambilan terbaru belum berhasil. Anda sedang melihat hasil sebelumnya.")
        with st.expander("Status pengambilan terbaru"):
            render_status_reports(attempt["reports"])
            for report in attempt["reports"]:
                if report.get("message"):
                    st.text(report["message"])
    if active:
        if st.session_state.get("job"):
            st.caption("Pengambilan baru sedang berlangsung. Hasil di bawah berasal dari pengambilan sebelumnya.")
        render_results(active)
    elif not st.session_state.get("job"):
        st.info("Pilih tanggal dan sumber pada Kumpulkan berita untuk mulai. Hasil akan tampil di sini.")


if __name__ == "__main__":
    main()
