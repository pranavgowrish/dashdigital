"""UCR NetID (SSO) sign-in via OAuth, without needing an interactive terminal.

    python login.py               # opens a sign-in link; a localhost:5173 listener catches the code
    python login.py --oob         # manual: prints a link that shows a code to paste...
    python login.py --code XXXX   # ...then exchange it (codes expire in ~1 minute)

The refresh token (valid 2 weeks) lives in output/.oauth.json, which is gitignored.
config.connect() uses it automatically.
"""

import argparse
import json
import time
from urllib.parse import urlencode

import requests

import config

OOB_REDIRECT = "urn:ietf:wg:oauth:2.0:oob"
LOCAL_PORT = 5173
LOCAL_REDIRECT = f"http://localhost:{LOCAL_PORT}"
TOKEN_PATH = config.ROOT / "output" / ".oauth.json"
TWO_WEEKS_MIN = 20160


def _client_id():
    import os

    client_id = (os.getenv("ARCGIS_CLIENT_ID") or "").strip()
    if not client_id:
        raise SystemExit("Set ARCGIS_CLIENT_ID in esri/.env first.")
    return client_id


def authorize_url(redirect_uri=OOB_REDIRECT):
    query = urlencode({
        "client_id": _client_id(),
        "response_type": "code",
        "expiration": TWO_WEEKS_MIN,
        "redirect_uri": redirect_uri,
    })
    return f"{config.ARCGIS_URL}/sharing/rest/oauth2/authorize?{query}"


def _token_request(**params):
    resp = requests.post(
        f"{config.ARCGIS_URL}/sharing/rest/oauth2/token",
        data={"client_id": _client_id(), "f": "json", **params},
        timeout=30,
    )
    data = resp.json()
    if "error" in data:
        raise SystemExit(f"OAuth error: {data['error']}")
    return data


def exchange_code(code, redirect_uri=OOB_REDIRECT):
    data = _token_request(grant_type="authorization_code", code=code.strip(), redirect_uri=redirect_uri)
    _save(data)
    return data


def _save(data):
    cached = json.loads(TOKEN_PATH.read_text()) if TOKEN_PATH.exists() else {}
    cached.update({
        "access_token": data["access_token"],
        "expires_at": time.time() + int(data.get("expires_in", 1800)) - 60,
        "username": data.get("username", cached.get("username")),
    })
    if data.get("refresh_token"):
        cached["refresh_token"] = data["refresh_token"]
    TOKEN_PATH.parent.mkdir(exist_ok=True)
    TOKEN_PATH.write_text(json.dumps(cached, indent=2))


def cached_access_token():
    """A valid access token from the cache (refreshing it if needed), or None."""
    if not TOKEN_PATH.exists():
        return None
    cached = json.loads(TOKEN_PATH.read_text())
    if cached.get("expires_at", 0) > time.time():
        return cached["access_token"]
    if cached.get("refresh_token"):
        data = _token_request(grant_type="refresh_token", refresh_token=cached["refresh_token"])
        _save(data)
        return data["access_token"]
    return None


def wait_for_local_code():
    """Serve one request on localhost:5173 and return the ?code= it carries."""
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import parse_qs, urlparse

    captured = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            params = parse_qs(urlparse(self.path).query)
            captured["code"] = params.get("code", [None])[0]
            captured["error"] = params.get("error_description", params.get("error", [None]))[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            msg = "Signed in. You can close this tab." if captured["code"] else f"Sign-in failed: {captured['error']}"
            self.wfile.write(f"<h2>{msg}</h2>".encode())

        def log_message(self, *args):
            pass

    with HTTPServer(("localhost", LOCAL_PORT), Handler) as server:
        while "code" not in captured:
            server.handle_request()
    if not captured["code"]:
        raise SystemExit(f"Sign-in failed: {captured['error']}")
    return captured["code"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--code", help="authorization code shown after an --oob sign-in")
    parser.add_argument("--oob", action="store_true", help="print a link that shows a code instead of using localhost")
    args = parser.parse_args()

    if args.code:
        data = exchange_code(args.code)
    elif args.oob:
        print("Open this link, sign in with your UCR NetID, then quickly run: python login.py --code <code>\n")
        print(authorize_url())
        return
    else:
        url = authorize_url(LOCAL_REDIRECT)
        print(f"Open this link and sign in with your UCR NetID:\n\n{url}\n\nWaiting on {LOCAL_REDIRECT} ...", flush=True)
        import webbrowser
        webbrowser.open(url)
        data = exchange_code(wait_for_local_code(), LOCAL_REDIRECT)
    print(f"Signed in as {data.get('username')}. Token cached in {TOKEN_PATH.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
