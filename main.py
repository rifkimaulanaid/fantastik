import streamlit as st
from datetime import date
import pandas as pd
from PIL import Image
import os

from helper.helper_function import get_date_range
from scrap.radartarakan import radar_scrap
from scrap.tribunkaltara import tribun_scrap
from scrap.prokal import prokal_scrap
from scrap.benuanta import benuanta_scrap

# Initialize session state to store the DataFrame
if 'scraped_df' not in st.session_state:
    st.session_state.scraped_df = None

# Page Configuration
st.set_page_config(
    page_title="Fantastik Bulungan", 
    page_icon=Image.open('./asset/Fantastik_Logo.png'), layout="wide"
    )

# Function to load CSS file
def local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    else:
        st.warning(f"File CSS {file_name} tidak ditemukan.")

# Load the CSS file
local_css("styles/style.css")

# Unified Scrape Function
def scrape_news(start_date, end_date, selected_sources):
    all_data = []
    total = len(selected_sources)
    progress_bar = st.progress(0)

    for idx, source in enumerate(selected_sources):
        if source == "Kaltara Tribunnews":
            dates_to_scrape = get_date_range(start_date, end_date)
            all_data.extend(tribun_scrap(dates_to_scrape))
        elif source == "Benuanta":
            all_data.extend(benuanta_scrap(start_date, end_date))
        elif source == "Prokal":
            all_data.extend(prokal_scrap(start_date, end_date))
        elif source == "Radar Tarakan":
            all_data.extend(radar_scrap(start_date, end_date))
        
        progress_bar.progress((idx + 1)/total)
    
    progress_bar.empty()
    return all_data

# Sidebar for User Input
with st.sidebar:
    st.image('./asset/Fantastik_Logo_Teks.png', width=400)
    st.subheader('Pilih Rentang Tanggal')
    start_date = st.date_input("Tanggal Awal", date.today())
    end_date = st.date_input("Tanggal Akhir", date.today())
    news_sources = st.multiselect("Sumber Media", ["Kaltara Tribunnews","Benuanta","Prokal","Radar Tarakan"])

    if start_date > end_date:
        st.error("Tanggal awal tidak boleh lebih dari tanggal akhir.")
    elif not news_sources:
        st.warning("Silakan pilih minimal satu sumber media.")
    elif st.button("Proses"):
        with st.spinner("Proses scraping berita..."):
            scraped_data = scrape_news(start_date, end_date, news_sources)
            if scraped_data:
                st.success(f"Scraped {len(scraped_data)} Berita Berhasil!")
                st.session_state.scraped_df = pd.DataFrame(scraped_data)
            else:
                st.warning("Tidak Ada Berita Ditemukan")

# Overview
with st.expander("**FANSTASTIK BULUNGAN**", expanded=True):
    st.write("""
    **FANTASTIK BULUNGAN** atau **Fenomena Statistik Kabupaten Bulungan** merupakan aplikasi yang dikembangkan untuk mengumpulkan informasi dari media massa *online* yang nantinya dapat digunakan sebagai sumber pendukung fenomena statistik yang terjadi pada suatu waktu.
    Adapun media massa *online* yang dapat dikumpulkan informasinya merupakan media massa lokal setempat seperti Kaltara Tribunnews, Benuanta, Prokal, dan Radar Tarakan.
    """)

# Usage Instruction
with st.expander("**CARA PENGGUNAAN**", expanded=True):
    st.write("""
    1. Pilih rentang tanggal yang diinginkan: **Tanggal Awal** dan **Tanggal Akhir**
    2. Pilih **Sumber Media** yang diinginkan
    3. Klik tombol **Proses** untuk memulai *scraping* berita yang sudah dipilih
    4. Hasil akan ditampilkan dalam bentuk tabel yang dapat diunduh dalam format CSV
    5. **Perhatian!!** Proses *scraping* dapat memerlukan waktu beberapa menit tergantung jumlah berita yang berhasil diproses
    """)

# Display Result
if st.session_state.scraped_df is not None:
    df = st.session_state.scraped_df

    # Filter UI
    with st.expander("**🔎 PENCARIAN BERITA**", expanded=True):
        keyword = st.text_input("Cari kata kunci dalam Judul/Isi", value="")

        categories = []
        if "Kategori" in df.columns:
            categories = df["Kategori"].dropna().unique().tolist()
            selected_categories = st.multiselect("Filter berdasarkan kategori", categories)
        else:
            selected_categories = []
    
    # Filtering Logic
    filtered_df = df.copy()

    if keyword:
        keyword = keyword.lower()
        filtered_df = filtered_df[
            filtered_df["Judul"].str.lower().str.contains(keyword) |
            filtered_df["Tagar"].str.lower().str.contains(keyword)
        ]
    
    if selected_categories:
        filtered_df = filtered_df[filtered_df["Kategori"].isin(selected_categories)]
    
    # Download and Display
    csv = filtered_df.to_csv(index=False)
    st.download_button("**Download CSV**", csv, "fantastik.csv", "text/csv")

    def make_clickable(url):
        return f'<a href="{url}" target="_blank">{url}</a>'

    filtered_df = filtered_df.copy()
    filtered_df["Tautan"] = filtered_df["Tautan"].apply(make_clickable)

    st.write(filtered_df.to_html(escape=False, index=False), unsafe_allow_html=True)