#!/usr/bin/env bash
# Inputs are validated before use. No secret is interpolated into this script.
set -Eeuo pipefail
deploy_path=${1:?deployment path required}
release_image=${2:?image digest required}
revision=${3:?git revision required}
[[ "$deploy_path" =~ ^/[a-zA-Z0-9_./-]+$ && "$deploy_path/" != *"/../"* ]]
[[ "$release_image" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[a-f0-9]{64}$ ]]
[[ "$revision" =~ ^[a-f0-9]{40}$ ]]
cd "$deploy_path"
test -f .env
exec 9>.deploy.lock
flock -n 9

compose() { docker compose --env-file .env "$@"; }
previous_id=$(compose ps -q fantastik)
previous_image=""
if [ -n "$previous_id" ]; then
  previous_image=$(docker inspect --format '{{.Image}}' "$previous_id")
fi
mutated=false
rollback() {
  code=$1
  trap - ERR
  if $mutated && [ -n "$previous_image" ]; then
    echo "Rilis gagal; memulihkan image sebelumnya." >&2
    APP_IMAGE="$previous_image" compose up -d --no-build --pull never --wait --wait-timeout 90 fantastik || {
      echo "Rollback gagal; periksa status container di server." >&2
    }
  fi
  exit "$code"
}
trap 'rollback $?' ERR

export APP_IMAGE="$release_image"
compose pull fantastik
actual=$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$release_image")
test "$actual" = "$revision"
docker run --rm --network none --memory 512m --pids-limit 128 \
  --security-opt no-new-privileges:true "$release_image" python scripts/smoke_test.py
mutated=true
compose up -d --no-build --wait --wait-timeout 90 fantastik
current_id=$(compose ps -q fantastik)
actual=$(docker inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$current_id")
test "$actual" = "$revision"
compose exec -T fantastik python scripts/smoke_test.py

if [ -f .release.env ]; then
  cp .release.env .previous-release.env
fi
printf 'APP_IMAGE=%s\n' "$release_image" > .release.env.tmp
mv .release.env.tmp .release.env
echo "Rilis $revision sehat dan telah diverifikasi."
