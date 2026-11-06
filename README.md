# FANTASTIK

FANTASTIK (Fenomena Statistik) membantu mengumpulkan berita dari Benuanta, Prokal, dan Radar Tarakan. Pilih tanggal dan sumber media, lalu cari, baca, atau unduh beritanya. Berita ini bisa dipakai sebagai bahan pendukung untuk menjelaskan fenomena statistik di daerah.

Cuplikan berita diambil dari kalimat awal artikel. Tribun Kaltara belum tersedia di aplikasi.

## Mulai memakai aplikasi

1. Buka **Kumpulkan berita** di bagian atas halaman.
2. Pilih tanggal dan sumber media. Untuk memilih tanggal dengan cepat, gunakan **Hari ini**, **7 hari**, atau **30 hari**.
3. Klik **Kumpulkan berita**, lalu tunggu hasilnya. Kalau perlu berhenti, klik **Batalkan proses**. Berita yang sudah terkumpul tetap tersedia.
4. Gunakan **Cari dalam hasil** atau **Kategori** untuk menyaring berita yang sudah ada. Klik **Hapus filter** untuk menampilkan semuanya lagi.
5. Pilih **Detail** untuk membaca isi berita. Tombol **Sebelumnya** dan **Berikutnya** berpindah ke berita lain.
6. Untuk menyimpan hasil, buka **Unduh** lalu klik **Siapkan unduhan**. Pilih Excel untuk dibaca sebagai tabel, atau JSON kalau datanya ingin diolah lagi.

Pencarian kata kunci hanya menyaring hasil yang sudah terkumpul. Untuk mengambil berita dari tanggal atau media lain, buka **Kumpulkan berita** lagi. Tanggal dan waktu hasil yang sedang dibaca tercantum di atas tabel.

## Kalau hasilnya belum lengkap

Setiap sumber punya status **Lengkap**, **Sebagian**, atau **Gagal**. Kalau ada sumber atau isi berita yang gagal diambil, hasil keseluruhan diberi label **Belum lengkap**. Penyebab dan kode error bisa dilihat di **Detail proses**.

Berita yang sudah berhasil diambil tetap bisa dibaca meskipun halaman berikutnya gagal. Kalau pencarian baru gagal tanpa menghasilkan berita, aplikasi tetap menampilkan hasil sebelumnya. Tiga hasil terakhir juga tersedia di bagian **Hasil sebelumnya**.

## Menyimpan dan membuka hasil

- File unduhan mengikuti kata kunci dan kategori yang sedang dipilih. Kalau filter berubah, klik **Siapkan unduhan** lagi.
- Excel menyimpan data berita sebagai teks. Isi yang terlalu panjang dilanjutkan di sheet **Teks Lanjutan**. Petunjuk membacanya ada di **Metadata**, sedangkan daftar error ada di **Galat Sumber**.
- JSON menyimpan teks asli, keterangan pencarian, dan daftar error. Pakai format ini jika ingin mengolah data lewat program lain.
- Hasil juga disimpan otomatis di `data/runs/`. Buka kembali lewat **Hasil yang sudah disimpan** di sidebar. Ini hanya membuka data yang sudah ada, tanpa mengulang pencarian.
- Aplikasi menyimpan 20 file hasil terbaru. File dari proses yang terputus diberi tanda belum lengkap. Jika aplikasi mati mendadak, perubahan setelah penyimpanan terakhir bisa hilang; jeda penyimpanannya sekitar dua detik.

Untuk berita yang baru diambil, paragraf dari sumber tetap dipertahankan. Hasil lama yang sudah terlanjur menjadi satu blok teks tetap ditampilkan seperti adanya.

## Batas pencarian

Satu pencarian bisa mencakup sampai 31 hari. Untuk setiap sumber, batasnya adalah 200 halaman, 1.000 entri, 8 juta karakter isi, dan sekitar 3 menit. Maksimal dua pencarian bisa berjalan bersamaan dalam satu proses server Python.

Pembatalan tidak selalu langsung selesai. Aplikasi perlu menunggu pembacaan halaman atau koneksi yang sedang berjalan. Kalau batas waktu atau jumlah data tercapai, hasil yang sudah ada tetap disimpan dengan status belum lengkap.

## Menjalankan di komputer sendiri

Siapkan Python 3.11 atau 3.12. Image Docker memakai Python 3.12.

Contoh untuk PowerShell di Windows:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --require-hashes --only-binary=:all: -r requirements.txt
.venv\Scripts\python -m streamlit run main.py
```

Pada Linux, ganti `.venv\Scripts\python` dengan `.venv/bin/python`. Perintah di bagian berikut dijalankan dari folder proyek, memakai Python dari virtual environment yang sama.

## Mengecek perubahan kode

Untuk pengembangan, pasang `requirements-dev.txt` dengan opsi pip yang sama. Lalu jalankan:

```powershell
python -m unittest discover -s tests -v
python scripts/smoke_test.py
python -m bandit -r main.py helper scrap scripts/smoke_test.py -ll
python -m pip_audit -r requirements.txt --no-deps --disable-pip
```

Tes browser memakai berita contoh dan memblokir request HTTP ke luar komputer. Tes ini tidak menjalankan pencarian berita sungguhan.

```powershell
python -m playwright install chromium
python scripts/check_ui.py
```

Kalau Chrome sudah terpasang, bisa langsung memakai `python scripts/check_ui.py --channel chrome`. Di Linux CI, gunakan `python -m playwright install --with-deps chromium` untuk memasang browser beserta kebutuhan sistemnya. Screenshot dan hasil tes disimpan di `test-results/ui/`.

## Catatan untuk pengelola server

Aplikasi hanya mengambil halaman HTTPS dari alamat media yang diizinkan. Alamat IP tujuan diperiksa sebelum koneksi dibuat, termasuk saat halaman mengarahkan ke alamat lain. Ukuran satu respons dibatasi 4 MiB. Aplikasi tidak memakai proxy dari environment dan tidak mencoba browser lain untuk melewati penolakan HTTP 403.

Isi berita yang berhasil dibaca disimpan sementara dalam cache selama lima menit, maksimal 64 entri atau 8 juta karakter. Cache membantu agar artikel yang sama tidak perlu terus diambil ulang. Pengambilan yang gagal tidak masuk cache.

Lihat [DEPLOYMENT.md](DEPLOYMENT.md) untuk pemasangan di server, pemeriksaan rilis, dan cara kembali ke versi sebelumnya. Port Compose hanya dibuka ke loopback. Kalau aplikasi akan dibuka lewat internet, pengelola perlu mengatur HTTPS, login bila dibutuhkan, dan batas akses pada reverse proxy. Aplikasi ini belum memiliki akun pengguna sendiri.

## Memperbarui library

Daftar library langsung ada di `requirements.in`. Versi lengkap beserta hash file instalasinya dikunci di `requirements.txt`, supaya pemasangan tidak tiba-tiba memakai versi lain. `requirements-dev.txt` menambahkan alat pengujian dengan tetap mengikuti versi runtime.

Untuk memperbarui daftar ini, gunakan uv 0.13.7:

```powershell
uv pip compile requirements.in --universal --python-version 3.11 --upgrade --generate-hashes --no-emit-index-url --output-file requirements.txt
uv pip compile requirements-dev.in --universal --python-version 3.11 --upgrade --generate-hashes --no-emit-index-url --output-file requirements-dev.txt
```

Periksa perubahan versinya, lalu jalankan tes sebelum merilis. Digest base image dan SHA Actions juga perlu diperbarui dari registry atau repository resminya.

## Catatan audit

- [Laporan audit awal](docs/audit/2026-11-06/REPORT.md)
- [Perbaikan dari hasil audit](docs/audit/2026-11-06/REMEDIATION.md)
- [Perbaikan tampilan dan cara pakai](docs/audit/2026-11-06/UI_UX_REMEDIATION.md)
