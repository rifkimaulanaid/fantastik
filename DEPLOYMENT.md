# Deployment Fantastik

## Identifikasi Proyek

Proyek ini adalah aplikasi **Python Streamlit**, bukan React, Vite, Next.js, Laravel, atau Express.

Indikator utamanya:
- entrypoint aplikasi ada di `main.py`
- dependency didefinisikan di `requirements.txt`
- runtime web memakai `streamlit`

## Alur Deployment

1. Developer push perubahan ke branch `main`.
2. GitHub Actions build Docker image dari repository ini.
3. Image dipush ke **GitHub Container Registry (GHCR)** dengan tag:
   - `latest`
   - `sha-<commit-sha>`
4. GitHub Actions melakukan SSH ke server.
5. Server menerima file deployment minimal:
   - `docker-compose.yml`
   - `.env.example`
6. Server menjalankan:
   - `docker compose pull`
   - `docker compose up -d`
7. Source code aplikasi tidak dibuild di server.

## Struktur File yang Disarankan

```text
.
|- .github/
|  |- workflows/
|     `- container-deploy.yml
|- .streamlit/
|  `- config.toml
|- asset/
|- helper/
|- scrap/
|- styles/
|- .dockerignore
|- .env.example
|- DEPLOYMENT.md
|- docker-compose.yml
|- Dockerfile
|- main.py
`- requirements.txt
```

## File yang Dipakai untuk Production

- `Dockerfile`
  Membuat image production aplikasi Streamlit.
- `docker-compose.yml`
  Dipakai di server untuk menjalankan image dari GHCR.
- `.env.example`
  Template variabel environment untuk server.
- `.github/workflows/container-deploy.yml`
  Build, push, dan deploy otomatis.

## GitHub Secrets yang Perlu Dibuat

### Wajib

- `SERVER_HOST`
  IP atau hostname server.
- `SERVER_PORT`
  Port SSH server, misalnya `22`.
- `SERVER_USER`
  User SSH di server, misalnya `deploy`.
- `SERVER_SSH_KEY`
  Private key untuk login SSH dari GitHub Actions.
- `SERVER_SSH_KNOWN_HOSTS`
  Output host key server, biasanya dari `ssh-keyscan -H <host>`.
- `SERVER_DEPLOY_PATH`
  Folder deployment di server, misalnya `/opt/fantastik`.

### Opsional tapi Direkomendasikan untuk Image Private

- `GHCR_USERNAME`
  Username GitHub pemilik token registry.
- `GHCR_TOKEN`
  Personal Access Token atau fine-grained token dengan minimal akses `read:packages`.

Catatan:
- Workflow build dan push ke GHCR menggunakan `GITHUB_TOKEN` bawaan GitHub Actions.
- `GHCR_USERNAME` dan `GHCR_TOKEN` dibutuhkan jika package GHCR diset **private** dan server perlu login sebelum pull.

## Setup Awal di PC Server

Asumsi:
- Docker dan Docker Compose sudah terpasang
- server berbasis Linux

### 1. Buat user deploy opsional

```bash
sudo adduser --disabled-password --gecos "" deploy
sudo usermod -aG docker deploy
```

### 2. Buat direktori deployment

```bash
sudo mkdir -p /opt/fantastik
sudo chown -R deploy:deploy /opt/fantastik
```

### 3. Siapkan file `.env`

Masuk ke direktori deploy:

```bash
cd /opt/fantastik
cp .env.example .env
```

Isi `.env` contoh:

```env
IMAGE_NAME=ghcr.io/owner/repo
IMAGE_TAG=latest
CONTAINER_NAME=fantastik
APP_PORT=8501
TZ=Asia/Makassar
```

Ganti `owner/repo` dengan nama image GHCR aktual Anda.

### 4. Login registry jika image private

```bash
echo "<GHCR_TOKEN>" | docker login ghcr.io -u "<GHCR_USERNAME>" --password-stdin
```

### 5. Uji pull dan run manual sekali

```bash
cd /opt/fantastik
docker compose --env-file .env pull
docker compose --env-file .env up -d
docker compose ps
```

## Cara Kerja Workflow GitHub Actions

Workflow `container-deploy.yml` memiliki dua job:

### `build-and-push`

- checkout repository
- login ke GHCR
- build image dari `Dockerfile`
- push image ke GHCR dengan tag `latest` dan `sha-<commit-sha>`

### `deploy`

- checkout repository
- buka koneksi SSH ke server
- upload `docker-compose.yml` dan `.env.example`
- login ke GHCR di server jika secret registry tersedia
- jalankan:
  - `docker compose pull`
  - `docker compose up -d --remove-orphans`

## Catatan Keamanan

### SSH Key

- gunakan key khusus deployment, jangan key pribadi harian
- batasi key itu hanya untuk user deploy
- simpan private key hanya di GitHub Secret `SERVER_SSH_KEY`
- simpan host fingerprint di `SERVER_SSH_KNOWN_HOSTS`, jangan gunakan `StrictHostKeyChecking=no`

### Registry Token

- jika image GHCR private, gunakan token khusus read-only untuk server
- jangan gunakan PAT dengan scope lebih luas dari yang dibutuhkan
- minimal akses untuk server adalah `read:packages`

### File `.env`

- file `.env` hanya disimpan di server, jangan commit ke repository
- `.env.example` boleh di-commit karena hanya template
- jika nanti ada secret aplikasi, simpan di `.env` server atau secret manager, bukan di workflow YAML

### GitHub Actions

- workflow saat ini tidak melakukan `docker compose build` di server
- workflow tidak meng-copy source code aplikasi ke server, hanya file deployment minimum
- jika ingin review manual sebelum deploy, tambahkan protection rules pada branch `main`

## Catatan Operasional

- deployment ini cocok untuk production sederhana dengan satu server
- jika image dibuat private, pastikan server bisa login ke GHCR
- jika nanti ingin rollback, ubah `IMAGE_TAG` di `.env` server menjadi tag `sha-<commit-sha>` tertentu lalu jalankan:

```bash
docker compose --env-file .env pull
docker compose --env-file .env up -d
```
