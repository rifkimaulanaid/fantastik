# FANTASTIK

FANTASTIK (Fenomena Statistik) mengumpulkan berita dari Benuanta, Prokal, dan Radar Tarakan untuk mendukung telaah fenomena statistik. Ringkasan mengambil kalimat awal artikel. Tribun Kaltara belum aktif; fallback browser tidak disertakan dalam runtime aman.

## Menjalankan lokal

Gunakan Python 3.11 atau 3.12. Container produksi memakai Python 3.12.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --require-hashes --only-binary=:all: -r requirements.txt
.venv\Scripts\python -m streamlit run main.py
```

Pada Linux, gunakan `.venv/bin/python`. Untuk pengembangan/pengujian, pasang `requirements-dev.txt` dengan opsi pip yang sama, lalu jalankan:

```powershell
python -m unittest discover -s tests -v
python scripts/smoke_test.py
python -m bandit -r main.py helper scrap scripts/smoke_test.py -ll
python -m pip_audit -r requirements.txt --no-deps --disable-pip
```

Pemeriksaan UI browser memakai data sintetis dan memblokir request HTTP eksternal. Pasang browser pengujian lalu jalankan:

```powershell
python -m playwright install chromium
python scripts/check_ui.py
```

Jika Chrome sudah tersedia, gunakan `python scripts/check_ui.py --channel chrome`. Pada Linux CI, browser dan dependensi sistem dipasang dengan `python -m playwright install --with-deps chromium`. Screenshot serta hasil pemeriksaan tersimpan di `test-results/ui/`.

## Menggunakan antarmuka

- Buka **Kumpulkan berita** pada area utama, termasuk dari ponsel. Tersedia rentang cepat Hari ini, 7 hari, 30 hari, atau tanggal pilihan. Filter ini menentukan pengambilan baru; hasil yang sedang dibaca tetap memiliki tanggal dan waktu pengambilannya sendiri.
- **Cari dalam hasil** dan **Kategori** hanya menyaring berita yang sudah diperoleh. **Hapus filter** muncul ketika filter digunakan. Status sumber dan label Lengkap/Belum lengkap tetap merujuk pengambilan tersebut.
- Pada **Detail**, pilih berita atau gunakan **Sebelumnya/Berikutnya**. Judul dan isi ditampilkan dengan lebar baca terbatas. Paragraf sumber dipertahankan untuk pengambilan baru (parser versi 3); teks lama yang telah digabung tidak direkonstruksi.
- Pada **Unduh**, pilih **Siapkan unduhan**. Jika filter berubah, aplikasi meminta berkas disiapkan ulang. Kode kendala, metadata, dan batas teknis tersedia pada **Rincian pengambilan dan kendala**.
- Aplikasi menggunakan tema terang yang konsisten; logo dan warna utama dipertahankan. Menu developer disembunyikan pada antarmuka pengguna.

## Hasil dan batas pekerjaan

- Status **Lengkap**, **Parsial**, dan **Gagal** dipisahkan. Kendala memuat sumber, tahap, kode, serta ID artikel bila tersedia. Artikel tanpa isi tetap memiliki status isi gagal.
- Kegagalan artikel/halaman berikutnya mempertahankan hasil sebelumnya. Pengambilan baru yang gagal tanpa data mempertahankan hasil aktif; tiga hasil sebelumnya tersedia dalam sesi.
- Rentang maksimal 31 hari. Setiap sumber dibatasi 200 halaman, 1.000 entri, 8 juta karakter isi, dan target durasi 180 detik. Durasi/pembatalan diperiksa di antara operasi jaringan; resolver DNS dan pembacaan socket dapat menunda penghentian hingga operasi tersebut kembali.
- Maksimal dua proses per server Python. Tombol **Batalkan proses** menghentikan pekerjaan secara kooperatif dan mempertahankan hasil parsial.
- Checkpoint atomik berada di `data/runs/`; maksimal 20 checkpoint terbaru disimpan. Penulisan disk ditunda maksimal sekitar dua detik di antara pembaruan. Crash mendadak dapat kehilangan pembaruan setelah checkpoint terakhir. Pemulihan menampilkan hasil tersimpan dan tidak mengirim ulang request otomatis.
- Detail ditampilkan untuk satu berita yang dipilih. Excel hanya dibuat setelah **Siapkan unduhan**; perubahan filter membuat unduhan lama tidak berlaku untuk tampilan baru.
- Excel menulis data eksternal sebagai teks. Isi panjang dilanjutkan pada sheet **Teks Lanjutan**; karakter yang tidak dapat ditulis ke XML direpresentasikan dengan escape yang dijelaskan pada sheet **Metadata**. JSON menyimpan teks asli beserta metadata dan galat sumber.

## Jaringan dan deployment

Request dibatasi ke HTTPS pada host sumber yang ditetapkan, IP publik yang dipin pada koneksi dengan validasi TLS hostname, redirect tervalidasi, dan maksimal 4 MiB per respons. Proxy dari environment tidak digunakan. Hanya error sementara yang diulang secara terbatas; HTTP 403 tidak dicoba ulang atau dialihkan ke browser. Cache isi artikel sukses berlaku lima menit, dengan batas 64 entri/8 juta karakter; kegagalan tidak disimpan di cache.

Lihat [DEPLOYMENT.md](DEPLOYMENT.md) untuk build, pemilihan digest image, pemeriksaan kesehatan, rollback, dan penyimpanan checkpoint. Jika dipublikasikan melalui reverse proxy, kelola autentikasi dan rate limit pada gateway. Repo tidak menyediakan akun pengguna atau pembatasan egress di host; port Compose tetap terikat ke loopback.

## Memperbarui dependensi

`requirements.in` berisi dependensi langsung, `requirements.txt` mengunci seluruh dependensi transitif dengan hash dan marker lintas platform/Python. Lock pengembangan juga dibatasi oleh lock runtime. Gunakan uv 0.13.7 dan review perubahan sebelum rilis:

```powershell
uv pip compile requirements.in --universal --python-version 3.11 --upgrade --generate-hashes --no-emit-index-url --output-file requirements.txt
uv pip compile requirements-dev.in --universal --python-version 3.11 --upgrade --generate-hashes --no-emit-index-url --output-file requirements-dev.txt
```

Perbarui digest base image dan SHA Actions dari repository/registry resmi, kemudian jalankan pengujian dan pemindaian image. Laporan audit awal tersimpan di [docs/audit/2026-11-06/REPORT.md](docs/audit/2026-11-06/REPORT.md); status perbaikannya dicatat terpisah di [REMEDIATION.md](docs/audit/2026-11-06/REMEDIATION.md).
