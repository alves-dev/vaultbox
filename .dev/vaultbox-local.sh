#!/usr/bin/env bash
set -euo pipefail
umask 077

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

# Altere somente esta linha.
VAULTBOX_API_KEY='replace-with-a-long-random-token'

curl --fail --silent --show-error \
  --connect-timeout 5 --max-time 30 --retry 2 \
  -X POST 'http://localhost:8000/api/v1/encrypt' \
  -H "X-API-Key: ${VAULTBOX_API_KEY}" \
  -H 'Content-Type: text/plain; charset=utf-8' \
  --data-binary @.dev/.env \
  --output .dev/.env.enc

curl --fail --silent --show-error \
  --connect-timeout 5 --max-time 30 --retry 2 \
  -X POST 'http://localhost:8000/api/v1/decrypt' \
  -H "X-API-Key: ${VAULTBOX_API_KEY}" \
  -H 'Content-Type: text/plain; charset=utf-8' \
  --data-binary @.dev/.env.enc \
  --output .dev/.env.decrypted

cmp --silent .dev/.env .dev/.env.decrypted
echo 'OK: encrypt/decrypt preservou .dev/.env'
