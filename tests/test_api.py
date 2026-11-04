from __future__ import annotations

import asyncio
import hashlib
import os
import stat
from pathlib import Path

import httpx
import pytest


@pytest.fixture()
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_sops = tmp_path / "sops"
    fake_sops.write_text("#!/usr/bin/env python3\nimport pathlib,sys\na=sys.argv[1:]\nout=pathlib.Path(a[a.index('--output')+1]); src=pathlib.Path(a[-1]); d=src.read_bytes()\nif 'decrypt' in a:\n  if not d.startswith(b'VAULTBOX-FAKE\\n'): sys.exit(3)\n  out.write_bytes(d[len(b'VAULTBOX-FAKE\\n'):])\nelse: out.write_bytes(b'VAULTBOX-FAKE\\n'+d)\n")
    fake_sops.chmod(fake_sops.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    monkeypatch.setenv("VAULTBOX_AGE_KEY", "AGE-SECRET-KEY-test")
    monkeypatch.setenv("VAULTBOX_AGE_RECIPIENT", "age1test")
    monkeypatch.setenv("VAULTBOX_API_KEYS", '["good-token", "sha256:' + hashlib.sha256(b"hashed-token").hexdigest() + '"]')
    monkeypatch.setenv("VAULTBOX_WEB_USERNAME", "admin")
    monkeypatch.setenv("VAULTBOX_WEB_PASSWORD", "password")
    monkeypatch.setenv("VAULTBOX_SESSION_SECRET", "a-session-secret-long-enough")
    monkeypatch.setenv("VAULTBOX_COOKIE_SECURE", "false")
    monkeypatch.setenv("VAULTBOX_MAX_PAYLOAD_BYTES", "64")
    monkeypatch.setenv("VAULTBOX_SOPS_TIMEOUT", "2")
    from vaultbox.app import create_app
    return create_app()


async def call(app, method: str, url: str, **kwargs):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, url, **kwargs)


def test_round_trip_and_api_keys(app):
    async def flow():
        original = "A=\"um\"\n# comentário\nB=x=y\n\n"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            encrypted = await client.post("/api/v1/encrypt", content=original, headers={"X-API-Key": "good-token", "Content-Type": "text/plain"})
            assert encrypted.status_code == 200
            decrypted = await client.post("/api/v1/decrypt", content=encrypted.content, headers={"X-API-Key": "hashed-token", "Content-Type": "text/plain; charset=utf-8"})
            assert decrypted.status_code == 200
            assert decrypted.content == original.encode()
    asyncio.run(flow())


def test_auth_content_type_and_limits(app):
    async def flow():
        assert (await call(app, "POST", "/api/v1/encrypt", content=b"A=1", headers={"Content-Type": "text/plain"})).status_code == 401
        assert (await call(app, "POST", "/api/v1/encrypt", content=b"A=1", headers={"X-API-Key": "bad", "Content-Type": "text/plain"})).status_code == 401
        assert (await call(app, "POST", "/api/v1/encrypt", content=b"A=1", headers={"X-API-Key": "good-token", "Content-Type": "application/json"})).status_code == 415
        assert (await call(app, "POST", "/api/v1/encrypt", content=b"x" * 65, headers={"X-API-Key": "good-token", "Content-Type": "text/plain"})).status_code == 413
        assert (await call(app, "GET", "/health")).text == "ok\n"
    asyncio.run(flow())


def test_web_login_and_session_csrf(app):
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", follow_redirects=False) as client:
            assert (await client.get("/")).status_code == 303
            invalid = await client.post("/login", data={"username": "admin", "password": "wrong"})
            assert invalid.status_code == 401
            assert "Invalid credentials" in invalid.text
            assert "name=\"username\"" in invalid.text
            login = await client.post("/login", data={"username": "admin", "password": "password"})
            assert login.status_code == 303
            page = await client.get("/")
            assert page.status_code == 200 and "Plaintext" in page.text
            import re
            csrf = re.search(r'data-csrf="([^"]+)"', page.text).group(1)
            response = await client.post("/api/v1/encrypt", content=b"A=1", headers={"X-CSRF-Token": csrf, "Content-Type": "text/plain"})
            assert response.status_code == 200
            assert (await client.post("/logout", data={"csrf": "wrong"})).status_code == 401
    asyncio.run(flow())
