# Deployment FANTASTIK

## Persyaratan

- Server Linux, Docker Engine, Docker Compose yang mendukung `--wait`, `--wait-timeout`, serta beberapa `--env-file`, dan util-linux `flock`.
- Port host default `127.0.0.1:8501`. Reverse proxy bertanggung jawab atas HTTPS, autentikasi bila diperlukan, dan rate limit sebelum aplikasi dipublikasikan.
- Checkpoint disimpan pada named volume `fantastik_data` di `/app/data`. Container memakai UID 10001, root filesystem read-only, tanpa Linux capabilities, dengan batas memori 1 GiB/1,5 CPU/128 PID.
- Host memerlukan akses HTTPS keluar ke GHCR dan portal berita yang disetujui. Transport aplikasi memblokir tujuan nonpublik dan memin IP koneksi; kebijakan firewall/egress host tetap dikelola administrator.

## Setup server

Buat direktori deploy yang dimiliki user SSH, misalnya `/opt/fantastik`. User tersebut memerlukan hak Docker. Simpan `.env` dari `.env.example`, sesuaikan `IMAGE_NAME`, `APP_PORT`, dan timezone. Jangan menyimpan secret di repository.

GitHub Secrets wajib: `SERVER_HOST`, `SERVER_PORT`, `SERVER_USER`, `SERVER_SSH_KEY`, `SERVER_SSH_KNOWN_HOSTS`, `SERVER_DEPLOY_PATH`. Gunakan hostname/IPv4, username tanpa spasi, port numerik, dan path absolut tanpa spasi atau `..`. SSH memverifikasi host key dan memakai key khusus deployment.

Untuk package private, isi `GHCR_USERNAME` dan `GHCR_TOKEN` dengan token khusus `read:packages`. Token build/push memakai `GITHUB_TOKEN` dengan permission `packages:write`. Workflow memakai environment `production`; protection/approval rule dapat dikelola melalui pengaturan GitHub sesuai kebijakan organisasi.

## Alur rilis

1. PR dan push menjalankan tes unit/integrasi, smoke test UI/ekspor, Bandit, dan audit dependensi pada Windows/Linux Python 3.12. Job Linux juga memeriksa UI browser desktop/ponsel dengan data sintetis, termasuk kontras tanggal, fokus, navigasi artikel, dan posisi hasil.
2. Setelah pemeriksaan berhasil, push `main` atau workflow manual pada `main` membangun image. Dependensi dipasang dari lock berhash, Actions dipin ke SHA, dan base Python dipin ke digest. Chromium tidak dibawa karena sumber aktif tidak memerlukannya.
3. Image didorong ke GHCR dengan tag `latest` dan `sha-<full-commit>`. **Deployment menggunakan digest hasil build**, bukan tag `latest` dari `.env` server.
4. CI menjalankan smoke test image tanpa network dan memindai paket OS/aplikasi menggunakan Trivy yang dipin ke digest. Temuan HIGH/CRITICAL yang sudah memiliki perbaikan memblokir deployment. Jika scanner/database tidak tersedia, deployment juga tidak dilanjutkan.
5. Workflow mengirim `docker-compose.yml`, `.env.example`, dan `deploy.sh`. File `.env` server dipertahankan.
6. `deploy.sh` mengunci direktori dengan `flock`, menarik image, memverifikasi label revision, lalu menjalankan smoke test image dengan network dinonaktifkan sebelum mengganti container aktif.
7. Compose menunggu status sehat maksimal 90 detik. Revision container diperiksa lagi dan smoke test aplikasi/ekspor dijalankan pada container yang aktif.
8. Jika pemeriksaan setelah pergantian gagal, script mencoba memulihkan **image ID lokal sebelumnya** dan tetap mengembalikan status gagal. Rilis pertama tidak memiliki image sebelumnya untuk rollback. Kegagalan rollback dinyatakan jelas di log.
9. Setelah berhasil, digest tersimpan atomik pada `.release.env`; referensi sebelumnya ada pada `.previous-release.env`. Image lama tidak dipangkas otomatis.

Workflow tidak membatalkan deployment aktif ketika ada push berikutnya. Lock server juga mencegah dua deployment berjalan bersamaan.

## Restart, pengamatan, dan rollback manual

Sesudah rilis pertama, gunakan `.release.env` agar restart tetap memakai digest yang telah diverifikasi:

```bash
cd /opt/fantastik
docker compose --env-file .env --env-file .release.env up -d --no-build --wait --wait-timeout 90
docker compose --env-file .env --env-file .release.env ps
docker compose --env-file .env --env-file .release.env logs --tail 100 fantastik
```

Untuk kembali ke referensi rilis sebelumnya, tinjau dahulu isi `.previous-release.env`, kemudian jalankan:

```bash
docker compose --env-file .env --env-file .previous-release.env pull fantastik
docker compose --env-file .env --env-file .previous-release.env up -d --no-build --wait --wait-timeout 90 fantastik
```

Sesudah rollback manual, sesuaikan `.release.env` dengan referensi yang dipilih agar restart berikutnya konsisten. Jangan gunakan `docker compose down -v` saat ingin mempertahankan checkpoint.

## Checkpoint dan pemulihan

Aplikasi menyimpan maksimal 20 checkpoint terbaru, secara atomik dan dengan interval penulisan disk sekitar dua detik. Checkpoint proses yang terputus diberi status belum lengkap ketika dipulihkan melalui sidebar. Pemulihan menampilkan data tersimpan; tidak melanjutkan request secara otomatis.

Pada server bersama, checkpoint di disk tersedia lintas sesi aplikasi dan hanya berisi berita publik/parameter pengumpulan. Batasi akses aplikasi pada gateway bila parameter riset memerlukan pembatasan pengguna. File unduhan JSON dapat digunakan sebagai arsip lengkap, termasuk metadata dan alasan kegagalan. Volume perlu masuk kebijakan backup server.

## Batas verifikasi lokal

Tes rollback menggunakan Docker pengganti untuk menguji alur perintah, status gagal, dan pemilihan image; bukan bukti deployment server. Build/runtime Linux yang sebenarnya dan konfigurasi reverse proxy/Secrets harus diverifikasi oleh CI/server. Docker daemon tidak tersedia pada lingkungan audit lokal, sehingga tidak ada deployment produksi yang dilakukan dari sesi perbaikan ini.
