# Perbaikan hasil audit — 6 November 2026

> Dokumen ini merekam tahap perbaikan fungsional sebelumnya. Penyempurnaan UI/UX berikutnya dan bukti pengujian terbaru tercatat pada [UI_UX_REMEDIATION.md](UI_UX_REMEDIATION.md).

Perbaikan diterapkan pada workspace setelah snapshot audit commit `27f350f4eef80c74f52ef5a1c589ad95232c29f8`. Tidak ada push, publikasi image, atau deployment server dari sesi ini. Laporan audit awal dan bukti baseline dipertahankan sebagai arsip.

## Perubahan per temuan

| Temuan | Implementasi | Verifikasi |
|---|---|---|
| A01 — SSRF | `helper/http_client.py`: HTTPS/host/port tervalidasi, semua alamat DNS harus publik, pool koneksi memakai IP numerik yang diperiksa dengan SNI/validasi sertifikat hostname asli, redirect per publisher, proxy environment dinonaktifkan | URL palsu/private/mapped IPv6/multicast ditolak; mock membuktikan koneksi dipin; request HTTPS ke portal berhasil |
| A02 — Formula Excel | `helper/data.py`: setiap nilai eksternal ditulis dengan tipe sel string, termasuk seluruh sheet metadata/galat | Round-trip workbook tidak mengandung sel formula/error; `=1+1` tetap teks |
| A03 — Status kelengkapan | `SourceResult` membedakan success/partial/failed, cakupan, alasan berhenti, jumlah isi kosong, tahap/kode/ID galat | Indeks gagal/selector berubah tidak menjadi sukses kosong; limit dan isi gagal terlihat |
| A04 — Kehilangan hasil | Adapter mengisolasi error per artikel, mengembalikan hasil parsial, dan mengirim checkpoint; UI mempertahankan hasil lama jika pengambilan baru gagal tanpa data | Halaman kedua gagal tetap membawa artikel pertama; hasil baru diadopsi tanpa menghapus riwayat sebelumnya |
| A05 — Dekode ganda | Parsing `data-page` bersama pada `scrap/jawapos.py`, tanpa `html.unescape` kedua | Kutip/ampersand pada JSON-HTML valid dibaca dengan benar |
| A06 — Regex pencarian | Filter literal `regex=False`, null-safe, mendukung kolom opsional | `[`, `.`, dan `a+b` tidak menimbulkan error atau kecocokan regex |
| A07 — Integritas ekspor | Teks panjang dibagi ke sheet Teks Lanjutan; karakter XML tidak valid dan backslash memakai escape reversibel; JSON mempertahankan teks asli | Teks panjang termasuk emoji dapat direkonstruksi utuh; karakter kontrol tidak memutus ekspor |
| A08 — Batas sumber daya | Batas tanggal/halaman/entri/isi/durasi/respons, deteksi halaman berulang/tidak maju, deduplikasi ID/URL, cancel event, maksimal dua pekerjaan aktif | Tes batas dan pembatalan mempertahankan data parsial; respons trickle dihentikan pada pemeriksaan deadline |
| A09 — Validasi respons | Schema GraphQL/pagination/tanggal/ID/slug/judul/kategori diperiksa; tanggal diverifikasi sebelum mengambil detail | Payload null/rusak gagal secara eksplisit; artikel di luar rentang tidak mengambil detail |
| A10 — HTML eksternal | Metadata/isi/pesan sumber memakai teks atau tabel native; link memakai URL tervalidasi; HTML kustom hanya template statis | Kategori bertag HTML tetap teks dan tidak masuk Markdown mentah |
| A11 — Integritas rilis | Digest image hasil build diteruskan ke server; verifikasi revision, smoke test tanpa network, health wait, lock, dan rollback ke image ID sebelumnya | Tes Docker pengganti membuktikan pemilihan digest, rollback saat gagal, dan larangan mengganti container bila smoke test awal gagal; server aktual belum diuji |
| A12 — Reproducibility/CI | Lock universal transitif berhash untuk runtime/dev; base Python/Trivy dipin digest; Actions dipin SHA; CI Windows/Linux, tes, Bandit, audit dependensi, smoke/image scan menjadi syarat deploy | Lock dipasang pada Python 3.11 dan 3.12; YAML/shell diperiksa; pemindaian dependensi lulus. Build/image scan/Linux CI menunggu eksekusi pada runner |

## Optimasi yang diterapkan

- UI merender tabel, satu detail yang dipilih, atau layar unduhan sesuai pilihan. Untuk 250 artikel, tes membuktikan tabel tidak membuat expander detail maupun Excel. Excel dibuat sekali saat diminta dan dibatalkan kecocokannya bila filter berubah.
- Isi artikel sukses disimpan dalam cache lima menit, maksimal 64 entri/8 juta karakter; kegagalan tidak dicache. Request tetap berurutan per pekerjaan dengan session milik thread, retry terbatas untuk error sementara, dan dukungan Retry-After numerik. Tidak menambah paralelisasi per portal tanpa pengukuran kuota layanan.
- Prokal/Radar menggunakan satu adapter terkonfigurasi; transformasi data, exporter, pipeline, budget, HTTP, dan pekerjaan latar dipisahkan dari UI. Import modul tidak menjalankan aplikasi.
- MutationObserver dan pemindaian DOM menyeluruh dihapus. API `use_container_width` dan iframe penerjemah yang deprecated diganti/dihapus; CSS tampilan utama tetap dipertahankan.
- Chromium, Selenium, driver, serta library GUI browser tidak lagi dibawa oleh runtime aktif. Entry point Tribun/fallback browser gagal secara eksplisit sampai adapter dengan batas pekerjaan dan isolasi jaringan diverifikasi. Tiga sumber aktif tetap tersedia.

Checkpoint memakai penulisan atomik, disimpan bertahap di `data/runs`, dengan retensi 20 file terbaru. Tiga hasil sebelumnya tersedia di sesi. Metadata pengumpulan/filter/status dan galat disertakan dalam ekspor. Checkpoint yang masih berstatus berjalan dipulihkan sebagai hasil terputus, bukan hasil lengkap; tidak ada pengiriman ulang request otomatis.

## Hasil verifikasi

- **52/52 tes lulus pada Python 3.12.16 dan 52/52 pada Python 3.11.9**, keduanya Windows, tanpa tes yang dilewati. Lock memiliki marker versi NumPy yang sesuai untuk masing-masing Python. Bukti: [verification-python312.json](verification-python312.json), [verification-python311.json](verification-python311.json), dan log `.txt` dengan nama yang sama. Hash sumber/config/test direkam pada JSON tersebut.
- Smoke test UI/ekspor berhasil pada kedua versi Python. Server Streamlit dijalankan sementara di loopback dan endpoint `/_stcore/health` merespons **HTTP 200, `ok`**: [runtime-health.json](runtime-health.json). Proses server pengujian dihentikan setelah pemeriksaan.
- **Pemeriksaan baca saja ke ketiga portal berhasil**: Benuanta membaca satu indeks dan satu isi; Prokal/Radar masing-masing membaca satu hasil API dan satu isi artikel. Tidak menyimpan isi/judul artikel dalam bukti: [live-readonly-smoke.json](live-readonly-smoke.json). Ini bukan bukti seluruh rentang tanggal atau seluruh variasi halaman portal.
- Bandit tidak menemukan temuan tingkat medium/high pada cakupan aplikasi/smoke test: [bandit-fixed.json](bandit-fixed.json). Peringatan RNG rendah pada helper Tribun yang belum aktif tidak terkait kriptografi.
- Audit versi runtime yang terkunci tidak menemukan kerentanan dikenal: [dependency-fixed.json](dependency-fixed.json). Ini bukan hasil pemindaian paket OS/image; hasil database kerentanan dapat berubah.
- Compose config, sintaks `deploy.sh`, YAML workflow, dan sintaks seluruh blok shell workflow berhasil diperiksa. Referensi SHA/digest diambil dari repository/registry resmi: [build-references.json](build-references.json).
- Tes deployment menggunakan Docker pengganti. Pada Windows, `flock` juga diganti pada fixture karena Git Bash tidak menyertakannya; locking Linux sebenarnya dan Docker daemon bukan bagian dari pembuktian lokal.

Perintah pengujian ada pada [README](../../../README.md). Probe `reproduce.py` di direktori audit adalah alat historis dan menolak dijalankan pada sumber yang sudah berubah agar bukti baseline tidak tertimpa.

## Batas dan catatan operasional

1. **Belum menjalankan build/container Linux, image scan, workflow GitHub, atau deployment server** karena Docker daemon dan akses server tidak tersedia pada sesi ini. Pemeriksaan tersebut sudah dimasukkan sebagai gate CI/deployment, tetapi keberhasilannya belum diklaim.
2. Batas waktu dan pembatalan bersifat kooperatif. Pemeriksaan berlangsung di antara operasi baca/request; resolver DNS dan satu operasi socket yang sedang berjalan dapat menunda respons pembatalan. Tidak memaksa kill thread yang dapat membuang data.
3. Penulisan checkpoint ditunda sekitar dua detik; crash mendadak dapat kehilangan perubahan sesudah checkpoint terakhir. File lokal tersedia lintas sesi pada instalasi yang sama. Atur autentikasi gateway bila parameter pengumpulan perlu dibatasi per pengguna.
4. Aplikasi tidak menambahkan autentikasi akun atau firewall egress host. Compose tetap mengikat port host ke loopback, memakai filesystem read-only, named volume, user non-root, dan batas resource. Pengaturan gateway/server perlu diverifikasi administrator.
5. Setelah rollout, ukur durasi per sumber, jumlah request, cache hit, 429, dan penggunaan memori sebelum mengubah batas atau menambah concurrency. Kebijakan keamanan tidak menggunakan fallback browser untuk melewati penolakan akses.
