# Audit FANTASTIK — 6 November 2026

> Snapshot sebelum perbaikan. Implementasi dan hasil verifikasi terbaru dicatat pada [REMEDIATION.md](REMEDIATION.md). Probe historis di direktori ini membutuhkan kode baseline; gunakan tes pada `tests/` untuk memverifikasi implementasi yang telah diperbaiki.

## Kesimpulan

Risiko utama proyek berada pada keakuratan status hasil scraping, hilangnya hasil saat terjadi kegagalan, serta perlakuan terhadap data eksternal ketika diambil, ditampilkan, dan diekspor. Prioritas pertama adalah memperkuat batas kepercayaan URL/Excel dan memastikan pengguna dapat membedakan hasil lengkap, parsial, kosong, serta gagal.

Audit menghasilkan **12 temuan utama: 4 P1 dan 8 P2**, disertai lima kelompok optimasi. P1/P2 adalah prioritas perbaikan engineering, bukan skor CVSS. Tidak ada kerentanan kritis yang telah dibuktikan. Risiko SSRF dan formula Excel memerlukan prasyarat yang dijelaskan pada masing-masing temuan.

Tidak ada perubahan pada kode aplikasi, konfigurasi deployment, atau dependensi proyek. Tambahan workspace hanya berisi laporan dan alat/bukti audit di direktori ini.

## Cakupan, metode, dan batas pembuktian

- Commit: `27f350f4eef80c74f52ef5a1c589ad95232c29f8`.
- Ditinjau: `main.py`, seluruh `helper/` dan `scrap/`, stylesheet, Dockerfile, Compose, konfigurasi Streamlit, workflow GitHub Actions, requirements, serta dokumentasi.
- Dijalankan: 14 probe sintetis, termasuk Streamlit AppTest untuk alur UI sebenarnya; pemeriksaan Bandit; pip-audit terhadap requirements yang diresolusi saat audit; validasi sintaks konfigurasi Compose.
- Probe HTTP hanya menghubungi server loopback sementara milik audit. Tidak melakukan scraping ke portal produksi, login server, deployment, atau pengujian beban layanan eksternal.
- Probe utama menggunakan Windows/Python 3.11.9, Streamlit 1.55.0, pandas 2.3.3, openpyxl 3.1.5, requests 2.32.5, Beautiful Soup 4.15.0. Versi ini bukan bukti versi di server produksi. Dockerfile menggunakan Python 3.12/Linux; build/runtime image belum diuji karena Docker daemon lokal tidak tersedia.
- Tidak memverifikasi konfigurasi reverse proxy, autentikasi di luar repo, GitHub Secrets, branch/environment protection, isi image produksi, kondisi portal saat ini, atau histori kebocoran secret.

Bukti: [evidence.json](evidence.json), [evidence-fresh.json](evidence-fresh.json), [fresh-startup.json](fresh-startup.json), [dependency-audit.json](dependency-audit.json), [bandit.json](bandit.json), dan [reproduce.py](reproduce.py). Kedua file evidence merekam versi, commit, hash file sumber, serta hasil setiap probe. Hasil `observed` berarti perilaku yang diaudit berhasil direproduksi; bukan berarti aplikasi lolos pemeriksaan keamanan.

## Pemahaman arsitektur

```text
Filter tanggal/sumber di sidebar
  -> main.scrape_news, sumber dijalankan berurutan
     -> Benuanta: indeks HTML berhalaman -> detail artikel HTML
     -> Prokal/Radar: GraphQL berhalaman -> detail data-page JSON/HTML
  -> normalisasi + ringkasan awal artikel + pengurutan
  -> DataFrame di st.session_state
  -> pencarian/kategori -> tabel + seluruh detail + ekspor Excel di memori
```

Tiga sumber aktif adalah Benuanta, Prokal, dan Radar Tarakan. Modul Tribun Kaltara tersedia tetapi tidak didaftarkan pada `ACTIVE_SOURCES`. Selenium dan Chromium terutama mendukung jalur Tribun tersebut. Tidak ditemukan database, antrean pekerjaan, penyimpanan checkpoint, atau autentikasi aplikasi dalam kode yang ditinjau.

Deployment membangun image di GitHub Actions, mengirimnya ke GHCR, lalu melakukan pull/up melalui SSH. `.env` server menentukan image/tag yang akhirnya dijalankan.

Hal yang sudah baik: sumber aktif memakai daftar tetap; Requests memakai timeout dan verifikasi TLS bawaan; kegagalan satu sumber tidak mencegah sumber lain diproses; container memakai user non-root; port Compose diikat ke `127.0.0.1`; tersedia healthcheck; SSH memakai known_hosts; permission token Actions ditentukan per job. Pengamanan ini perlu dipertahankan.

## Daftar prioritas

| ID | Prioritas | Temuan | Pembuktian |
|---|---|---|---|
| A01 | P1 | URL dari indeks dapat memicu request ke jaringan internal | HTTP loopback terkontrol |
| A02 | P1 | Teks artikel dapat tersimpan sebagai formula Excel | Workbook dibuka kembali, tipe sel `f` |
| A03 | P1 | Hasil gagal/parsial dapat ditampilkan sebagai sukses | Tiga fixture kegagalan/kelengkapan |
| A04 | P1 | Kegagalan lanjutan membuang hasil satu sumber yang sudah terkumpul | Prokal dan Radar |
| A05 | P2 | Dekode HTML ganda merusak JSON artikel yang valid | Prokal dan Radar |
| A06 | P2 | Pencarian diperlakukan sebagai regex dan dapat memunculkan galat UI | AppTest `[` dan `.` |
| A07 | P2 | Ekspor memotong isi panjang dan gagal pada karakter kontrol | Round-trip Excel |
| A08 | P2 | Pagination/pekerjaan tidak memiliki pengaman sumber daya yang memadai | Halaman duplikat + inspeksi kode |
| A09 | P2 | Tanggal hasil GraphQL dan struktur respons terlalu dipercaya | Fixture tanggal di luar rentang |
| A10 | P2 | Data eksternal masuk ke HTML tanpa escaping | AppTest jalur metadata |
| A11 | P2 | Deployment belum memastikan image commit dan kesehatan rilis | Inspeksi workflow |
| A12 | P2 | Build tidak reproducible dan pemeriksaan kualitas belum menjadi syarat rilis | Requirements/Docker/workflow |

## Temuan dan rekomendasi

### A01 — Pengambilan URL eksternal tanpa pembatas tujuan

**Lokasi:** `scrap/benuanta.py:99-109`, `scrap/benuanta.py:13-19`, `helper/helper_function.py:25-39`. Requests untuk detail Prokal/Radar juga mengikuti redirect secara bawaan. Jalur Tribun yang belum aktif membaca URL sitemap tanpa validasi host.

`href` dari artikel langsung diteruskan ke fungsi pengambil halaman. Probe menyediakan indeks sintetis dengan tautan `http://127.0.0.1:<port>/audit`; scraper benar-benar melakukan request dan memasukkan isi server audit ke hasil.

**Dampak dan prasyarat:** jika penyerang dapat memengaruhi indeks yang diambil atau tujuan redirect suatu halaman, server aplikasi dapat diarahkan ke layanan internal. Ini adalah jalur SSRF yang dibuktikan secara lokal. Tidak ada bukti bahwa pengunjung aplikasi bisa langsung memasukkan URL arbitrer atau bahwa portal sumber sudah disusupi. Risiko produksi bergantung pada kontrol konten sumber dan akses jaringan container.

**Perbaikan:** terapkan validasi terpusat sebelum semua fetch: skema HTTPS, host sumber yang diizinkan secara eksplisit, tanpa userinfo/port tak diizinkan, dan path yang sesuai. Tolak IP loopback/private/link-local/reserved untuk seluruh hasil resolusi IPv4/IPv6. Matikan redirect otomatis atau validasi setiap hop dengan kebijakan yang sama. Tambahkan pembatasan egress sebagai lapisan tambahan untuk mengurangi risiko perubahan resolusi DNS. Gunakan URL validator yang sama untuk tautan hasil ekspor/tampilan. Panduan ini sejalan dengan [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html).

**Kriteria selesai:** fixture URL/redirect menuju loopback, private IPv4/IPv6, dan host mirip domain sumber ditolak sebelum request; artikel resmi tetap dapat diambil.

### A02 — Formula injection pada ekspor Excel

**Lokasi:** `main.py:92-98`.

Data eksternal diteruskan langsung ke `DataFrame.to_excel` dengan openpyxl. Nilai sintetis `=1+1` tersimpan sebagai sel formula (`data_type='f'`), bukan teks. Pengujian tidak menjalankan formula atau aplikasi Excel.

**Dampak dan prasyarat:** apabila judul/kategori/isi dari sumber eksternal diawali formula, pembaca file menerima formula yang dapat diproses aplikasi spreadsheet. Dampak lebih jauh bergantung pada formula, aplikasi, serta pengaturan keamanan pengguna. Tidak ada pembuktian eksekusi kode atau eksfiltrasi dalam audit ini.

**Perbaikan:** tulis kolom data eksternal sebagai string secara eksplisit dan pastikan writer tidak mengubahnya menjadi formula. Uji hasil workbook, bukan hanya string sebelum ekspor. Jangan menganggap seluruh karakter `+`, `-`, dan `@` otomatis menjadi formula pada writer ini; perilaku `=` yang telah dibuktikan harus ditutup dahulu.

**Kriteria selesai:** data `=1+1` dan fixture formula lain tetap bertipe string setelah round-trip workbook, dengan isi asli terjaga.

### A03 — Status sukses tidak menjamin keberhasilan atau kelengkapan

**Lokasi:** `helper/helper_function.py:25-39`, `scrap/benuanta.py:58-67`, `scrap/benuanta.py:134-137`, `main.py:280-293`, `main.py:202-225`.

`fetch_page` mengembalikan `None` setelah kegagalan request. Benuanta keluar dari loop dan mengembalikan daftar biasa; pemanggil mencatat `success`. Probe membuktikan kegagalan mengambil indeks menjadi `success, count=0`. Probe lain membuktikan artikel dengan `Isi=None` tetap dihitung sebagai sukses. Batas halaman Benuanta, default 200, juga dapat tercapai sebelum tanggal target tanpa status cakupan tidak lengkap.

Halaman blokir HTTP 200 atau perubahan selector berpotensi mengikuti pola kosong yang sama; kasus portal langsung belum diuji. Hasil kosong yang valid tidak boleh disamakan dengan kegagalan akses/parser atau batas pemindaian.

**Dampak:** pengguna dapat menafsirkan “tidak ada berita” sebagai fenomena nyata, padahal pengumpulan gagal atau tidak lengkap. Ini berisiko pada penggunaan hasil sebagai pendukung analisis statistik.

**Perbaikan:** kontrak hasil scraper perlu memuat data, status `success/partial/failed`, jumlah ditemukan/berhasil/gagal/isi kosong, halaman terakhir, alasan berhenti, serta apakah rentang target sudah tercakup. Propagasikan kegagalan fetch dan kegagalan validasi halaman sebagai error terstruktur. Tampilkan status parsial dan kelengkapan isi secara eksplisit.

**Kriteria selesai:** indeks gagal menjadi `failed`; limit sebelum target menjadi `partial`; isi gagal tercatat pada artikel dan ringkasan sumber; hasil kosong tervalidasi tetap `success` dengan count 0.

### A04 — Kegagalan lanjutan menghapus hasil yang sudah terkumpul

**Lokasi:** `scrap/prokal.py:153-219`, `scrap/radartarakan.py:154-220`, `main.py:280-311`, `main.py:378-384`.

Data ditampung dalam variabel lokal scraper dan baru dikembalikan setelah seluruh pagination selesai. Probe untuk kedua scraper: halaman pertama berhasil memproses satu artikel, halaman kedua gagal; hasil akhirnya tidak membawa artikel yang telah berhasil dan laporan hanya berisi error/count 0. Exception parser satu artikel juga dapat memutus sumber yang sama karena tidak ada isolasi per artikel.

Pada tingkat UI, menjalankan proses baru yang menghasilkan data kosong/gagal mengganti `scraped_df` sebelumnya menjadi `None`. Tidak tersedia arsip hasil atau pemulihan run sebelumnya.

**Perbaikan:** simpan hasil valid secara bertahap dalam kontrak hasil parsial/checkpoint; isolasi error per artikel; pertahankan hasil run sebelumnya sampai run baru diterima pengguna atau tersimpan terpisah. Data parsial harus berlabel dan tidak boleh dipresentasikan sebagai hasil lengkap. Retry hanya kegagalan yang memang aman/layak diulang dan gunakan identitas artikel untuk mencegah duplikasi.

**Kriteria selesai:** kegagalan halaman kedua tetap mengembalikan satu artikel valid dengan status parsial dan alasan kegagalan; artikel rusak tidak membuang artikel lain.

### A05 — `unescape` kedua merusak JSON yang valid

**Lokasi:** `scrap/prokal.py:126-132`, `scrap/radartarakan.py:127-133`.

Beautiful Soup telah mendekode HTML entity pada nilai atribut `data-page`. Pemanggilan `unescape` berikutnya mengubah entity yang merupakan isi string JSON. Fixture artikel `<p>Ia berkata &quot;baik&quot; hari ini.</p>` yang dikemas menjadi atribut HTML secara benar menghasilkan `JSONDecodeError` pada kedua extractor. Karakter kutip tersebut dapat muncul pada artikel normal; tidak perlu payload berbahaya.

**Perbaikan:** parse JSON dari nilai atribut setelah satu tahap dekode HTML oleh parser; validasi tipe setiap bagian payload. Hindari perbaikan string menyeluruh yang mengubah isi JSON. Catat kegagalan pada artikel terkait.

**Kriteria selesai:** fixture entity kutip/ampersand/Unicode diparse dengan benar; JSON rusak dicatat sebagai error artikel tanpa memutus sumber.

### A06 — Kata kunci menggunakan regex tanpa sengaja

**Lokasi:** `main.py:414-422`.

Ketiga `str.contains` menggunakan default regex. Dalam AppTest aplikasi sebenarnya, input `[` menyebabkan `unterminated character set at position 0`; input `.` menampilkan dua artikel yang kolom pencariannya tidak mengandung titik. Ini membuktikan galat dan ketidakakuratan pencarian, bukan crash seluruh proses server. Potensi regex mahal belum diuji dan tidak diklaim sebagai eksploitasi terbukti.

**Perbaikan:** gunakan pencarian literal, misalnya `str.contains(keyword, case=False, regex=False, na=False)`, pada kolom teks yang sudah dinormalisasi. Pastikan kolom opsional tidak menimbulkan `KeyError` atau kegagalan `.str`.

**Kriteria selesai:** `[`, `.`, `(`, dan `a+b` dicari sebagai teks biasa tanpa exception.

### A07 — Integritas dan ketahanan ekspor Excel

**Lokasi:** `main.py:92-98`, `main.py:487-503`.

Probe round-trip membuktikan isi 40.000 karakter menjadi 32.767 karakter tanpa peringatan. Karakter kontrol `\x01` menghasilkan `IllegalCharacterError`; penanganan UI hanya menangkap `ModuleNotFoundError`. Karena tab Unduh ikut dieksekusi saat rerun, data tersebut dapat menimbulkan galat bahkan sebelum pengguna mencoba mengunduh.

**Perbaikan:** validasi batas format sebelum ekspor dan sampaikan setiap perubahan data. Pertahankan isi lengkap melalui pembagian kolom/baris atau lampiran JSON/TXT; jangan memotong diam-diam. Normalisasi karakter yang tidak valid untuk XML secara terukur dan tercatat. Tangani kegagalan ekspor tanpa menghilangkan hasil tabel. Batas dan perlakuan formula ada pada [implementasi sel openpyxl](https://openpyxl.readthedocs.io/en/stable/_modules/openpyxl/cell/cell.html).

**Kriteria selesai:** artikel panjang tetap dapat direkonstruksi utuh; karakter kontrol tidak memutus UI; pengguna menerima informasi bila representasi ekspor berubah.

### A08 — Pekerjaan dapat terus berjalan atau mengulang artikel

**Lokasi:** `scrap/prokal.py:158-214`, `scrap/radartarakan.py:159-215`, `helper/helper_function.py:25-39`, `main.py:334-376`.

Loop GraphQL hanya berhenti berdasarkan artikel kosong atau `hasMorePages`. Tidak ada maksimum halaman/artikel, deteksi halaman identik, deduplikasi ID/URL, deadline keseluruhan, atau pembatalan pekerjaan. Probe mengembalikan artikel sama dengan `hasMorePages=True` pada tiga halaman; kedua scraper mengambil detail artikel identik tiga kali dan mencoba halaman keempat. Audit menghentikannya melalui exception sintetis, sehingga tidak benar-benar menjalankan loop tanpa batas.

Timeout request sudah ada, tetapi itu bukan deadline keseluruhan pekerjaan maupun batas ukuran respons. [Dokumentasi Requests](https://requests.readthedocs.io/en/latest/user/quickstart/#timeouts) menjelaskan bahwa timeout baca berkaitan dengan jeda penerimaan data.

**Perbaikan:** tetapkan batas halaman/artikel/rentang tanggal, total durasi, dan byte respons; deteksi pagination yang tidak maju; deduplikasi berdasarkan `(sumber, article_id)` atau URL kanonis; sediakan pembatalan dan status limit/parsial. Untuk banyak pengguna, batasi jumlah pekerjaan aktif di server. Verifikasi kontrol autentikasi/rate limit di gateway jika aplikasi dipublikasikan; repo saat ini mengikat port Compose ke loopback sehingga paparan publik tidak dapat disimpulkan dari kode saja.

**Kriteria selesai:** halaman berulang berhenti dengan status diagnostik, artikel hanya diambil sekali, dan batas pekerjaan berakhir tanpa menyatakan data lengkap.

### A09 — Respons GraphQL terlalu dipercaya

**Lokasi:** `scrap/prokal.py:174-198`, `scrap/radartarakan.py:175-199`.

Tanggal dikirim sebagai filter server, tetapi tanggal artikel yang dikembalikan tidak divalidasi terhadap rentang tersebut. Probe meminta 6 November 2026 dan memasukkan artikel 1 Januari 2020; kedua scraper tetap menerimanya dan mengambil detail. Variasi seperti `data:null`, `searchArticle:null`, atau `category.name:null` juga belum ditangani dengan kontrak tipe yang jelas; inspeksi kode menunjukkan potensi exception, bukan bukti respons portal saat ini.

**Perbaikan:** validasi schema minimal sebelum pemrosesan; verifikasi tanggal lokal sebelum request detail; tetapkan zona waktu tanggal bisnis secara eksplisit; gunakan ID/slug valid sebelum membangun URL. Respons tak sesuai schema harus menghasilkan error yang terlihat, bukan sekadar daftar kosong.

**Kriteria selesai:** artikel di luar tanggal tidak masuk hasil; payload null/rusak tercatat sebagai error atau artikel ditolak dengan alasan yang spesifik.

### A10 — Data eksternal dirangkai menjadi HTML mentah

**Lokasi:** `main.py:210-225`, `main.py:470-483`.

Kategori berita dan pesan error dimasukkan ke template `st.markdown(..., unsafe_allow_html=True)` tanpa escaping. AppTest membuktikan kategori sintetis `<b>AUDIT_HTML</b>` mencapai template detail sebagai tag mentah. Uji ini membuktikan jalur data ke HTML; **tidak membuktikan eksekusi JavaScript/XSS di browser**. Penyisipan tautan lewat Markdown juga perlu format URL yang tervalidasi.

**Perbaikan:** gunakan komponen teks bawaan untuk nilai eksternal atau `html.escape` pada setiap interpolasi teks di template statis. Jangan menerapkan escaping ke keseluruhan template setelah dirangkai. Gunakan kontrol link dengan URL yang sudah divalidasi. Risiko keselamatan dan pemeliharaan HTML kustom dijelaskan pada [dokumentasi st.markdown](https://docs.streamlit.io/develop/api-reference/text/st.markdown).

**Kriteria selesai:** kategori dan pesan error berisi tag tampil sebagai teks; markup statis aplikasi tetap bekerja.

### A11 — Rilis belum terikat pada image commit dan hasil healthcheck

**Lokasi:** `.github/workflows/container-deploy.yml:23-24`, `:44-46`, `:140-142`; `docker-compose.yml:7`; `Dockerfile:43-44`.

Workflow membangun tag SHA tetapi job deploy tidak menggunakan output image/digest build. Server menggunakan `IMAGE_NAME`/`IMAGE_TAG` dari `.env`, dengan contoh `latest`. Karena itu job dapat berstatus berhasil tanpa membuktikan bahwa commit workflow tersebut yang dijalankan, terutama jika `.env` masih menunjuk tag rollback atau image lain.

`docker compose up -d` tidak diikuti penantian status sehat, pemeriksaan revision image, atau pengujian fungsional ringan. Healthcheck Docker hanya menguji endpoint kesehatan Streamlit, bukan apakah aplikasi atau parser berhasil berjalan. Pembatalan workflow yang sedang deploy juga tidak sama dengan transaksi rollback.

**Perbaikan:** teruskan digest image hasil build ke deploy; verifikasi revision yang sedang berjalan; tunggu healthcheck dengan batas waktu; lakukan smoke test aplikasi; simpan referensi rilis sebelumnya dan prosedur rollback. Opsi menunggu kesehatan container tersedia pada [Docker Compose up](https://docs.docker.com/reference/cli/docker/compose/up/), dengan tetap menyesuaikan versi Compose di server. Kurangi pembatalan saat perubahan produksi sedang berlangsung atau serialkan tahap deployment hingga selesai.

**Kriteria selesai:** rilis gagal jika image/revision salah atau aplikasi tidak sehat; image rilis sebelumnya dapat dijalankan kembali secara deterministik. Temuan ini berasal dari kode, belum diuji pada server.

### A12 — Dependensi dan pemeriksaan rilis belum terkunci

**Lokasi:** `requirements.txt:1-8`, `Dockerfile:1`, `:34-35`, `.github/workflows/container-deploy.yml:26-62`.

Seluruh dependensi Python tanpa versi; base image memakai tag yang dapat berubah; Actions memakai major tag. Tidak ada workflow pengujian aplikasi/parser atau pemindaian dependensi sebelum deployment. Checkout yang sama dapat menghasilkan runtime berbeda di waktu berbeda.

`pip-audit -r requirements.txt` saat audit meresolusi **50 paket** dan melaporkan **0 kerentanan dikenal**. Ini adalah hasil resolusi baru pada lingkungan audit, bukan audit versi di image produksi. Versi Streamlit/pandas yang teresolusi berbeda dari probe utama; daftar persis ada di `dependency-audit.json`. Hasil bersih tidak meniadakan kerentanan logika yang dibuktikan di atas dan tidak mencakup paket OS/Chromium.

**Perbaikan:** kunci seluruh dependensi transitif beserta hash, nyatakan Python yang didukung, dan perbarui secara terjadwal melalui CI. Pin Actions ke commit SHA yang diverifikasi, sejalan dengan [panduan keamanan GitHub Actions](https://docs.github.com/en/actions/reference/security/secure-use). Tambahkan tes parser fixture, smoke test Streamlit, dan audit dependensi/image pada PR sebelum deploy. Pindahkan nilai konfigurasi/secret dari interpolasi langsung ke skrip Actions menjadi environment variable atau input terstruktur; validasi port/path sebelum membentuk perintah SSH. Tidak ada eksploitasi secret atau kebocoran secret yang dibuktikan.

**Kriteria selesai:** instalasi bersih menghasilkan versi identik; perubahan parser/filter/ekspor yang merusak perilaku terdeteksi sebelum rilis; referensi image/actions dapat ditelusuri ke konten tetap.

## Optimasi yang paling bernilai

| ID | Lokasi / masalah | Perubahan yang disarankan | Ukuran keberhasilan |
|---|---|---|---|
| O01 | `main.py:439-503`: seluruh detail dan Excel dihitung pada setiap rerun | Pilih satu artikel untuk detail atau paginasi; siapkan Excel atas permintaan; cache hasil ekspor berdasarkan identitas/isi hasil filter dan versi exporter | Pada 250 artikel, render hanya halaman/detail aktif dan jangan membuat Excel sebelum diperlukan |
| O02 | Detail artikel diambil berurutan, tanpa cache; kebijakan retry berbeda antar sumber | Cache berdasarkan sumber/ID/URL dengan TTL; retry terbatas untuk kegagalan sementara dengan backoff dan Retry-After; setelah ada batas pekerjaan, ukur concurrency kecil per host dengan session/worker yang jelas | Ukur request/artikel, cache hit, durasi per sumber, 429/error; throughput naik tanpa menambah rate limit |
| O03 | Prokal/Radar hampir identik; UI dan fungsi data bercampur dalam `main.py`; Benuanta memakai wildcard import | Satukan klien GraphQL dan parsing detail menjadi adapter terkonfigurasi; pisahkan pipeline, model hasil, exporter, dan UI; import eksplisit; tambahkan fixture berdasarkan variasi payload nyata yang sudah disanitasi | Perubahan parser bersama cukup satu tempat; fungsi data dapat diimpor tanpa menjalankan UI |
| O04 | `main.py:125-157` memindai semua `div/span/label` saat DOM berubah; CSS bergantung selector internal | Utamakan lokalisasi/widget resmi; bila skrip masih perlu, batasi node yang dipantau, debounce, dan putus observer saat tidak diperlukan; pin dan verifikasi kontrak UI saat upgrade | Tidak melakukan pemindaian seluruh DOM pada setiap perubahan; tidak menggandakan observer |
| O05 | Docker membawa Chromium, driver, Selenium, dan library GUI untuk sumber Tribun yang tidak aktif | Ukur ukuran image/startup; pertimbangkan image dasar tanpa browser dan varian browser opsional; jika diaktifkan, evaluasi penghapusan `--no-sandbox` dan isolasi container | Ukuran image dan permukaan patch berkurang; jalur browser diuji terpisah |

**Bukti O01:** AppTest dengan 250 baris membuat 250 expander saat tab tabel menjadi default. Dua rerun membuat Excel dua kali tanpa satu pun klik unduh. Ini adalah pengukuran jumlah operasi, bukan klaim persentase percepatan. [Dokumentasi st.tabs](https://docs.streamlit.io/develop/api-reference/layout/st.tabs) menjelaskan bahwa perilaku default menjalankan seluruh konten tab; opsi rendering kondisional bergantung versi Streamlit yang nantinya dikunci.

Untuk O02, lakukan pembatasan dan observabilitas sebelum paralelisasi. Session Requests saat ini merupakan objek global; hindari membagikannya ke worker tanpa desain kepemilikan yang jelas. Jangan menggunakan judul berita sebagai identitas deduplikasi karena judul sama dapat merujuk artikel berbeda.

Peningkatan kualitas data: simpan `run_id`, waktu pengambilan, tanggal/sumber yang diminta, cakupan yang benar-benar dicapai, URL/ID kanonis, status isi, dan versi parser. Ekspor sebaiknya menyertakan sheet metadata serta ringkasan artikel gagal. Ringkasan saat ini mengambil kalimat awal, sehingga label/deskripsinya perlu mencerminkan metode tersebut.

## Urutan pelaksanaan

1. **Lindungi pengambilan dan ekspor:** A01, A02; tambahkan fixture batas kepercayaan URL dan tipe sel Excel.
2. **Benahi kejujuran hasil dan pemulihan:** A03, A04, A05; tetapkan kontrak hasil parsial serta error per artikel.
3. **Tutup galat interaksi/data:** A06, A07, A09, A10.
4. **Batasi pekerjaan dan tegakkan mutu rilis:** A08, A11, A12; mulai mencatat durasi/request/memori sebagai baseline.
5. **Optimalkan dari bukti:** O01 dahulu, lalu cache/retry terkontrol dan pengurangan duplikasi adapter; paralelisasi setelah batas sumber daya dan identitas artikel jelas.

Tidak perlu mengganti framework sebelum menyelesaikan masalah ini. Struktur adapter sumber dan UI Streamlit yang ada masih dapat dikembangkan untuk kebutuhan pengumpulan berita berskala kecil sampai menengah, dengan kapasitas yang harus ditentukan lewat pengukuran nyata.

## Hasil alat dan reproduksi

- **14/14 skenario pada masing-masing dua lingkungan:** seluruh perilaku target teramati pada lingkungan utama dan instalasi baru, total 28 eksekusi probe; rincian ada pada kedua file evidence.
- **Bandit:** 1.378 baris Python aplikasi dipindai, dua peringatan B311 tingkat rendah pada `random.uniform` di modul Tribun. Keduanya dipakai untuk jeda, bukan tujuan kriptografi, sehingga tidak dihitung sebagai kerentanan yang perlu diperbaiki.
- **pip-audit:** 50 dependensi hasil resolusi requirements, 0 kerentanan dikenal. Tidak mencakup audit image/OS atau inventaris server.
- **Compose:** `docker compose --env-file .env.example config --quiet` berhasil. Build dan startup container belum dijalankan karena Docker daemon tidak tersedia.
- **Kompatibilitas instalasi baru:** virtual environment terpisah tanpa paket global, dipasang dari `requirements.txt`. Startup AppTest tidak menghasilkan exception; 14 skenario juga teramati dengan Streamlit 1.67.0, pandas 3.1.1, requests 2.34.2, Pillow 13.0.0, Beautiful Soup 4.15.0, dan openpyxl 3.1.5. Startup memberikan peringatan deprecation `use_container_width` dan `st.components.v1.html`, sehingga migrasi API perlu masuk pemeliharaan. Ini tetap pengujian Windows/Python 3.11, bukan bukti runtime image Linux/Python 3.12.

Jalankan ulang probe dari root proyek dalam virtual environment yang berisi dependensi aplikasi:

```powershell
python docs/audit/2026-11-06/reproduce.py
# Simpan hasil lingkungan lain tanpa menimpa bukti utama:
python docs/audit/2026-11-06/reproduce.py --output docs/audit/2026-11-06/evidence-other.json
```

Skrip menulis ulang `evidence.json` di direktori ini dan hanya memulai HTTP server loopback sementara. Beberapa probe mengharapkan bug masih ada; setelah perbaikan, ubah menjadi tes regresi yang menegaskan perilaku aman/benar. Probe tidak mencakup pengujian browser visual, kondisi portal langsung, kinerja jaringan produksi, atau pengujian isolasi container.
