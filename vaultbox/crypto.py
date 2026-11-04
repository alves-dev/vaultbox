from __future__ import annotations

import os
import asyncio
import subprocess
import tempfile
from pathlib import Path

from .config import Settings


class CryptoError(RuntimeError):
    pass


def validate_runtime(settings: Settings) -> dict[str, str]:
    """Validate the complete SOPS/age path before the HTTP server accepts traffic."""
    environment = {"PATH": os.environ.get("PATH", ""), "SOPS_AGE_KEY": settings.age_key}
    try:
        version = subprocess.run(["sops", "--version"], env=environment, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=False,
                                 check=False, timeout=settings.sops_timeout_seconds, text=True)
        if version.returncode != 0:
            raise CryptoError("SOPS executable unavailable")
        age = subprocess.run(["age-keygen", "-y"], env=environment, input=(settings.age_key + "\n"),
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=False,
                              check=False, timeout=settings.sops_timeout_seconds, text=True)
        if age.returncode != 0 or settings.age_recipient not in {line.strip() for line in age.stdout.splitlines()}:
            raise CryptoError("age private key or recipient is invalid")
        probe = transform(b"VAULTBOX_STARTUP_CHECK=ok\n", decrypt=False, settings=settings)
        if transform(probe, decrypt=True, settings=settings) != b"VAULTBOX_STARTUP_CHECK=ok\n":
            raise CryptoError("SOPS+age startup round-trip failed")
        age_version = subprocess.run(["age", "--version"], env=environment, stdin=subprocess.DEVNULL,
                                      stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=False,
                                      check=False, timeout=settings.sops_timeout_seconds, text=True)
        if age_version.returncode != 0:
            raise CryptoError("age executable unavailable")
        return {
            "sops": version.stdout.splitlines()[0].strip() or "unknown",
            "age": age_version.stdout.splitlines()[0].strip() or "unknown",
        }
    except CryptoError:
        raise
    except subprocess.TimeoutExpired:
        raise CryptoError("SOPS+age startup validation timed out") from None
    except (OSError, ValueError):
        raise CryptoError("required runtime binary or configuration is unavailable") from None


def transform(content: bytes, *, decrypt: bool, settings: Settings) -> bytes:
    """Run SOPS with private, mode-0600 files and never expose stderr."""
    try:
        with tempfile.TemporaryDirectory(prefix="vaultbox-", dir="/tmp") as directory:
            root = Path(directory)
            source = root / ("input.env.enc" if decrypt else "input.env")
            target = root / ("output.env" if decrypt else "output.env.enc")
            source.write_bytes(content)
            source.chmod(0o600)
            command = ["sops", "decrypt" if decrypt else "encrypt", "--input-type", "dotenv", "--output-type", "dotenv"]
            if not decrypt:
                command += ["--age", settings.age_recipient]
            command += ["--output", str(target), str(source)]
            environment = {"PATH": os.environ.get("PATH", ""), "SOPS_AGE_KEY": settings.age_key}
            try:
                completed = subprocess.run(
                    command,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    shell=False,
                    check=False,
                    timeout=settings.sops_timeout_seconds,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
                raise CryptoError from exc
            if completed.returncode != 0 or not target.is_file():
                raise CryptoError
            result = target.read_bytes()
            if not result:
                raise CryptoError
            return result
    except (OSError, ValueError) as exc:
        raise CryptoError from exc


async def transform_async(content: bytes, *, decrypt: bool, settings: Settings) -> bytes:
    """Async subprocess variant used by the HTTP handler."""
    try:
        with tempfile.TemporaryDirectory(prefix="vaultbox-", dir="/tmp") as directory:
            root = Path(directory)
            source = root / ("input.env.enc" if decrypt else "input.env")
            target = root / ("output.env" if decrypt else "output.env.enc")
            source.write_bytes(content)
            source.chmod(0o600)
            command = ["sops", "decrypt" if decrypt else "encrypt", "--input-type", "dotenv", "--output-type", "dotenv"]
            if not decrypt:
                command += ["--age", settings.age_recipient]
            command += ["--output", str(target), str(source)]
            environment = {"PATH": os.environ.get("PATH", ""), "SOPS_AGE_KEY": settings.age_key}
            process = await asyncio.create_subprocess_exec(*command, env=environment,
                stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
            try:
                _, _ = await asyncio.wait_for(process.communicate(), timeout=settings.sops_timeout_seconds)
            except asyncio.TimeoutError as exc:
                process.kill()
                await process.wait()
                raise CryptoError from exc
            if process.returncode != 0 or not target.is_file():
                raise CryptoError
            result = target.read_bytes()
            if not result:
                raise CryptoError
            return result
    except (OSError, ValueError) as exc:
        raise CryptoError from exc
