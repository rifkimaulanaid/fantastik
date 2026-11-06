# Tinjauan UI/UX — 6 November 2026

> Snapshot sebelum penyempurnaan UI. Perbaikan dan hasil pengujian terbaru tersedia pada [UI_UX_REMEDIATION.md](UI_UX_REMEDIATION.md); screenshot di direktori `uiux/` tetap menjadi bukti kondisi awal.

Alur aplikasi sudah lebih andal setelah perbaikan pipeline, tetapi antarmuka masih perlu disempurnakan untuk pekerjaan harian. Prioritas tertinggi adalah keterbacaan tanggal dan akses cepat ke hasil.

Pemeriksaan menggunakan Chrome headless lokal, viewport desktop 1440 × 900 dan ponsel 390 × 844, dengan data sintetis 40 artikel serta tiga status sumber. Tidak menjalankan scraping atau mengubah kode UI pada tinjauan ini. Ukuran viewport ponsel bukan pengujian perangkat fisik. Tidak ditemukan exception JavaScript pada ketiga skenario yang diperiksa; ini bukan audit aksesibilitas menyeluruh.

## Temuan prioritas

| Prioritas | Temuan dan bukti | Perbaikan yang disarankan |
|---|---|---|
| Tinggi | Angka tanggal hampir tidak terlihat. Elemen tanggal sekarang berupa `span[role=spinbutton]`; aturan CSS hanya memperbaiki warna `input`. Aturan sidebar menyetel teks menjadi RGB(247,239,228), sementara latar field RGB(241,240,238). Rasio kontras sekitar **1,001:1**. | Atur warna elemen tanggal yang benar dan hindari aturan warna universal pada seluruh turunan sidebar. Verifikasi teks, placeholder, fokus, kalender, serta kondisi disabled. |
| Tinggi | Area hasil terlalu jauh ke bawah. Pada skenario tiga sumber, tabel mulai di **y≈1226 px** pada desktop dan **y≈2033 px** pada ponsel. Header sendiri setinggi sekitar 338/712 px. | Setelah hasil tersedia, gunakan header ringkas; pindahkan Alur Singkat ke bantuan yang dapat dibuka. Ringkas status sumber menjadi indikator/kartu pendek dengan rincian kendala yang dapat diperluas. Pencarian, jumlah hasil, dan navigasi hasil harus segera terlihat. |
| Menengah | Pada ponsel, satu layar awal hampir seluruhnya berisi judul dan panduan. Filter utama tersembunyi dalam sidebar yang diciutkan. | Sediakan tombol Filter yang jelas pada area utama atau tempatkan filter inti di atas hasil. Tambahkan pilihan cepat Hari ini, 7 hari, dan 30 hari, tetap menghormati batas tanggal. |
| Menengah | Detail berita berupa blok teks panjang. Judul hanya muncul dalam dropdown pemilihan; tidak ada tombol berita sebelumnya/berikutnya. | Tampilkan judul sebagai heading, tanggal/sumber/kategori sebagai metadata singkat, batasi lebar bacaan, dan sediakan navigasi sebelumnya/berikutnya. Pelestarian paragraf perlu diperbaiki di normalisasi konten jika ingin menampilkan paragraf asli; jangan mengarang paragraf yang telah hilang. |
| Menengah | Istilah teknis mendominasi: Scraping, checkpoint, HTTP, serta batas halaman/entri. Metadata menampilkan timestamp ISO dan ID run. Label Kategori/Tagar serta Unduh/Download tidak seragam. | Gunakan Kumpulkan berita, Hasil tersimpan, Kategori, dan Unduh pada layar utama. Tampilkan waktu seperti 6 November 2026, 10.00 WITA. Letakkan kode teknis/ID pada rincian yang tetap mudah diakses untuk diagnosis. |
| Menengah | Pemilihan tanggal/sumber dan hasil yang sudah tersimpan adalah konteks berbeda. Metrik Sumber Aktif sebenarnya menghitung sumber yang memiliki berita setelah filter. Tombol unduhan menghilang setelah filter berubah tanpa penjelasan khusus. | Bedakan Filter pengambilan dari Filter hasil; ubah metrik menjadi Sumber dengan hasil. Jelaskan hasil yang sedang dilihat dan berikan pesan Siapkan ulang unduhan bila filter berubah. Sediakan aksi Hapus filter pada hasil kosong. |
| Rendah | Pemisah pada pesan status sumber tampil sebagai `?`. CSS masih memuat selector kartu/tab yang tidak lagi digunakan. | Perbaiki literal/encoding pemisah, bersihkan CSS yang tidak dipakai, dan simpan file sebagai UTF-8. |

Kontras teks normal setidaknya 4,5:1 merupakan acuan [WCAG 2.2 — Contrast Minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html). Angka di atas dihitung dari computed style browser, bukan perkiraan warna screenshot. Tidak ada overflow horizontal pada kontainer utama dalam dua viewport tersebut; tabel sendiri boleh memerlukan pengguliran dua dimensi, sesuai pengecualian yang dijelaskan pada [WCAG — Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html).

## Yang sudah membantu pengguna

- Status lengkap/parsial/gagal terlihat dan dilengkapi rincian kendala.
- Proses dapat dibatalkan; hasil sebelumnya dan hasil parsial dapat dipertahankan.
- Pencarian literal, satu detail sesuai pilihan, serta ekspor atas permintaan mengurangi galat dan pekerjaan yang tidak diperlukan.
- Identitas warna dan logo sudah konsisten, sehingga perbaikan dapat dilakukan tanpa mengganti framework atau identitas aplikasi.

## Urutan penyempurnaan

1. Perbaiki kontras tanggal dan pemeriksaan keyboard/fokus pada seluruh filter.
2. Ringkas header, panduan, dan status; tempatkan hasil/pencarian lebih tinggi.
3. Rapikan filter ponsel, label, konteks hasil aktif, serta keadaan kosong/unduhan berubah.
4. Perbaiki tampilan baca berita dan navigasinya.
5. Verifikasi screenshot desktop/ponsel, lebar 320 px, zoom, navigasi keyboard, dan tema yang didukung. Tes AppTest sebelumnya memverifikasi perilaku, tetapi tidak menangkap regresi warna CSS ini.

## Bukti

- [Desktop awal](uiux/desktop-empty.png)
- [Desktop dengan hasil parsial](uiux/desktop-results.png)
- [Ponsel dengan hasil parsial](uiux/mobile-results.png)
- [Detail berita](uiux/desktop-detail.png)
- [Ukuran layout dan computed style](uiux/layout.json)

Snapshot ARIA berada di direktori `uiux/`. Semua artikel pada screenshot adalah data contoh untuk tinjauan antarmuka, bukan hasil pengumpulan berita sebenarnya.
