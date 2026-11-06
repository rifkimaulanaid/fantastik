# Memasang FANTASTIK di server

Panduan ini untuk pengelola server. Aplikasi dibungkus dalam image Docker, dibangun lewat GitHub Actions, lalu dikirim ke server lewat SSH.

## Yang perlu disiapkan

- Server Linux dengan Docker Engine, Docker Compose, dan `flock` dari util-linux.
- Compose harus mendukung `--wait`, `--wait-timeout`, dan beberapa `--env-file` dalam satu perintah.
- User SSH yang bisa menjalankan Docker dan menulis ke folder pemasangan, misalnya `/opt/fantastik`.
- Akses HTTPS keluar ke GHCR dan portal berita yang dipakai aplikasi.

Port awalnya hanya dibuka di `127.0.0.1:8501`. Kalau aplikasi akan diakses dari internet, siapkan reverse proxy untuk HTTPS, pembatasan akses, dan login bila diperlukan.

Hasil pencarian disimpan di volume `fantastik_data`, yang dipasang ke `/app/data`. Container berjalan sebagai UID 10001, dengan batas memori 1 GiB, 1,5 CPU, dan 128 PID. Folder sistem container dibuat read-only dan Linux capabilities dilepas. Volume data tetap bisa ditulis.

Aplikasi sudah memeriksa alamat tujuan sebelum mengambil berita. Firewall dan aturan koneksi keluar di server tetap perlu diatur oleh pengelola.

## Pengaturan awal

Buat folder pemasangan yang dimiliki user SSH. Salin `.env.example` menjadi `.env`, lalu sesuaikan `IMAGE_NAME`, `APP_PORT`, dan zona waktunya. Simpan `.env` di server.

Isi GitHub Secrets berikut:

| Secret | Isi |
|---|---|
| `SERVER_HOST` | Hostname atau IPv4 server |
| `SERVER_PORT` | Nomor port SSH |
| `SERVER_USER` | User SSH, tanpa spasi |
| `SERVER_SSH_KEY` | Private key khusus untuk deployment |
| `SERVER_SSH_KNOWN_HOSTS` | Host key server yang sudah diperiksa |
| `SERVER_DEPLOY_PATH` | Path absolut folder pemasangan, tanpa spasi atau `..` |

Untuk image GHCR private, isi juga `GHCR_USERNAME` dan `GHCR_TOKEN`. Token ini cukup punya akses `read:packages`. Proses build/push memakai `GITHUB_TOKEN` dengan izin `packages:write`.

Workflow menggunakan environment GitHub bernama `production`. Jika butuh persetujuan sebelum rilis, atur approval rule di pengaturan environment tersebut.

## Apa yang terjadi saat rilis?

1. Setiap PR dan push menjalankan tes kode, tes singkat aplikasi/ekspor, Bandit, dan audit library pada Windows/Linux Python 3.12. Job Linux juga menguji tampilan desktop dan ponsel dengan berita contoh.
2. Setelah tes lulus, push ke `main` atau workflow manual pada `main` membangun image. Versi library, base Python, dan Actions sudah dikunci. Browser Chromium tidak ikut dipasang karena tiga sumber aktif tidak membutuhkannya.
3. Image dikirim ke GHCR dengan tag `latest` dan `sha-<full-commit>`. Saat memasang ke server, workflow memakai **digest image hasil build**. Digest adalah ID tetap untuk image tersebut, sehingga rilis tidak bergantung pada tag yang bisa berubah.
4. CI menjalankan tes singkat image tanpa jaringan dan memeriksa paket OS/aplikasi dengan Trivy. Temuan HIGH/CRITICAL yang sudah punya perbaikan akan menghentikan rilis. Rilis juga berhenti kalau scanner atau database-nya tidak bisa dipakai.
5. Workflow mengirim `docker-compose.yml`, `.env.example`, dan `deploy.sh` ke server. File `.env` yang sudah ada tetap dipakai.
6. `deploy.sh` memasang lock dengan `flock` agar dua rilis tidak berjalan bersamaan. Script menarik image, memeriksa label commit, lalu menguji aplikasi tanpa jaringan sebelum mengganti container yang aktif.
7. Compose menunggu container siap, maksimal 90 detik. Script lalu memeriksa commit container dan mencoba fitur aplikasi/ekspor sekali lagi.
8. Kalau pemeriksaan setelah pergantian gagal, script mencoba menjalankan kembali image ID lokal sebelumnya. Status rilis tetap gagal agar masalahnya terlihat di log. Pada pemasangan pertama belum ada image lama untuk dikembalikan.
9. Kalau berhasil, digest disimpan ke `.release.env`. Referensi rilis sebelumnya disalin ke `.previous-release.env`. Image lama tidak dihapus otomatis.

Push berikutnya tidak membatalkan rilis yang sedang berjalan. Jika upaya kembali ke versi lama juga gagal, script menuliskan pesannya di log server.

## Restart dan melihat log

Setelah rilis pertama, sertakan `.release.env` agar restart memakai image yang sama dengan rilis terakhir:

```bash
cd /opt/fantastik
docker compose --env-file .env --env-file .release.env up -d --no-build --wait --wait-timeout 90
docker compose --env-file .env --env-file .release.env ps
docker compose --env-file .env --env-file .release.env logs --tail 100 fantastik
```

## Kembali ke versi sebelumnya

Periksa dulu isi `.previous-release.env`. Jika referensinya sesuai dengan versi yang ingin dipakai, jalankan:

```bash
docker compose --env-file .env --env-file .previous-release.env pull fantastik
docker compose --env-file .env --env-file .previous-release.env up -d --no-build --wait --wait-timeout 90 fantastik
```

Setelah rollback manual, sesuaikan `.release.env` dengan image yang dipilih. Dengan begitu, restart berikutnya tetap memakai versi yang benar.

Hindari `docker compose down -v` jika hasil pencarian masih dibutuhkan. Opsi `-v` akan menghapus volume data.

## Hasil yang tersimpan di server

Aplikasi menyimpan 20 file hasil terbaru. File diganti setelah penulisan selesai, supaya pembaca tidak membuka file yang baru terisi sebagian. Jeda penyimpanannya sekitar dua detik.

Jika proses terputus, pengguna bisa membuka hasil yang sudah tersimpan lewat sidebar. Hasilnya ditandai belum lengkap dan pencarian tidak dilanjutkan otomatis.

Pada server yang dipakai bersama, hasil tersimpan bisa dibuka dari sesi lain di aplikasi yang sama. Isinya berupa berita publik dan pilihan pencarian. Kalau pilihan pencarian perlu dibatasi per pengguna, atur akses melalui gateway. Masukkan volume data ke jadwal backup server.

## Yang sudah dan belum diuji

Tes rollback lokal memakai Docker pengganti untuk memeriksa urutan perintah, penanganan gagal, dan pemilihan image. Tes ini belum membuktikan bahwa deployment di server berjalan.

Build image, container Linux, reverse proxy, dan GitHub Secrets perlu diperiksa lewat CI atau server. Pada tahap audit, Docker daemon lokal tidak tersedia dan tidak ada deployment ke server produksi.
