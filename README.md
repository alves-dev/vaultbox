# Vaultbox

<p align="center">
  <img src="vaultbox/static/vaultbox-mark.png" alt="Vaultbox" width="333" height="333">
</p>

Vaultbox is a lightweight, stateless secrets encryption service powered by [SOPS](https://github.com/getsops/sops) and [age](https://github.com/FiloSottile/age). It provides a REST API and web interface for secure dotenv management.

## Goals

- Keep secret management simple, portable, and self-hostable.
- Encrypt dotenv-style configuration at rest without storing private keys or credentials in the service.
- Provide a small, observable API that fits homelab and containerized deployments.
- Make common secrets workflows accessible through both HTTP clients and a browser interface.

## Main features

- Stateless encryption and decryption workflows using SOPS and age.
- REST API suitable for automation and integrations.
- Web interface for managing encrypted dotenv content.
- Docker-friendly deployment model.
- Python-based implementation designed for straightforward operation and maintenance.

## Security

Vaultbox is intended to operate without persisting private keys, credentials, or plaintext secrets. Configure key material through secure runtime mechanisms such as mounted files, environment injection, or an external secret store. Never commit real `.env` files, age private keys, cloud credentials, or other sensitive material.

This repository is initialized with a Python-focused `.gitignore`; only example configuration files containing placeholders should be committed.

## Quick start

Requirements: Docker with Compose (for the container) or Python 3.11+ and SOPS/age (for a direct local run).

Generate an age identity and recipient, then create the runtime values:

```bash
age-keygen -o age.key
chmod 600 age.key
grep '^# public key:' age.key
```

For Docker, copy `.env.vaultbox.example` to `.env.vaultbox`, set the values (including the complete contents of `age.key`), then run `docker compose up --build -d`. The service is available at `http://localhost:8000`; set `VAULTBOX_COOKIE_SECURE=true` when it is behind HTTPS. The image bundles pinned SOPS and age releases and verifies their release checksums during build. Startup performs a real SOPS+age round-trip and the container exits with an informative log if configuration or key material is invalid.

The health endpoint is `GET /health`. There is no readiness endpoint: a running container has already passed startup validation. API documentation is disabled by default; set `VAULTBOX_ENABLE_DOCS=true` only for local or controlled environments.

The repository includes a GitHub Actions workflow that builds the image on pull requests and publishes tagged/`main` builds to GitHub Container Registry (`ghcr.io`) on pushes. The published image can be pulled with `docker pull ghcr.io/<owner>/<repository>:main`.

`VAULTBOX_API_KEYS` is a JSON array of independent tokens. For safer configuration, entries may be `sha256:<64-hex-digest>` instead of plaintext tokens; calculate the digest with `printf %s "$TOKEN" | sha256sum`. The web login is independent from API keys.

API example:

```bash
curl -fsS -X POST http://localhost:8000/api/v1/encrypt \
  -H "X-API-Key: $VAULTBOX_API_KEY" -H 'Content-Type: text/plain' \
  --data-binary $'A=1\n# comment\n' > .env.enc
curl -fsS -X POST http://localhost:8000/api/v1/decrypt \
  -H "X-API-Key: $VAULTBOX_API_KEY" -H 'Content-Type: text/plain' \
  --data-binary @.env.enc
```

Para simular localmente o fluxo completo pela API, altere somente `VAULTBOX_API_KEY` no helper e execute:

```bash
./.dev/vaultbox-local.sh
```

Use `./deploy.sh` from a stack directory containing `.env.enc`; set `VAULTBOX_API_KEY` only in the server environment. It writes `.env` atomically and runs Compose only after a successful decrypt. Keep `.env`, the age identity, API keys and session secret out of Git. Back up the age identity securely: losing it makes existing ciphertext unrecoverable.

Run tests with `pip install -e '.[test]' && pytest`. The tests use a fake SOPS executable for deterministic API coverage; the Docker image validates the real SOPS+age binaries and performs a startup round-trip before serving traffic.

## License

Vaultbox is released under the MIT License. See [LICENSE](LICENSE).
