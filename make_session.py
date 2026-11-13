#!/usr/bin/env python3
"""Create a 24-hour MotherDuck embed session for the Brandwatch Dive.

The session is requested with the svc_embed_caller token and runs the Dive as
svc_embed_internal (read-only). It is written to session.js next to this script.
Nothing secret is printed.

Token: read ONLY from $TOKEN_FILE (default ~/.motherduck_svc_embed_caller_read_write_token_01).
The script refuses any token that does not belong to svc_embed_caller. Two checks
must both pass before MotherDuck is asked for a session:
  1. offline: the token's account email matches svc_embed_caller's
  2. online:  MotherDuck reports current_user = svc_embed_caller (needs the duckdb CLI)
"""
import base64
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

DIVE_ID = "fb2fef55-5648-404d-986f-90da7eed2278"  # Brandwatch Sentiment Intelligence
TARGET_ACCOUNT = "svc_embed_internal"             # the Dive runs as this (read-only)

# The only account allowed to create sessions from this repo.
CALLER_USERNAME = "svc_embed_caller"
CALLER_EMAIL = "sa-3007f7cf-3b7e-4d89-982d-8a12619625bd@sa.motherduck.com"

TOKEN_FILE = pathlib.Path(
    os.environ.get("TOKEN_FILE") or "~/.motherduck_svc_embed_caller_read_write_token_01"
).expanduser()


def refuse(msg: str) -> None:
    sys.exit(f"REFUSED: {msg}\nThis repo only ever uses the {CALLER_USERNAME} token.")


if not TOKEN_FILE.is_file():
    refuse(f"token file not found: {TOKEN_FILE}")
token = TOKEN_FILE.read_text().strip()
if not token:
    refuse(f"token file is empty: {TOKEN_FILE}")

# --- Check 1 (offline): who does the token say it is? -----------------------
try:
    part = token.split(".")[1]
    part += "=" * (-len(part) % 4)
    claims = json.loads(base64.urlsafe_b64decode(part))
except Exception:
    refuse("couldn't read the token's details")

email = claims.get("email", "?")
exp = claims.get("exp")
exp_txt = datetime.datetime.fromtimestamp(exp, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if exp else "never"

print(f"Using token: {TOKEN_FILE.name}")
print(f"  account:  {email}")
print(f"  type:     {claims.get('tokenType', '?')} (read-only: {claims.get('readOnly', '?')})")
print(f"  expires:  {exp_txt}")

if email != CALLER_EMAIL:
    refuse(f"token belongs to {email}, not {CALLER_USERNAME}")

# --- Check 2 (online): ask MotherDuck who this token is ---------------------
cli = shutil.which("duckdb")
if not cli:
    refuse("duckdb CLI not found, so the account can't be confirmed with MotherDuck")
try:
    r = subprocess.run(
        [cli, "-noheader", "-list", "md:", "-c", "SELECT current_user"],
        env={**os.environ, "motherduck_token": token},  # token via env, never argv
        capture_output=True, text=True, timeout=90,
    )
except subprocess.TimeoutExpired:
    refuse("timed out confirming the account with MotherDuck")
if r.returncode != 0:
    err = r.stderr.strip().splitlines()
    refuse(f"couldn't confirm the account with MotherDuck ({err[0][:200] if err else 'unknown error'})")

user = r.stdout.strip()
print(f"  user:     {user}")
if user != CALLER_USERNAME:
    refuse(f"MotherDuck says this token is {user!r}, not {CALLER_USERNAME}")

# --- Create the session -----------------------------------------------------
req = urllib.request.Request(
    f"https://api.motherduck.com/v1/dives/{DIVE_ID}/embed-session",
    data=json.dumps({"username": TARGET_ACCOUNT}).encode(),
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        session = json.load(resp)["session"]
except urllib.error.HTTPError as e:
    sys.exit(f"MotherDuck refused: HTTP {e.code}: {e.read().decode(errors='replace')[:500]}")

out = pathlib.Path(__file__).with_name("session.js")
out.write_text(f"window.EMBED_SESSION = {json.dumps(session)};\n")
os.chmod(out, 0o600)
print(f"Session written to {out.name} (valid ~24h).")
