# MotherDuck Dive embed demo (Brandwatch)

A local prototype showing the MotherDuck Dive **Brandwatch Sentiment Intelligence** embedded in a web page via an iframe. The page around it ("Insight Hub") is fictional decoration.

## How it works

1. `make_session.py` calls MotherDuck's API with the caller token (`svc_embed_caller`, Admin role) and asks for an embed session for the Dive, run as `svc_embed_internal`.
2. MotherDuck returns a read-only session string, valid 24h. It is written to `session.js`, which is git-ignored.
3. `index.html` loads the Dive in an iframe:
   `https://embed-motherduck.com/sandbox/#session=<session>`
4. `serve.py` serves the folder on http://localhost:8000 with caching disabled.

## Run it

```bash
make serve    # token read from ~/.motherduck_svc_embed_caller_read_write_token_01 (or $TOKEN_FILE)
```

Requires Python 3 and the `duckdb` CLI.

**Only the `svc_embed_caller` token is ever used.** Before asking for a session, the script prints the token file, account, type and expiry (never the token itself). It refuses to continue unless both checks pass:
1. **Offline:** the token's account email matches `svc_embed_caller`.
2. **Online:** MotherDuck confirms `current_user = svc_embed_caller`.

Any other token (a personal admin token, another service account) is refused. There is no fallback to environment variables or a prompt.

## Accounts

| Account | Role | Purpose |
| --- | --- | --- |
| `svc_embed_caller` | Admin | Creates embed sessions. Tested 2026-11-13: Explorer and Builder were refused. |
| `svc_embed_internal` | Explorer | The identity the Dive runs as. Has read access to the `brandwatch` share only. |

## Rules for a real deployment

- The caller token stays server-side only (e.g. Azure Key Vault): never in code, the repo, logs or the browser.
- Hard-code `svc_embed_internal` as the run-as account; never take it from the browser.
- Put the site behind company login (Entra ID).
- Session strings are credentials: don't log them. Refresh them before the 24h expiry.
- New Dives start private; share them with `svc_embed_internal` before embedding.

Docs: https://motherduck.com/docs/key-tasks/dives/embedding-dives/
