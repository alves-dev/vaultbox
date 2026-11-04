from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import secrets
import threading
from urllib.parse import parse_qs
from importlib.metadata import PackageNotFoundError, version as package_version

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .config import ConfigurationError, Settings
from .crypto import CryptoError, transform_async, validate_runtime
from .web import render, render_login


def create_app() -> FastAPI:
    logger = logging.getLogger("vaultbox")
    app_version = _package_version()
    # Docs are disabled by default; enabling them is an explicit local/admin choice.
    docs = "/docs" if _env_true("VAULTBOX_ENABLE_DOCS") else None
    app = FastAPI(title="Vaultbox", version=app_version, docs_url=docs, redoc_url=None)
    app.state.runtime_versions = {"sops": "not validated", "age": "not validated"}

    async def validate_runtime_configuration():
        # Uvicorn/Docker fail during startup; ASGI unit tests can still call routes directly.
        try:
            configured = settings()
            versions = validate_runtime(configured)
            app.state.runtime_versions = versions
            logger.info("Vaultbox startup validation passed (SOPS %s, age %s, age recipient configured)", versions["sops"], versions["age"])
        except (ConfigurationError, CryptoError) as exc:
            reason = str(exc) if isinstance(exc, CryptoError) else "required environment variable is missing or invalid"
            logger.error("Vaultbox startup validation failed: %s", reason)
            raise RuntimeError("Vaultbox startup validation failed") from None

    app.router.on_startup.append(validate_runtime_configuration)

    def settings() -> Settings:
        try:
            return app.state.settings
        except AttributeError:
            try:
                app.state.settings = Settings.from_env()
                app.state.crypto_slots = threading.BoundedSemaphore(app.state.settings.max_concurrency)
                return app.state.settings
            except (ConfigurationError, ValueError) as exc:
                raise ConfigurationError from exc

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        if request.url.path in {"/api/v1/encrypt", "/api/v1/decrypt"}:
            try:
                if int(request.headers.get("content-length", "0")) > settings().max_payload_bytes:
                    return PlainTextResponse("Payload too large\n", status_code=413)
            except (ConfigurationError, ValueError):
                pass
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path in {"/", "/login"}:
            response.headers["Content-Security-Policy"] = "default-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        return response

    def auth_api(request: Request) -> bool:
        token = request.headers.get("X-API-Key", "")
        if token and settings().api_key_matches(token):
            return True
        session = get_session(request)
        csrf = request.headers.get("X-CSRF-Token", "")
        return bool(session and csrf and secrets.compare_digest(session.get("csrf", ""), csrf))

    def session_serializer() -> URLSafeTimedSerializer:
        return URLSafeTimedSerializer(settings().session_secret, salt="vaultbox-session")

    def get_session(request: Request) -> dict | None:
        raw = request.cookies.get("vaultbox_session")
        if not raw:
            return None
        try:
            value = session_serializer().loads(raw, max_age=8 * 3600)
            return value if isinstance(value, dict) else None
        except BadSignature:
            return None

    def session_response(response: Response, session: dict) -> None:
        response.set_cookie("vaultbox_session", session_serializer().dumps(session), httponly=True,
                            secure=settings().cookie_secure, samesite="strict", max_age=8 * 3600, path="/")

    @app.get("/health")
    async def health():
        return PlainTextResponse("ok\n")

    @app.post("/api/v1/{operation}")
    async def api_operation(operation: str, request: Request):
        if operation not in {"encrypt", "decrypt"}:
            return PlainTextResponse("Not found\n", status_code=404)
        try:
            s = settings()
        except ConfigurationError:
            return PlainTextResponse("Service not configured\n", status_code=503)
        if not auth_api(request):
            return PlainTextResponse("Unauthorized\n", status_code=401)
        content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type != "text/plain":
            return PlainTextResponse("Unsupported media type\n", status_code=415)
        body_buffer = bytearray()
        async for chunk in request.stream():
            if len(body_buffer) + len(chunk) > s.max_payload_bytes:
                return PlainTextResponse("Payload too large\n", status_code=413)
            body_buffer.extend(chunk)
        body = bytes(body_buffer)
        if not body.strip():
            return PlainTextResponse("Invalid content\n", status_code=400)
        try:
            with app.state.crypto_slots:
                result = await transform_async(body, decrypt=operation == "decrypt", settings=s)
        except CryptoError:
            return PlainTextResponse("Unable to process content\n", status_code=422)
        return PlainTextResponse(result, media_type="text/plain")

    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def root(request: Request):
        if get_session(request) is None:
            return RedirectResponse("/login", status_code=303)
        session = get_session(request)
        return HTMLResponse(render(session["csrf"], app_version, app.state.runtime_versions))

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        if get_session(request) is not None:
            return RedirectResponse("/", status_code=303)
        return HTMLResponse(render_login())

    @app.post("/login")
    async def login(request: Request):
        body = parse_qs((await request.body()).decode("utf-8", "replace"))
        import hmac
        valid = hmac.compare_digest(body.get("username", [""])[0], settings().web_username) and hmac.compare_digest(body.get("password", [""])[0], settings().web_password)
        if not valid:
            return HTMLResponse(render_login("Invalid credentials"), status_code=401)
        response = RedirectResponse("/", status_code=303)
        session_response(response, {"csrf": secrets.token_urlsafe(32)})
        return response

    @app.post("/logout")
    async def logout(request: Request):
        session = get_session(request)
        if session is None or not secrets.compare_digest(session.get("csrf", ""), request.headers.get("X-CSRF-Token", "") or parse_qs((await request.body()).decode()).get("csrf", [""])[0]):
            return PlainTextResponse("Unauthorized\n", status_code=401)
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie("vaultbox_session", path="/")
        return response

    return app


def _env_true(name: str) -> bool:
    import os
    return os.environ.get(name, "false").lower() in {"1", "true", "yes"}


def _package_version() -> str:
    try:
        return package_version("vaultbox")
    except PackageNotFoundError:
        return "0.2.0"


app = create_app()
