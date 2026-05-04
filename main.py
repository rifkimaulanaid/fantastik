import os
import re
from datetime import date, datetime
from io import BytesIO

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

from scrap.benuanta import benuanta_scrap
from scrap.prokal import prokal_scrap
from scrap.radartarakan import radar_scrap

ACTIVE_SOURCES = {
    "Benuanta": benuanta_scrap,
    "Prokal": prokal_scrap,
    "Radar Tarakan": radar_scrap,
}

DATE_STORAGE_FORMAT = "%Y-%m-%d"
DATE_DISPLAY_FORMAT = "%d-%m-%Y"
SUMMARY_MAX_CHARS = 320
SUMMARY_MAX_SENTENCES = 2

if "scraped_df" not in st.session_state:
    st.session_state.scraped_df = None
if "scrape_reports" not in st.session_state:
    st.session_state.scrape_reports = []

st.set_page_config(
    page_title="Fantastik Bulungan",
    page_icon=Image.open("./asset/LOGO-BPS.png"),
    layout="wide",
)


def local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name, encoding="utf-8") as file:
            st.markdown(f"<style>{file.read()}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"File CSS {file_name} tidak ditemukan.")


def build_summary(text, max_sentences=SUMMARY_MAX_SENTENCES, max_chars=SUMMARY_MAX_CHARS):
    """Create a short summary from article content using the leading sentences."""
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return None

    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    selected = []
    current_length = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        selected.append(sentence)
        current_length += len(sentence)
        if len(selected) >= max_sentences or current_length >= max_chars:
            break

    summary = " ".join(selected).strip()
    if len(summary) > max_chars:
        summary = summary[:max_chars].rsplit(" ", 1)[0].rstrip(".,;:") + "..."

    return summary or normalized[:max_chars]


def enrich_scraped_data(rows):
    """Add derived fields such as Ringkasan while keeping original full text intact."""
    enriched_rows = []
    for row in rows:
        enriched_row = dict(row)
        enriched_row["Ringkasan"] = build_summary(enriched_row.get("Isi"))
        enriched_rows.append(enriched_row)
    return enriched_rows


def build_export_dataframe(df):
    """Order export columns consistently while keeping all available data."""
    preferred_order = ["Tanggal", "Sumber", "Tagar", "Judul", "Ringkasan", "Isi", "Tautan"]
    ordered_columns = [column for column in preferred_order if column in df.columns]
    remaining_columns = [column for column in df.columns if column not in ordered_columns]
    ordered_df = df[ordered_columns + remaining_columns].copy()
    return format_date_column(ordered_df)


def dataframe_to_excel_bytes(df):
    """Convert a DataFrame to an Excel file in memory."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Berita")
    buffer.seek(0)
    return buffer.getvalue()


def format_date_value(value):
    """Convert YYYY-MM-DD values to DD-MM-YYYY for presentation."""
    if value is None or value == "":
        return value

    text = str(value).strip()
    for date_format in (DATE_STORAGE_FORMAT, DATE_DISPLAY_FORMAT):
        try:
            return datetime.strptime(text, date_format).strftime(DATE_DISPLAY_FORMAT)
        except ValueError:
            continue

    return text


def format_date_column(df):
    """Return a copy with formatted Tanggal values for UI/export."""
    formatted_df = df.copy()
    if "Tanggal" in formatted_df.columns:
        formatted_df["Tanggal"] = formatted_df["Tanggal"].apply(format_date_value)
    return formatted_df


def inject_ui_translations():
    """Translate built-in Streamlit UI text that is not exposed in Python API."""
    components.html(
        """
        <script>
        const translateText = () => {
            const root = window.parent.document;
            if (!root) {
                return;
            }

            root.querySelectorAll("div, span, label").forEach((node) => {
                if (!node || node.children.length > 0) {
                    return;
                }

                const text = node.textContent ? node.textContent.trim() : "";
                if (text === "Select all") {
                    node.textContent = "Pilih Semua";
                }
            });
        };

        translateText();
        const observer = new MutationObserver(translateText);
        observer.observe(window.parent.document.body, { childList: true, subtree: true });
        </script>
        """,
        height=0,
        width=0,
    )


def render_app_header():
    source_pills = "".join(
        f'<span class="source-pill">{source}</span>'
        for source in ACTIVE_SOURCES
    )
    st.markdown(
        f"""
        <section class="app-hero">
            <div class="hero-copy">
                <span class="eyebrow">Fenomena Statistik Kabupaten Bulungan</span>
                <h1>Fantastik Bulungan</h1>
                <p>
                    Kumpulkan berita lokal dari beberapa portal media untuk mendukung
                    pemantauan fenomena statistik menurut waktu, kategori, dan isi berita.
                </p>
                <div class="source-pill-row">{source_pills}</div>
            </div>
            <div class="hero-panel">
                <h3>Alur Singkat</h3>
                <ol>
                    <li>Tentukan tanggal awal dan tanggal akhir di sidebar.</li>
                    <li>Pilih satu atau beberapa sumber media aktif.</li>
                    <li>Jalankan proses scraping lalu telaah hasil pada tabel dan detail berita.</li>
                    <li>Unduh hasil akhir dalam format Excel jika diperlukan.</li>
                </ol>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(label, value, help_text):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-help">{help_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_reports(reports):
    if not reports:
        return

    st.markdown("### Status Sumber")
    columns = st.columns(len(reports))
    for column, report in zip(columns, reports):
        status_class = f"status-{report['status']}"
        if report["status"] == "error":
            detail = report["message"] or "Gagal diproses."
        elif report["count"] == 0:
            detail = "Tidak ada berita pada rentang tanggal ini."
        else:
            detail = f"{report['count']} berita berhasil dikumpulkan."

        with column:
            st.markdown(
                f"""
                <div class="status-card {status_class}">
                    <div class="status-source">{report["source"]}</div>
                    <div class="status-detail">{detail}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_empty_state():
    st.markdown(
        """
        <section class="empty-state">
            <h3>Belum Ada Hasil Scraping</h3>
            <p>
                Atur filter pada sidebar, pilih sumber media yang dibutuhkan, lalu klik
                <strong>Proses</strong> untuk menampilkan hasil scraping.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )


local_css("styles/style.css")


def scrape_news(start_date, end_date, selected_sources, progress_bar=None, progress_note=None):
    all_data = []
    source_reports = []
    total_sources = max(len(selected_sources), 1)

    for index, source in enumerate(selected_sources):
        scraper = ACTIVE_SOURCES[source]

        def update_source_progress(local_progress, detail):
            if progress_bar is None:
                return

            bounded_local_progress = max(0.0, min(local_progress, 1.0))
            absolute_progress = int(
                round(((index + bounded_local_progress) / total_sources) * 100)
            )
            progress_bar.progress(
                min(absolute_progress, 100),
                text=f"{source}: {detail}",
            )
            if progress_note is not None:
                progress_note.markdown(
                    f"""
                    <div class="progress-note">
                        <strong>{source}</strong><br>
                        {detail}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        try:
            update_source_progress(0.03, "Memulai proses scraping.")
            source_data = scraper(
                start_date,
                end_date,
                progress_callback=update_source_progress,
            )
            all_data.extend(source_data)
            source_reports.append(
                {
                    "source": source,
                    "status": "success",
                    "count": len(source_data),
                    "message": None,
                }
            )
        except Exception as error:
            error_message = str(error)
            print(f"[ERROR] Scraping failed for {source}: {error_message}")
            update_source_progress(1.0, "Gagal diproses.")
            source_reports.append(
                {
                    "source": source,
                    "status": "error",
                    "count": 0,
                    "message": error_message,
                }
            )

    all_data.sort(
        key=lambda item: (
            item.get("Tanggal", ""),
            item.get("Judul", ""),
        ),
        reverse=True,
    )

    result = {
        "data": enrich_scraped_data(all_data),
        "reports": source_reports,
    }
    if progress_bar is not None:
        progress_bar.progress(100, text="Scraping selesai.")
    if progress_note is not None:
        total_articles = len(result["data"])
        progress_note.markdown(
            f"""
            <div class="progress-note progress-note-complete">
                <strong>Scraping selesai</strong><br>
                Total {total_articles} berita berhasil dikumpulkan dari {len(selected_sources)} sumber.
            </div>
            """,
            unsafe_allow_html=True,
        )
    return result


with st.sidebar:
    st.image("./asset/Fantastik_Logo_Teks.png", use_container_width=True)
    st.markdown("## Filter Scraping")
    st.caption("Tentukan rentang tanggal dan sumber berita yang ingin diproses.")
    start_date = st.date_input("Tanggal Awal", date.today(), format="DD-MM-YYYY")
    end_date = st.date_input("Tanggal Akhir", date.today(), format="DD-MM-YYYY")
    news_sources = st.multiselect(
        "Sumber Media",
        list(ACTIVE_SOURCES),
        placeholder="Pilih sumber media",
    )
    process_clicked = st.button("Proses", use_container_width=True)

    st.markdown(
        """
        <div class="sidebar-note">
            <strong>Catatan</strong><br>
            Proses scraping dapat memerlukan beberapa menit jika jumlah berita pada
            rentang tanggal yang dipilih cukup banyak.
        </div>
        """,
        unsafe_allow_html=True,
    )


render_app_header()
inject_ui_translations()
progress_bar_placeholder = st.empty()
progress_note_placeholder = st.empty()

if start_date > end_date:
    st.error("Tanggal awal tidak boleh lebih dari tanggal akhir.")
elif process_clicked and not news_sources:
    st.warning("Silakan pilih minimal satu sumber media.")
elif process_clicked:
    progress_bar = progress_bar_placeholder.progress(0, text="Menyiapkan proses scraping...")
    scrape_result = scrape_news(
        start_date,
        end_date,
        news_sources,
        progress_bar=progress_bar,
        progress_note=progress_note_placeholder,
    )
    scraped_data = scrape_result["data"]
    st.session_state.scrape_reports = scrape_result["reports"]

    if scraped_data:
        st.session_state.scraped_df = pd.DataFrame(scraped_data)
    else:
        st.session_state.scraped_df = None


if st.session_state.scrape_reports:
    render_status_reports(st.session_state.scrape_reports)
    has_errors = any(report["status"] == "error" for report in st.session_state.scrape_reports)
    total_results = sum(report["count"] for report in st.session_state.scrape_reports)
    if total_results == 0 and has_errors:
        st.warning("Scraping selesai, tetapi ada sumber yang gagal diproses.")
    elif total_results == 0:
        st.info("Tidak ada berita yang cocok dengan rentang tanggal yang dipilih.")


if st.session_state.scraped_df is None:
    render_empty_state()
else:
    df = st.session_state.scraped_df.copy()

    filter_col1, filter_col2 = st.columns([2.4, 1.6])
    with filter_col1:
        keyword = st.text_input("Cari kata kunci dalam Judul atau Isi", value="")
    with filter_col2:
        if "Tagar" in df.columns:
            categories = sorted(df["Tagar"].dropna().unique().tolist())
            selected_categories = st.multiselect("Filter kategori", categories)
        else:
            selected_categories = []

    filtered_df = df.copy()

    if keyword:
        keyword = keyword.lower()
        filtered_df = filtered_df[
            filtered_df["Judul"].str.lower().str.contains(keyword, na=False)
            | filtered_df["Tagar"].str.lower().str.contains(keyword, na=False)
            | filtered_df.get("Isi", pd.Series(index=filtered_df.index, dtype="object"))
            .str.lower()
            .str.contains(keyword, na=False)
        ]

    if selected_categories:
        filtered_df = filtered_df[filtered_df["Tagar"].isin(selected_categories)]

    presented_df = format_date_column(filtered_df)
    unique_sources = filtered_df["Sumber"].nunique() if "Sumber" in filtered_df.columns else 0
    unique_categories = filtered_df["Tagar"].dropna().nunique() if "Tagar" in filtered_df.columns else 0

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    with metric_col1:
        render_metric_card("Total Berita", len(filtered_df), "Jumlah berita setelah filter diterapkan.")
    with metric_col2:
        render_metric_card("Sumber Aktif", unique_sources, "Sumber media yang berkontribusi pada hasil saat ini.")
    with metric_col3:
        render_metric_card("Kategori", unique_categories, "Jumlah kategori atau tagar yang muncul pada hasil.")

    tabs = st.tabs(["Tabel", "Detail", "Unduh"])

    with tabs[0]:
        st.markdown("### Hasil Tabel")
        display_columns = [
            column
            for column in ["Tanggal", "Sumber", "Tagar", "Judul", "Ringkasan", "Tautan"]
            if column in presented_df.columns
        ]
        display_df = presented_df[display_columns].copy()
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Tautan": st.column_config.LinkColumn("Tautan"),
                "Ringkasan": st.column_config.TextColumn("Ringkasan", width="large"),
                "Judul": st.column_config.TextColumn("Judul", width="large"),
            },
        )

    with tabs[1]:
        st.markdown("### Detail Berita")
        if presented_df.empty:
            st.info("Tidak ada berita yang cocok dengan filter pencarian.")
        else:
            for _, row in presented_df.iterrows():
                expander_title = f"{row.get('Tanggal', '-')} | {row.get('Judul', '-')}"
                with st.expander(expander_title):
                    meta_col1, meta_col2 = st.columns([1.1, 2.4])
                    with meta_col1:
                        st.markdown(
                            f"""
                            <div class="detail-meta-card">
                                <div><strong>Sumber</strong><br>{row.get("Sumber", "-")}</div>
                                <div><strong>Tagar</strong><br>{row.get("Tagar", "-")}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    with meta_col2:
                        if row.get("Ringkasan"):
                            st.markdown("**Ringkasan**")
                            st.write(row.get("Ringkasan"))
                        st.markdown(f"**Tautan**: [{row.get('Tautan', '-')}]({row.get('Tautan', '#')})")
                    st.markdown("**Isi Berita**")
                    st.write(row.get("Isi") or "-")

    with tabs[2]:
        st.markdown("### Unduh Hasil")
        export_df = build_export_dataframe(filtered_df)
        st.write(
            "Unduhan Excel akan mengikuti hasil yang sedang tampil setelah filter kata kunci dan kategori diterapkan."
        )
        try:
            excel_bytes = dataframe_to_excel_bytes(export_df)
            st.download_button(
                "Download Excel",
                excel_bytes,
                "fantastik.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except ModuleNotFoundError:
            st.info("Download Excel membutuhkan package `openpyxl`.")
