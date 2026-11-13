"""Web app for the Brandwatch Dive embed.

Serves index.html and /api/session, which hands the page a MotherDuck embed
session created server-side with the svc_embed_caller token.

In Azure (App Service), login is enforced by App Service Authentication
("Easy Auth") locked to the company Entra ID tenant. This app also refuses
/api/session unless Easy Auth has identified the user, so it fails closed if
Easy Auth is ever switched off.

Token source:
  Azure: app setting MOTHERDUCK_CALLER_TOKEN (ideally a Key Vault reference).
  Local: LOCAL_DEV=1 and the token file at $TOKEN_FILE
         (default ~/.motherduck_svc_embed_caller_read_write_token_01).
"""
import logging
import os
import pathlib
import threading
import time

from flask import Flask, abort, jsonify, request, send_from_directory

from motherduck_session import SessionError, check_caller_token, create_session

HERE = pathlib.Path(__file__).parent
IN_AZURE = bool(os.environ.get("WEBSITE_SITE_NAME"))  # set by App Service
LOCAL_DEV = os.environ.get("LOCAL_DEV") == "1" and not IN_AZURE

# Each session is valid ~24h from creation. Hand out one that is at most this
# old, so every page load gets at least ~12h of use before it expires.
SESSION_MAX_AGE = 12 * 60 * 60

log = logging.getLogger("dive-embed")
logging.basicConfig(level=logging.INFO)
app = Flask(__name__, static_folder=None)

_lock = threading.Lock()
_cached = {"session": None, "created": 0.0}


def _caller_token() -> str:
    if LOCAL_DEV:
        path = pathlib.Path(
            os.environ.get("TOKEN_FILE") or "~/.motherduck_svc_embed_caller_read_write_token_01"
        ).expanduser()
        return path.read_text().strip() if path.is_file() else ""
    return os.environ.get("MOTHERDUCK_CALLER_TOKEN", "").strip()


def _get_session() -> str:
    with _lock:
        if _cached["session"] and time.time() - _cached["created"] < SESSION_MAX_AGE:
            return _cached["session"]
        session = create_session(_caller_token())
        _cached.update(session=session, created=time.time())
        log.info("Created a new embed session")
        return session


def _signed_in_user() -> str | None:
    # Easy Auth strips any client-supplied X-MS-CLIENT-PRINCIPAL-* headers and
    # sets them itself for signed-in users.
    return request.headers.get("X-MS-CLIENT-PRINCIPAL-ID")


@app.after_request
def _headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.get("/api/session")
def session():
    if not LOCAL_DEV and not _signed_in_user():
        abort(401)
    try:
        return jsonify(session=_get_session())
    except SessionError as e:
        log.error("Embed session refused: %s", e)
        return jsonify(error="Couldn't create a dashboard session. See the app logs."), 502


@app.get("/healthz")
def healthz():
    return "ok"


if IN_AZURE:
    # Fail fast in the logs if the token setting is missing or wrong.
    try:
        check_caller_token(_caller_token())
    except SessionError as e:
        log.error("MOTHERDUCK_CALLER_TOKEN problem: %s", e)


if __name__ == "__main__":
    if not LOCAL_DEV:
        raise SystemExit("For local runs use `make serve` (sets LOCAL_DEV=1).")
    print("Serving on http://localhost:8000 (local dev, no login). Ctrl+C to stop.")
    app.run(host="127.0.0.1", port=8000)
