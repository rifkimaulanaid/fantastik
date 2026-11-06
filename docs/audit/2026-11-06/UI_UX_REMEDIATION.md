# Perbaikan UI/UX — 6 November 2026

Perbaikan telah diterapkan pada workspace dan diverifikasi di browser lokal menggunakan data sintetis. Tidak menjalankan pengumpulan berita produksi atau deployment server pada tahap ini.

## Perubahan

- **Tanggal terbaca:** aturan warna universal sidebar dihapus, elemen tanggal diberi warna teks yang jelas, serta indikator fokus keyboard ditambahkan. Kontras tanggal terukur **11,08:1**, dari sekitar 1:1; tombol aksi utama **7,92:1**.
- **Hasil lebih cepat dijangkau:** header menjadi ringkas, panduan dipindahkan ke bagian bantuan, dan status sumber ditampilkan dalam kartu pendek dengan label teks. Rincian kendala/metadata dibuka saat diperlukan, tanpa memenuhi layar hasil.
- **Filter tersedia di ponsel:** panel Kumpulkan berita berada di area utama, dengan Hari ini, 7 hari, 30 hari, atau tanggal pilihan. Validasi tanggal/sumber tetap dilakukan sebelum pekerjaan dapat dimulai.
- **Konteks lebih jelas:** filter pengambilan dipisahkan dari filter hasil. Metrik kini bernama Sumber dengan hasil. Waktu ditampilkan dalam format Indonesia/WITA. Label Kategori dan Unduh digunakan secara konsisten; nama kolom data tersimpan tetap kompatibel.
- **Membaca lebih nyaman:** judul menjadi kolom pertama tabel; detail memiliki judul jelas, navigasi sebelumnya/berikutnya, ringkasan, lebar baca terbatas, dan jarak baris yang lebih lega. Teks eksternal tetap di-escape sebelum dimasukkan ke template HTML.
- **Paragraf sumber dipertahankan:** normalisasi pengambilan baru menjaga pemisah paragraf yang memang tersedia. Parser/cache dinaikkan ke versi 3. Teks lama yang sudah tergabung tidak diberi paragraf buatan; ringkasan tetap menggunakan kalimat awal.
- **Keadaan kosong dan unduhan:** Hapus filter muncul ketika diperlukan, hasil kosong memberi petunjuk tindakan, dan perubahan filter menjelaskan perlunya menyiapkan ulang unduhan. Pembuatan Excel tetap atas permintaan; pengamanan formula dan isi panjang dipertahankan.
- **Tampilan konsisten:** tema terang dan konfigurasi UI ikut disalin ke image; menu developer disembunyikan. Preferensi sistem gelap tetap menampilkan tema aplikasi yang terbaca. CSS lama yang tidak digunakan dihapus.

## Pengukuran layout

Skenario sebelum/sesudah menggunakan tiga status sumber, 40 berita contoh, dan ukuran viewport yang sama. Titik mulai tabel diukur relatif terhadap layar awal tanpa menggulir.

| Viewport | Sebelum | Sesudah |
|---|---:|---:|
| Desktop 1440 × 900 | sekitar 1.226 px | sekitar **561 px** |
| Ponsel 390 × 844 | sekitar 2.033 px | sekitar **595 px** |
| Layar sempit 320 × 844 | belum diukur pada baseline | sekitar **613 px** |

Tabel kini mulai dalam layar pertama pada seluruh viewport tersebut. Kontainer halaman dan tampilan detail tidak mengalami overflow horizontal; tabel tetap dapat digulir secara horizontal untuk melihat kolom lain.

## Verifikasi

- **61 tes lulus pada Python 3.12.16 dan 61 tes pada Python 3.11.9**, tanpa tes yang dilewati. Termasuk tanggal cepat, tanggal tidak valid, pencarian literal, hapus filter, navigasi artikel, pembatalan tanpa exception, penyiapan ulang unduhan, escaping, pelestarian paragraf, serta pengamanan scraping/ekspor sebelumnya.
- Smoke test UI/ekspor lulus pada kedua versi Python. Bukti: [Python 3.12](uiux-verification-python312.json) dan [Python 3.11](uiux-verification-python311.json); log `.txt` tersedia dengan nama yang sama. Hash sumber, CSS, konfigurasi, dan tes direkam di dalamnya.
- **Enam skenario browser lulus:** desktop awal/hasil, ponsel hasil, layar sempit 320 px, ponsel awal, serta preferensi sistem gelap. Pemeriksaan mencakup kontras tanggal/tombol, fokus keyboard tanggal, posisi tabel, overflow halaman, navigasi artikel pada desktop/ponsel/320 px, dan exception JavaScript. Bukti: [verification.json](uiux-fixed/verification.json) dan [manifest browser/sumber](uiux-fixed/manifest.json).
- Script browser memblokir request HTTP eksternal dan tidak menekan tombol pengumpulan berita. Seluruh preview memakai fixture sintetis. Server serta proses anak yang dibuat untuk pengujian dihentikan setelah pemeriksaan.
- Pemeriksaan browser ditambahkan ke gate **Linux CI**. Playwright hanya dependensi pengembangan; runtime container tidak membawa browser.
- Bandit tidak menemukan temuan medium/high pada cakupan aplikasi/smoke test: [uiux-bandit.json](uiux-bandit.json). Audit 38 dependensi runtime tidak menemukan kerentanan dikenal: [uiux-dependency.json](uiux-dependency.json).
- Compose, YAML workflow, sintaks shell, dan whitespace diperiksa. Build container, eksekusi Linux CI, dan deployment server belum dijalankan secara lokal karena Docker daemon tidak tersedia.

Pengujian browser ini bukan sertifikasi aksesibilitas penuh. Pemeriksaan perangkat fisik, pembaca layar, seluruh keadaan kalender, serta seluruh variasi artikel produksi belum dilakukan. Hasil pengukuran tampilan bergantung viewport dan data yang disajikan.

## Pratinjau

- [Desktop dengan hasil](uiux-fixed/desktop-results.png)
- [Ponsel dengan hasil](uiux-fixed/mobile-results.png)
- [Layar sempit 320 px](uiux-fixed/narrow-results.png)
- [Form pengambilan dan tanggal](uiux-fixed/desktop-empty.png)
- [Detail pada desktop](uiux-fixed/desktop-detail.png)
- [Detail pada ponsel](uiux-fixed/mobile-detail.png)

Untuk menjalankan pemeriksaan ulang, ikuti bagian pengujian browser pada [README](../../../README.md).
