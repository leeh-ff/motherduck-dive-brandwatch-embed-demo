"""Shared logic for creating MotherDuck embed sessions for the Brandwatch Dive.

Used by the web app (app.py) and the local token check (check_token.py).
Nothing here logs or prints a token or a session string.
"""
import base64
import datetime
import json
import urllib.error
import urllib.request

DIVE_ID = "fb2fef55-5648-404d-986f-90da7eed2278"  # Brandwatch Sentiment Intelligence
TARGET_ACCOUNT = "svc_embed_internal"             # the Dive runs as this (read-only); never from the browser

# The only account allowed to create sessions from this repo.
CALLER_USERNAME = "svc_embed_caller"
CALLER_EMAIL = "sa-3007f7cf-3b7e-4d89-982d-8a12619625bd@sa.motherduck.com"


class SessionError(Exception):
    """A refusal or failure. The message never contains a token or session."""


def token_claims(token: str) -> dict:
    """Decode the token's JWT payload (no signature check: MotherDuck does that)."""
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part))
    except Exception:
        raise SessionError("couldn't read the token's details") from None


def describe_token(claims: dict) -> str:
    exp = claims.get("exp")
    exp_txt = (
        datetime.datetime.fromtimestamp(exp, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if exp else "never"
    )
    return (
        f"account: {claims.get('email', '?')}, type: {claims.get('tokenType', '?')}, "
        f"read-only: {claims.get('readOnly', '?')}, expires: {exp_txt}"
    )


def check_caller_token(token: str) -> dict:
    """Offline check: refuse any token that isn't svc_embed_caller's, or has expired."""
    if not token:
        raise SessionError("no token configured")
    claims = token_claims(token)
    email = claims.get("email", "?")
    if email != CALLER_EMAIL:
        raise SessionError(f"token belongs to {email}, not {CALLER_USERNAME}")
    exp = claims.get("exp")
    if exp and exp < datetime.datetime.now(datetime.timezone.utc).timestamp():
        raise SessionError(f"the {CALLER_USERNAME} token has expired")
    return claims


def create_session(token: str) -> str:
    """Ask MotherDuck for a ~24h read-only embed session, run as TARGET_ACCOUNT."""
    check_caller_token(token)
    req = urllib.request.Request(
        f"https://api.motherduck.com/v1/dives/{DIVE_ID}/embed-session",
        data=json.dumps({"username": TARGET_ACCOUNT}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)["session"]
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        raise SessionError(f"MotherDuck refused: HTTP {e.code}: {body}") from None
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
        raise SessionError(f"couldn't get a session from MotherDuck ({type(e).__name__})") from None
