FROM python:3.12-slim AS runtime

ARG SOPS_VERSION=3.9.4
ARG AGE_VERSION=1.2.1
ARG AGE_SHA256_AMD64=7df45a6cc87d4da11cc03a539a7470c15b1041ab2b396af088fe9990f7c79d50
ARG AGE_SHA256_ARM64=
ARG TARGETARCH
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/* \
 && set -eux; \
    case "$TARGETARCH" in amd64) SOPS_ARCH=amd64; AGE_ARCH=amd64;; arm64) SOPS_ARCH=arm64; AGE_ARCH=arm64;; *) echo "unsupported architecture: $TARGETARCH" >&2; exit 1;; esac; \
    curl -fsSL "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.linux.${SOPS_ARCH}" -o /usr/local/bin/sops; \
    curl -fsSL "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.checksums.txt" -o /tmp/sops.checksums; \
    grep "sops-v${SOPS_VERSION}.linux.${SOPS_ARCH}$" /tmp/sops.checksums | sed "s#  .*#  /usr/local/bin/sops#" | sha256sum -c -; \
    curl -fsSL "https://github.com/FiloSottile/age/releases/download/v${AGE_VERSION}/age-v${AGE_VERSION}-linux-${AGE_ARCH}.tar.gz" -o /tmp/age.tar.gz; \
    AGE_SHA256="$AGE_SHA256_AMD64"; if [ "$AGE_ARCH" = arm64 ]; then AGE_SHA256="$AGE_SHA256_ARM64"; fi; \
    if [ -n "$AGE_SHA256" ]; then echo "$AGE_SHA256  /tmp/age.tar.gz" | sha256sum -c -; else echo "AGE_SHA256_ARM64 must be supplied for arm64 builds" >&2; exit 1; fi; \
    tar -xzf /tmp/age.tar.gz -C /tmp; \
    install -m 0755 "/tmp/age/age" "/tmp/age/age-keygen" /usr/local/bin/; \
    chmod 0755 /usr/local/bin/sops; \
    rm -rf /tmp/age /tmp/age.tar.gz /tmp/*.checksums
RUN sops --version && age --version && age-keygen --version

COPY pyproject.toml README.md ./
COPY vaultbox ./vaultbox
RUN pip install --no-cache-dir .
RUN addgroup --system vaultbox && adduser --system --ingroup vaultbox vaultbox
USER vaultbox
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD curl -fsS http://127.0.0.1:8000/health || exit 1
CMD ["uvicorn", "vaultbox.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
