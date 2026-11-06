# Perbaikan hasil audit — 6 November 2026

> Catatan ini membahas perbaikan fungsi aplikasi pada tahap sebelumnya. Perbaikan tampilannya ada di [UI_UX_REMEDIATION.md](UI_UX_REMEDIATION.md). Angka dan file bukti di sini tetap mengikuti pengujian saat itu.

Kode diperbaiki di folder proyek setelah audit commit `27f350f4eef80c74f52ef5a1c589ad95232c29f8`. Pada tahap ini, kode belum di-push, image belum dipublikasikan, dan aplikasi belum dipasang ke server. Laporan serta bukti awal tetap disimpan.

## Perubahan per temuan

| Temuan | Yang diubah | Cara mengeceknya |
|---|---|---|
| A01 — SSRF | URL, host, port, dan hasil DNS diperiksa di `helper/http_client.py`. Koneksi hanya menuju IP publik yang sudah diperiksa; SNI dan sertifikat tetap memakai hostname asli. Redirect diperiksa per sumber, dan proxy environment dimatikan. | URL palsu dan alamat jaringan internal ditolak. Tes pengganti memeriksa IP koneksi; request HTTPS ke portal berhasil. |
| A02 — Formula Excel | Semua nilai dari sumber berita ditulis sebagai teks, termasuk sheet keterangan dan error. | Workbook dibuka kembali: `=1+1` tetap teks, dan tidak ada sel formula/error. |
| A03 — Status kelengkapan | `SourceResult` mencatat status, halaman yang dibaca, alasan berhenti, isi kosong, dan detail error. | Indeks gagal atau tampilan portal berubah tidak lagi disebut sukses kosong. Batas proses dan isi yang gagal terlihat. |
| A04 — Hasil yang hilang | Error ditangani per artikel. Hasil yang sudah ada tetap dikembalikan dan disimpan. UI juga menyimpan hasil sebelumnya. | Jika halaman kedua gagal, berita dari halaman pertama tetap ada. |
| A05 — Dekode ganda | `scrap/jawapos.py` membaca `data-page` tanpa memanggil `html.unescape` untuk kedua kalinya. | Kutip dan ampersand dalam data JSON-HTML yang valid bisa dibaca. |
| A06 — Regex pencarian | Kata kunci dicari sebagai teks biasa dengan `regex=False`. Kolom kosong atau tidak tersedia juga ditangani. | `[`, `.`, dan `a+b` tidak menyebabkan error atau dianggap sebagai pola regex. |
| A07 — Isi Excel | Teks panjang dilanjutkan ke sheet Teks Lanjutan. Karakter yang tidak bisa ditulis ke XML diberi penanda yang bisa dibaca kembali. JSON menyimpan teks asli. | Teks panjang, emoji, dan karakter kontrol tetap bisa disimpan dan disambungkan lagi. |
| A08 — Proses terlalu panjang | Tanggal, halaman, entri, ukuran isi, durasi, dan ukuran respons dibatasi. Halaman berulang dan artikel duplikat dideteksi. Ada pembatalan dan batas dua proses bersamaan. | Saat batas tercapai atau proses dibatalkan, hasil yang sudah ada tetap tersedia. Respons yang mengirim data terlalu lambat juga dihentikan saat waktu habis. |
| A09 — Data dari API | Format data, informasi halaman, tanggal, ID, slug, judul, dan kategori diperiksa sebelum dipakai. | Data null/rusak menghasilkan error yang jelas. Isi artikel di luar tanggal pilihan tidak diambil. |
| A10 — HTML dari sumber | Data sumber ditampilkan sebagai teks, tabel, atau HTML yang sudah di-escape. Tautan juga diperiksa. | Tag HTML dari kategori tampil sebagai teks. |
| A11 — Versi yang dipasang | Server menerima digest image hasil build. Script memeriksa commit, menguji aplikasi, menunggu container siap, dan menyiapkan rollback ke image lama. | Docker pengganti dipakai untuk mengecek urutan rilis dan rollback. Server sebenarnya belum diuji. |
| A12 — Versi library dan CI | Library dikunci beserta hash. Base Python/Trivy memakai digest, Actions memakai SHA, dan tes menjadi syarat sebelum deploy. | Pemasangan Python 3.11/3.12, YAML, shell, dan audit library berhasil. Build image dan job Linux CI masih perlu dijalankan di runner. |

## Perubahan agar aplikasi lebih ringan

- Aplikasi hanya menampilkan tabel, satu detail berita, atau halaman unduhan sesuai pilihan pengguna. Saat diuji dengan 250 artikel, membuka tabel tidak sekaligus membuat seluruh detail dan file Excel. Excel baru dibuat saat diminta. Jika filter berubah, file perlu disiapkan ulang.
- Isi artikel sukses disimpan dalam cache lima menit, maksimal 64 entri/8 juta karakter; kegagalan tidak dicache. Request tetap berurutan per pekerjaan dengan session milik thread, retry terbatas untuk error sementara, dan dukungan Retry-After numerik. Tidak menambah paralelisasi per portal tanpa pengukuran kuota layanan.
- Prokal/Radar menggunakan satu adapter terkonfigurasi; transformasi data, exporter, pipeline, budget, HTTP, dan pekerjaan latar dipisahkan dari UI. Import modul tidak menjalankan aplikasi.
- MutationObserver dan pemindaian DOM menyeluruh dihapus. API `use_container_width` dan iframe penerjemah yang deprecated diganti/dihapus; CSS tampilan utama tetap dipertahankan.
- Chromium, Selenium, driver, serta library GUI browser tidak lagi dibawa oleh lingkungan aplikasi yang dipakai. Entry point Tribun/fallback browser gagal dengan jelas sampai adapter dengan batas pekerjaan dan isolasi jaringan diperiksa. Tiga sumber aktif tetap tersedia.

Checkpoint memakai penulisan atomik, disimpan bertahap di `data/runs`, dengan retensi 20 file terbaru. Tiga hasil sebelumnya tersedia di sesi. Metadata pengumpulan/filter/status dan galat disertakan dalam ekspor. Checkpoint yang masih berstatus berjalan dipulihkan sebagai hasil terputus, bukan hasil lengkap; tidak ada pengiriman ulang request otomatis.

## Hasil pengujian

- **52/52 tes lulus pada Python 3.12.16 dan 52/52 pada Python 3.11.9**, keduanya Windows, tanpa tes yang dilewati. Lock memiliki marker versi NumPy yang sesuai untuk masing-masing Python. Bukti: [verification-python312.json](verification-python312.json), [verification-python311.json](verification-python311.json), dan log `.txt` dengan nama yang sama. Hash sumber/config/test direkam pada JSON tersebut.
- Smoke test UI/ekspor berhasil pada kedua versi Python. Server Streamlit dijalankan sementara di loopback dan endpoint `/_stcore/health` merespons **HTTP 200, `ok`**: [runtime-health.json](runtime-health.json). Proses server pengujian dihentikan setelah pemeriksaan.
- **Pemeriksaan baca saja ke ketiga portal berhasil**: Benuanta membaca satu indeks dan satu isi; Prokal/Radar masing-masing membaca satu hasil API dan satu isi artikel. Tidak menyimpan isi/judul artikel dalam bukti: [live-readonly-smoke.json](live-readonly-smoke.json). Ini belum membuktikan seluruh rentang tanggal atau seluruh variasi halaman portal.
- Bandit tidak menemukan temuan tingkat medium/high pada cakupan aplikasi/smoke test: [bandit-fixed.json](bandit-fixed.json). Peringatan RNG rendah pada helper Tribun yang belum aktif tidak terkait kriptografi.
- Audit versi runtime yang terkunci tidak menemukan kerentanan dikenal: [dependency-fixed.json](dependency-fixed.json). Ini bukan hasil pemindaian paket OS/image; hasil database kerentanan dapat berubah.
- Compose config, sintaks `deploy.sh`, YAML workflow, dan sintaks seluruh blok shell workflow berhasil diperiksa. Referensi SHA/digest diambil dari repository/registry resmi: [build-references.json](build-references.json).
- Tes deployment menggunakan Docker pengganti. Pada Windows, `flock` juga diganti pada fixture karena Git Bash tidak menyertakannya; locking Linux sebenarnya dan Docker daemon bukan bagian dari pembuktian lokal.

Perintah pengujian ada pada [README](../../../README.md). Probe `reproduce.py` di direktori audit adalah alat historis dan menolak dijalankan pada sumber yang sudah berubah agar bukti sebelum perbaikan tidak tertimpa.

## Catatan saat dipakai

1. **Belum menjalankan build/container Linux, image scan, workflow GitHub, atau deployment server** karena Docker daemon dan akses server tidak tersedia pada sesi ini. Pemeriksaan tersebut sudah dimasukkan sebagai pemeriksaan wajib sebelum deployment, tetapi keberhasilannya belum bisa dipastikan.
2. Pembatalan menunggu operasi yang sedang berjalan. Pencarian alamat DNS atau pembacaan socket bisa membuatnya tidak langsung selesai. Thread tidak dimatikan paksa agar hasil yang sudah ada tetap bisa disimpan.
3. Penulisan checkpoint ditunda sekitar dua detik; crash mendadak dapat kehilangan perubahan sesudah checkpoint terakhir. File lokal tersedia lintas sesi pada instalasi yang sama. Atur autentikasi gateway bila parameter pengumpulan perlu dibatasi per pengguna.
4. Aplikasi tidak menambahkan autentikasi akun atau firewall egress host. Compose tetap mengikat port host ke loopback, memakai filesystem read-only, named volume, user non-root, dan batas resource. Pengaturan gateway/server perlu diperiksa administrator.
5. Setelah rollout, ukur durasi per sumber, jumlah request, cache hit, 429, dan penggunaan memori sebelum mengubah batas atau menambah concurrency. Kebijakan keamanan tidak menggunakan fallback browser untuk melewati penolakan akses.
