# Vaultbox

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

## Status

The project is being initialized. Implementation details and deployment documentation will be added as the service evolves.

## License

Vaultbox is released under the MIT License. See [LICENSE](LICENSE).
