#!/usr/bin/env bash
set -euo pipefail
umask 077

: "${VAULTBOX_API_KEY:?VAULTBOX_API_KEY não configurada}"
: "${VAULTBOX_URL:=https://vaultbox.internal.alves-dev.com}"

tmp_env="$(mktemp ./.env.XXXXXX)"
cleanup() { rm -f -- "$tmp_env"; }
trap cleanup EXIT

curl --fail --silent --show-error \
  --connect-timeout 5 --max-time 30 --retry 2 \
  -X POST "${VAULTBOX_URL%/}/api/v1/decrypt" \
  -H "X-API-Key: ${VAULTBOX_API_KEY}" \
  -H 'Content-Type: text/plain' \
  --data-binary @.env.enc --output "$tmp_env"

mv -f -- "$tmp_env" .env
docker compose up -d
