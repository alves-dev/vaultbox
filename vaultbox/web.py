from __future__ import annotations

from html import escape


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vaultbox</title><link rel="stylesheet" href="/static/style.css"></head>
<body><main><header><div class="brand"><img src="/static/vaultbox-mark.png" alt="Vaultbox"><div><h1>Vaultbox</h1><p class="tagline">Secure dotenv encryption</p></div></div><form method="post" action="/logout"><input type="hidden" name="csrf" value="{csrf}"><button>Log out</button></form></header>
<p id="status" role="status" aria-live="polite"></p><section class="panels">
<label>Plaintext (.env)<textarea id="plain" spellcheck="false" autocomplete="off"></textarea></label>
<label>Encrypted (.env.enc)<textarea id="encrypted" spellcheck="false" autocomplete="off"></textarea></label></section>
<nav><button id="encrypt">Encrypt →</button><button id="decrypt">← Decrypt</button><button data-copy="plain">Copy plaintext</button><button data-copy="encrypted">Copy encrypted</button><button id="clear">Clear</button></nav>
<footer class="diagnostics"><span>Vaultbox {app_version}</span><span>SOPS {sops_version}</span><span>age {age_version}</span></footer><script src="/static/app.js" data-csrf="{csrf}" defer></script>
</main></body></html>"""

LOGIN_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Vaultbox login</title><link rel="stylesheet" href="/static/style.css"></head><body><main class="login"><div class="login-brand"><img src="/static/vaultbox-mark.png" alt="Vaultbox"><h1>Vaultbox</h1><p class="tagline">Secure dotenv encryption</p></div><form method="post" action="/login"><label>Username<input name="username" autocomplete="username" required></label><label>Password<input type="password" name="password" autocomplete="current-password" required></label><button>Log in</button>{error}</form></main></body></html>"""


def render(csrf: str, app_version: str, runtime_versions: dict[str, str]) -> str:
    return PAGE.format(
        csrf=escape(csrf, quote=True),
        app_version=escape(app_version),
        sops_version=escape(runtime_versions.get("sops", "unknown")),
        age_version=escape(runtime_versions.get("age", "unknown")),
    )


def render_login(error: str = "") -> str:
    message = f'<p class="form-error" role="alert">{escape(error)}</p>' if error else ""
    return LOGIN_PAGE.format(error=message)
