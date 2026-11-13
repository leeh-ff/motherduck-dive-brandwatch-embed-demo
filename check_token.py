#!/usr/bin/env python3
"""Check that a token file holds the svc_embed_caller token, before you put it in Azure.

Token: read ONLY from $TOKEN_FILE (default ~/.motherduck_svc_embed_caller_read_write_token_01).
Two checks must both pass:
  1. offline: the token's account email matches svc_embed_caller's, and it hasn't expired
  2. online:  MotherDuck reports current_user = svc_embed_caller (needs the duckdb CLI)
Nothing secret is printed.
"""
import os
import pathlib
import shutil
import subprocess
import sys

from motherduck_session import CALLER_USERNAME, SessionError, check_caller_token, describe_token, token_claims

TOKEN_FILE = pathlib.Path(
    os.environ.get("TOKEN_FILE") or "~/.motherduck_svc_embed_caller_read_write_token_01"
).expanduser()


def refuse(msg: str) -> None:
    sys.exit(f"REFUSED: {msg}\nThis repo only ever uses the {CALLER_USERNAME} token.")


if not TOKEN_FILE.is_file():
    refuse(f"token file not found: {TOKEN_FILE}")
token = TOKEN_FILE.read_text().strip()

# --- Check 1 (offline) -------------------------------------------------------
try:
    print(f"Token file: {TOKEN_FILE.name}\n  {describe_token(token_claims(token))}")
    check_caller_token(token)
except SessionError as e:
    refuse(str(e))

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
print(f"  user: {user}")
if user != CALLER_USERNAME:
    refuse(f"MotherDuck says this token is {user!r}, not {CALLER_USERNAME}")
print(f"OK: this is the {CALLER_USERNAME} token.")
